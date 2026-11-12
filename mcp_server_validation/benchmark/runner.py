from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Union
from datetime import datetime

from benchmark.case import BenchmarkCase
from benchmark.evaluator import BenchmarkEvaluator
from benchmark.prompt import TaskPromptBuilder
from discopop.runner import DiscoPoPRunner
from llm.claude_code import ClaudeCodeClient
from llm.opencode import OpenCodeClient


class BenchmarkRunner:
    """
    Main benchmark orchestrator.

    Benchmark modes:

        DIRECT
            OpenCode coding agent
            DiscoPoP: OFF
            MCP: OFF

        FULL_DISCOPOP
            DiscoPoP is executed before OpenCode
            Full DiscoPoP output is available in workspace
            MCP: OFF

        MCP
            DiscoPoP is not executed by the benchmark runner.
            DiscoPoP MCP server is enabled.
            OpenCode is responsible for initializing, building,
            profiling and querying DiscoPoP through MCP.

        FORCE_MCP
            Same runtime as MCP, with a mandatory MCP workflow in the prompt.
    """

    MODES = (
        "direct",
        "full_discopop",
        "mcp",
        "force_mcp",
    )
    MCP_MODES = ("mcp", "force_mcp")

    # The agent follows the selected condition's prompt. A coding agent can still
    # stop after making an edit that fails the final, external evaluation, though.
    # Give it the evaluator's concrete compiler/test diagnostics and a bounded
    # opportunity to repair its own work before recording the mode as failed.
    MAX_SESSION_TURNS = 2

    def __init__(
        self,
        llm_client: Union[OpenCodeClient, ClaudeCodeClient],
        output_root: Path,
    ):
        """
        Parameters
        ----------
        llm_client:
            Despite the historical variable name, this must be an
            OpenCodeClient or a ClaudeCodeClient.

        output_root:
            Directory in which benchmark results are stored.
        """

        if not isinstance(llm_client, (OpenCodeClient, ClaudeCodeClient)):
            raise TypeError(
                "BenchmarkRunner requires an OpenCodeClient or ClaudeCodeClient. "
                "Select one of the supported coding agents."
            )

        self.llm = llm_client
        self.output_root = Path(output_root).resolve()

        self.prompts = TaskPromptBuilder()
        self.discopop = DiscoPoPRunner()
        self.evaluator = BenchmarkEvaluator()

    # ==================================================================
    # PUBLIC API
    # ==================================================================

    def _case_output_root(
        self,
        case: BenchmarkCase,
    ) -> Path:
        """
        Create a unique output directory for one benchmark case.
        """

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        return (
            self.output_root
            / f"{timestamp}_{case.repository}_{case.name}"
        )

    def run_case(
        self,
        case: BenchmarkCase,
    ) -> dict[str, Any]:

        case_output = self._case_output_root(case)

        case_output.mkdir(
            parents=True,
            exist_ok=True,
        )

        results: dict[str, Any] = {}

        print()
        print("=" * 80)
        print(f"BENCHMARK CASE: {case.name}")
        print("=" * 80)

        # ==============================================================
        # Run all benchmark modes
        # ==============================================================

        for mode in self.MODES:

            print()
            print("=" * 80)
            print(f"MODE: {mode.upper()}")
            print("=" * 80)

            try:
                results[mode] = self.run_mode(
                    case=case,
                    mode=mode,
                    case_output=case_output,
                )

            except Exception as exc:
                print()
                print(
                    f"[Benchmark] Mode '{mode}' failed:"
                )
                print(exc)

                results[mode] = {
                    "mode": mode,
                    "case": case.name,
                    "success": False,
                    "status": "runner_failed",
                    "error": str(exc),
                }

        # ==============================================================
        # Write complete result JSON
        # ==============================================================

        result_file = case_output / "result.json"

        self._write_json(
            result_file,
            results,
        )

        print()
        print(
            "[Benchmark] Results written to: "
            f"{result_file}"
        )

        # ==============================================================
        # Final benchmark results table
        # ==============================================================

        print()
        print("=" * 110)
        print("BENCHMARK RESULTS")
        print("=" * 110)

        print(
            f"{'Mode':<20}"
            f"{'Input token':>15}"
            f"{'Output token':>15}"
            f"{'Total token':>15}"
            f"{'Accuracy':>12}"
            f"{'Latency':>12}"
            f"{'Performance':>20}"
        )

        for mode in self.MODES:

            result = results.get(
                mode,
                {},
            )

            # ----------------------------------------------------------
            # Token usage
            # ----------------------------------------------------------

            tokens = result.get(
                "tokens",
                {},
            )

            input_tokens = tokens.get(
                "input",
                0,
            )

            output_tokens = tokens.get(
                "output",
                0,
            )

            total_tokens = tokens.get(
                "total",
                0,
            )

            # ----------------------------------------------------------
            # Accuracy
            # ----------------------------------------------------------

            status = result.get(
                "status"
            )

            if status in {
                "discopop_failed",
                "runner_failed",
            }:
                accuracy = "N/A"

            elif "success" not in result:
                accuracy = "N/A"

            else:
                accuracy = (
                    "PASS"
                    if result.get(
                        "success",
                        False,
                    )
                    else "FAIL"
                )

            # ----------------------------------------------------------
            # Latency
            # ----------------------------------------------------------

            latency = result.get(
                "latency_seconds"
            )

            if latency is None:
                latency_text = "N/A"

            else:
                latency_text = (
                    f"{latency:.3f}s"
                )

            performance_text = self._performance_status(result)

            # ----------------------------------------------------------
            # Print row
            # ----------------------------------------------------------

            print(
                f"{mode:<20}"
                f"{input_tokens:>15,}"
                f"{output_tokens:>15,}"
                f"{total_tokens:>15,}"
                f"{accuracy:>12}"
                f"{latency_text:>12}"
                f"{performance_text:>20}"
            )

        print("=" * 110)

        return results

    # ==================================================================
    # MODE
    # ==================================================================

    def run_mode(
        self,
        case: BenchmarkCase,
        mode: str,
        case_output: Path,
    ) -> dict[str, Any]:

        if mode not in self.MODES:
            raise ValueError(
                f"Unknown benchmark mode: {mode}"
            )

        mode_output = case_output / mode
        mode_output.mkdir(
            parents=True,
            exist_ok=True,
        )

        # --------------------------------------------------------------
        # 1. Create isolated workspace
        # --------------------------------------------------------------

        workspace = (
            mode_output
            / "workspace"
        )

        self._prepare_workspace(
            source=case.workspace,
            destination=workspace,
        )

        print(
            f"[Benchmark] Workspace: {workspace}"
        )

        isolated_case = self._case_with_workspace(
            case,
            workspace,
        )

        # --------------------------------------------------------------
        # 2. DiscoPoP
        #
        # DIRECT:
        #     Do not run DiscoPoP.
        #
        # FULL_DISCOPOP:
        #     Run DiscoPoP and expose generated analysis to OpenCode.
        #
        # MCP / FORCE_MCP:
        #     Do not prepare or run DiscoPoP in advance. The agent may use the
        #     enabled MCP server according to the condition's prompt.
        # --------------------------------------------------------------

        discopop_result = None

        if mode == "full_discopop":

            discopop_result = self.discopop.run(
                isolated_case
            )

            self._write_json(
                mode_output / "discopop.json",
                discopop_result,
            )

            if not discopop_result.get(
                    "analysis_available",
                    False,
            ):
                print()
                print(
                    "[Benchmark] DiscoPoP analysis failed."
                )
                print(
                    f"[Benchmark] Stage: "
                    f"{discopop_result.get('stage')}"
                )
                print(
                    f"[Benchmark] Return code: "
                    f"{discopop_result.get('returncode')}"
                )
                if discopop_result.get("missing_artifacts"):
                    print()
                    print(
                        "[DiscoPoP] Missing profiler artifacts: "
                        + ", ".join(discopop_result["missing_artifacts"])
                    )

                return {
                    "mode": mode,
                    "case": case.name,
                    "success": False,
                    "status": "discopop_failed",
                    "workspace": str(workspace),
                    "discopop": discopop_result,
                }

        elif mode in self.MCP_MODES:

            print()
            print(
                "[Benchmark] DiscoPoP MCP is configured; agent startup reports availability."
            )
        # --------------------------------------------------------------
        # 3. Build prompt
        # --------------------------------------------------------------

        prompt = self._build_prompt(
            isolated_case,
            mode,
        )

        prompt_file = (
            mode_output
            / "prompt.txt"
        )

        prompt_file.write_text(
            prompt,
            encoding="utf-8",
        )

        # --------------------------------------------------------------
        # 4. MCP configuration
        # --------------------------------------------------------------
        #
        # IMPORTANT:
        #
        # DIRECT          -> False
        # FULL_DISCOPOP   -> False
        # MCP             -> True
        # FORCE_MCP       -> True
        #
        # This guarantees that only the MCP benchmark conditions have
        # access to the DiscoPoP MCP server.
        # --------------------------------------------------------------

        mcp_enabled = (
            mode in self.MCP_MODES
        )

        print()
        print(
            "[Benchmark] MCP enabled: "
            f"{mcp_enabled}"
        )

        # --------------------------------------------------------------
        # 5. Run OpenCode
        # --------------------------------------------------------------

        events_file = (
            mode_output
            / "events.jsonl"
        )

        print()
        print(
            "[Benchmark] Starting Agent..."
        )

        session_started = time.perf_counter()
        start_time = time.perf_counter()

        llm_result = self.llm.run(
            prompt=prompt,
            workspace=workspace,
            mcp_enabled=mcp_enabled,
            events_file=events_file,
        )

        latency = (
            time.perf_counter()
            - start_time
        )

        self._write_json(
            mode_output / "llm_result.json",
            llm_result,
        )

        # --------------------------------------------------------------
        # 6. Evaluate modified repository
        # --------------------------------------------------------------

        print()
        print(
            "[Benchmark] Evaluating result..."
        )

        evaluation = self._evaluate_hidden_tests(
            source=case.workspace,
            agent_workspace=workspace,
            evaluation_workspace=mode_output / "evaluation_workspace",
            case=isolated_case,
        )
        self._print_evaluation_output(evaluation)

        self._write_json(
            mode_output / "evaluation.json",
            evaluation,
        )
        evaluation_file = mode_output / "evaluation.json"

        attempts = [
            {
                "kind": "initial",
                "llm_result": llm_result,
                "evaluation": evaluation,
                "events": str(events_file),
                "latency_seconds": latency,
            }
        ]

        session_id = llm_result.get("session_id")

        for turn_number in range(2, self.MAX_SESSION_TURNS + 1):
            if evaluation.get("passed", False):
                break

            if not isinstance(session_id, str) or not session_id:
                attempts.append(
                    {
                        "kind": "continuation_unavailable",
                        "reason": "OpenCode did not emit a session identifier.",
                        "llm_result": {"usage": {}, "mcp_usage": {}},
                        "evaluation": evaluation,
                        "latency_seconds": 0.0,
                    }
                )
                break

            remediation_prompt = self._build_remediation_prompt(
                case=isolated_case,
                evaluation=evaluation,
                turn_number=turn_number,
            )
            remediation_prompt_file = mode_output / f"turn_{turn_number}_prompt.txt"
            remediation_prompt_file.write_text(remediation_prompt, encoding="utf-8")
            remediation_events_file = mode_output / f"turn_{turn_number}_events.jsonl"

            print()
            print(
                f"[Benchmark] Continuing OpenCode session, turn {turn_number}/"
                f"{self.MAX_SESSION_TURNS}, after {evaluation.get('status', 'failure')}..."
            )

            remediation_started = time.perf_counter()
            try:
                remediation_result = self.llm.run(
                    prompt=remediation_prompt,
                    workspace=workspace,
                    mcp_enabled=mcp_enabled,
                    events_file=remediation_events_file,
                    session_id=session_id,
                )
            except Exception as exc:
                remediation_result = {
                    "error": str(exc),
                    "usage": {},
                    "mcp_usage": {},
                }
            remediation_latency = time.perf_counter() - remediation_started
            self._write_json(
                mode_output / f"turn_{turn_number}_llm_result.json",
                remediation_result,
            )

            evaluation = self._evaluate_hidden_tests(
                source=case.workspace,
                agent_workspace=workspace,
                evaluation_workspace=mode_output / "evaluation_workspace",
                case=isolated_case,
            )
            self._print_evaluation_output(evaluation)
            self._write_json(
                mode_output / f"turn_{turn_number}_evaluation.json",
                evaluation,
            )
            evaluation_file = mode_output / f"turn_{turn_number}_evaluation.json"
            attempts.append(
                {
                    "kind": "continuation",
                    "turn": turn_number,
                    "llm_result": remediation_result,
                    "evaluation": evaluation,
                    "prompt": str(remediation_prompt_file),
                    "events": str(remediation_events_file),
                    "latency_seconds": remediation_latency,
                }
            )

            if remediation_result.get("error"):
                break

            session_id = remediation_result.get("session_id") or session_id

        agent_latency = sum(
            attempt["latency_seconds"]
            for attempt in attempts
        )
        latency = time.perf_counter() - session_started

        # --------------------------------------------------------------
        # 7. Create patch
        # --------------------------------------------------------------

        patch_file = (
            mode_output
            / "patch.diff"
        )

        self._create_patch(
            source=case.workspace,
            modified=workspace,
            output=patch_file,
        )

        # --------------------------------------------------------------
        # 8. Extract usage
        # --------------------------------------------------------------

        usage = self._merge_usage(
            [attempt["llm_result"].get("usage", {}) for attempt in attempts]
        )

        mcp_usage = self._merge_mcp_usage(
            [attempt["llm_result"].get("mcp_usage", {}) for attempt in attempts]
        )

        # --------------------------------------------------------------
        # 9. Build final result
        # --------------------------------------------------------------

        result = {
            "mode": mode,
            "case": case.name,

            "success": evaluation.get(
                "passed",
                False,
            ),

            "status": evaluation.get(
                "status",
                "unknown",
            ),

            "latency_seconds": latency,
            "agent_latency_seconds": agent_latency,

            "tokens": {
                "input": usage.get(
                    "input_tokens",
                    0,
                ),
                "output": usage.get(
                    "output_tokens",
                    0,
                ),
                "total": usage.get(
                    "total_tokens",
                    0,
                ),
                "reasoning": usage.get(
                    "reasoning_tokens",
                    0,
                ),
                "cache_read": usage.get(
                    "cache_read_tokens",
                    0,
                ),
                "cache_write": usage.get(
                    "cache_write_tokens",
                    0,
                ),
            },

            "mcp": {
                "enabled": mcp_enabled,
                "availability_by_invocation": [
                    attempt["llm_result"]["mcp_availability"]
                    for attempt in attempts
                    if "mcp_availability" in attempt["llm_result"]
                ],

                "used": mcp_usage.get(
                    "used",
                    False,
                ),

                "tool_calls": mcp_usage.get(
                    "tool_calls",
                    0,
                ),

                "tools": mcp_usage.get(
                    "tools",
                    {},
                ),
            },

            "workspace": str(
                workspace
            ),

            "files": {
                "prompt": str(
                    prompt_file
                ),

                "events": str(
                    events_file
                ),

                "patch": str(
                    patch_file
                ),

                "evaluation": str(
                    evaluation_file
                ),

                "discopop": (
                    str(
                        mode_output
                        / "discopop.json"
                    )
                    if discopop_result is not None
                    else None
                ),
            },

            "attempts": [
                {
                    key: value
                    for key, value in attempt.items()
                    if key != "llm_result"
                }
                for attempt in attempts
            ],

            "evaluation": evaluation,

            "performance": evaluation.get("performance"),
            "performance_point": self._performance_point(evaluation),

            "discopop": discopop_result,
        }

        self._write_json(
            mode_output / "result.json",
            result,
        )

        # --------------------------------------------------------------
        # 10. Console summary
        # --------------------------------------------------------------

        print()
        print(
            f"[Benchmark] {mode}: "
            f"{result['status']}"
        )

        print(
            f"[Benchmark] Passed: "
            f"{result['success']}"
        )

        print(
            f"[Benchmark] Tokens: "
            f"{result['tokens']['total']}"
        )

        print(
            f"[Benchmark] Latency: "
            f"{result['latency_seconds']:.3f}s"
        )
        self._print_performance_summary(mode, result)
        return result

    @staticmethod
    def _merge_usage(usages: list[dict[str, Any]]) -> dict[str, int]:
        """Sum invocation usage while retaining the final inference-step size."""
        keys = (
            "steps",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "reasoning_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
        )
        merged = {key: 0 for key in keys}
        last_step_keys = tuple("last_step_" + key for key in keys[1:])
        merged.update({key: 0 for key in last_step_keys})
        for usage in usages:
            if not isinstance(usage, dict):
                continue
            for key in keys:
                value = usage.get(key, 0)
                if isinstance(value, int):
                    merged[key] += value
            for key in last_step_keys:
                value = usage.get(key)
                if isinstance(value, int):
                    merged[key] = value
        return merged

    @staticmethod
    def _merge_mcp_usage(usages: list[dict[str, Any]]) -> dict[str, Any]:
        tools: dict[str, int] = {}
        tool_calls = 0
        for usage in usages:
            if not isinstance(usage, dict):
                continue
            value = usage.get("tool_calls", 0)
            if isinstance(value, int):
                tool_calls += value
            tools_by_name = usage.get("tools", {})
            if not isinstance(tools_by_name, dict):
                continue
            for name, count in tools_by_name.items():
                if isinstance(count, int):
                    tools[name] = tools.get(name, 0) + count
        return {"used": bool(tool_calls), "tool_calls": tool_calls, "tools": dict(sorted(tools.items()))}

    @staticmethod
    def _performance_point(evaluation: dict[str, Any]) -> int | None:
        performance = evaluation.get("performance")
        if not isinstance(performance, dict) or not performance.get("available"):
            return None
        report = performance.get("report")
        if not isinstance(report, dict):
            return None
        point = report.get("performance_point")
        return point if type(point) is int and point in (0, 1) else None

    @staticmethod
    def _performance_status(result: dict[str, Any]) -> str:
        performance = result.get("performance")
        if not isinstance(performance, dict):
            return "N/A"
        if not performance.get("available", False):
            return "unavailable"
        report = performance.get("report")
        if not isinstance(report, dict):
            return "unavailable"
        status = report.get("status")
        if status in {"pass", "fail", "inconclusive"}:
            label = "INCONCLUSIVE" if status == "inconclusive" else status.upper()
            ratio = None
            comparisons = report.get("comparisons")
            if isinstance(comparisons, list) and comparisons:
                ratio = comparisons[0].get("ratio") if isinstance(comparisons[0], dict) else None
            if isinstance(ratio, (int, float)):
                return f"{label} {ratio:.2f}x"
            return label
        comparisons = report.get("comparisons")
        if report.get("methodology") == "paired_rounds_v1" and isinstance(comparisons, list) and len(comparisons) >= 2:
            comparison = comparisons[1]  # Candidate 4 workers against its reference.
            ratio = comparison.get("ratio")
            evidence = comparison.get("evidence")
            label = {"above_one": "faster", "below_one": "slower"}.get(evidence, "uncertain")
            if isinstance(ratio, (int, float)):
                return f"{ratio:.2f}x ({label})"
        if isinstance(comparisons, list):
            return f"{len(comparisons)} comparison(s)"
        return "available"

    @classmethod
    def _print_performance_summary(
        cls,
        mode: str,
        result: dict[str, Any],
    ) -> None:
        """Print task-defined measurements and any separate performance point."""
        performance = result.get("performance")
        if not isinstance(performance, dict):
            return

        print(f"[Benchmark] Performance ({mode}): {cls._performance_status(result)}")
        if not performance.get("available", False):
            error = performance.get("error")
            if error:
                print(f"  Measurement error: {error}")
            return

        report = performance.get("report")
        if not isinstance(report, dict):
            return

        if report.get("status") in {"pass", "fail", "inconclusive"}:
            print(
                f"  Performance point: {report.get('performance_point')} "
                f"(threshold={report.get('threshold_ratio')}, "
                f"95% interval={report.get('confidence_interval_95')})"
            )

        workloads = report.get("workloads")
        if isinstance(workloads, list):
            calibration = report.get("calibration", {})
            print(f"  Primary: performance / Program / 4t vs ref; {report.get('repetitions')} paired rounds.")
            for workload in workloads:
                parameters = workload.get("parameters", {})
                dimensions = parameters.get("dimensions", parameters)
                size = ", ".join(f"{key}={value}" for key, value in dimensions.items())
                print(f"  {workload.get('label')}: {size}; batch={workload.get('batch_invocations')}")

            metrics = [(workload.get("label", "workload"), metric)
                       for workload in workloads for metric in workload.get("metrics", [])]
            has_reference_four = any(
                measurement.get("workers") == 4 and "reference" in measurement.get("label", "")
                for _, metric in metrics for measurement in metric.get("measurements", []))
            time_rows, ratio_rows, reference_scaling = [], [], []
            for label, metric in metrics:
                scope = {"end_to_end_wall_time_seconds": "Program", "kernel_wall_time_seconds": "Kernel"}.get(
                    metric.get("metric"), metric.get("metric", "unspecified"))
                measurements = metric.get("measurements", [])

                def milliseconds(candidate, workers):
                    value = next((item.get("median") for item in measurements
                                  if item.get("workers") == workers and
                                  (item.get("label") == "candidate" if candidate else
                                   "reference" in item.get("label", ""))), None)
                    return f"{value * 1000:.3f}" if isinstance(value, (int, float)) else "-"

                row = [label, scope, milliseconds(False, 1)]
                if has_reference_four:
                    row.append(milliseconds(False, 4))
                time_rows.append([*row, milliseconds(True, 1), milliseconds(True, 4)])
                comparisons = {item.get("label"): item for item in metric.get("comparisons", [])}
                one = comparisons.get("candidate_1_worker_vs_serial_reference",
                                      comparisons.get("candidate_vs_reference_1_worker", {}))
                four = comparisons.get("candidate_4_workers_vs_serial_reference",
                                       comparisons.get("candidate_vs_reference_4_workers", {}))
                scaling = comparisons.get("candidate_scaling_1_to_4_workers", {})
                ratio_rows.append([label, scope, *[cls._format_speedup(item) for item in (one, four, scaling)]])
                if "reference_scaling_1_to_4_workers" in comparisons:
                    reference_scaling.append(
                        f"  Reference scaling {label}/{scope}, 1t -> 4t: "
                        + cls._format_speedup(comparisons["reference_scaling_1_to_4_workers"]))

            time_headers = ["Workload", "Scope", "Ref 1t"]
            if has_reference_four:
                time_headers.append("Ref 4t")
            print("  Times (median, ms)")
            cls._print_performance_table([*time_headers, "Candidate 1t", "Candidate 4t"], time_rows)
            print("  Speedups (paired median) [95% confidence interval]")
            cls._print_performance_table(
                ["Workload", "Scope", "1t vs ref", "4t vs ref", "Scaling 1t -> 4t"], ratio_rows)
            for line in reference_scaling:
                print(line)
            reference = "upstream at matching thread count" if has_reference_four else "serial (1 thread)"
            print(f"  t = threads; ref = {reference}; >1 is better; ? = inconclusive.")
            if not calibration.get("target_reached", True):
                print("  Note: performance workload hit its size cap before the calibration time target.")
            probe = report.get("runtime_probe_threads", {})
            if probe and probe != {"1": 1, "4": 4}:
                print(f"  Runtime probe: {probe}")
            details = result.get("files", {}).get("evaluation")
            if details:
                path = Path(details)
                try:
                    path = path.relative_to(Path.cwd())
                except ValueError:
                    pass
                print(f"  Full precision, samples and build details: {path}")
            else:
                print("  Full precision, samples and build details are saved in evaluation.json.")
            return

        cls._print_performance_metric(report)

    @staticmethod
    def _print_performance_table(headers: list[str], rows: list[list[str]]) -> None:
        widths = [max(len(header), *(len(row[index]) for row in rows))
                  for index, header in enumerate(headers)] if rows else list(map(len, headers))
        for index, row in enumerate([headers, *rows]):
            print("  " + "  ".join(value.ljust(width) if column < 2 or index == 0 else value.rjust(width)
                                    for column, (value, width) in enumerate(zip(row, widths))).rstrip())

    @staticmethod
    def _format_speedup(comparison: dict[str, Any]) -> str:
        ratio = comparison.get("ratio")
        if not isinstance(ratio, (int, float)):
            return "-"
        interval = comparison.get("confidence_interval_95")
        uncertain = comparison.get("evidence") == "inconclusive"
        if isinstance(interval, list) and len(interval) == 2:
            uncertain = uncertain or interval[0] <= 1 <= interval[1]
            bounds = f" [{interval[0]:.3f},{interval[1]:.3f}]"
        else:
            bounds = ""
        return f"{ratio:.3f}{'?' if uncertain else ''}{bounds}"

    @staticmethod
    def _print_performance_metric(report: dict[str, Any]) -> None:
        metric = report.get("metric")
        unit = report.get("unit")
        if metric or unit:
            print(f"  Metric: {metric or 'unspecified'} ({unit or 'unspecified unit'})")

        measurements = report.get("measurements")
        if isinstance(measurements, list):
            for measurement in measurements:
                if not isinstance(measurement, dict):
                    continue
                label = measurement.get("label", "unnamed measurement")
                median = measurement.get("median")
                workers = measurement.get("workers")
                if isinstance(median, (int, float)) and unit == "seconds":
                    detail = f"median={median * 1000:.6g} ms"
                else:
                    detail = f"median={median}"
                if workers is not None:
                    detail += f", workers={workers}"
                print(f"  Measurement {label}: {detail}")

        comparisons = report.get("comparisons")
        if isinstance(comparisons, list):
            for comparison in comparisons:
                if not isinstance(comparison, dict):
                    continue
                label = comparison.get("label", "unnamed comparison")
                direction = comparison.get("direction", "unspecified direction")
                print(f"  Comparison {label}: {BenchmarkRunner._format_speedup(comparison)} ({direction})")

    @staticmethod
    def _build_remediation_prompt(
        case: BenchmarkCase,
        evaluation: dict[str, Any],
        turn_number: int,
    ) -> str:
        """Give the agent the evaluator's complete captured output."""
        diagnostics = BenchmarkRunner._full_evaluation_output(evaluation)
        return f"""You are repairing your previous attempt in {case.workspace}.

Original task: {case.task}

The benchmark's independent evaluator reports:
```text
{diagnostics}
```

Fix the actual cause in the existing workspace. Preserve valid changes already made;
do not restart the task. Treat every reported structural condition as an invariant:
inspect your diff before editing again, restore any removed parallel work or other
required structure, and do not trade correctness for serialization. Tests remain
unavailable to you. Make the smallest necessary source change, then run
`{case.build_command}`. This is continuation turn {turn_number}.
"""

    @staticmethod
    def _full_evaluation_output(evaluation: dict[str, Any]) -> str:
        """Return unfiltered stdout and stderr from every evaluator command."""
        sections: list[str] = []
        for label, result in (
            ("Build", evaluation.get("build")),
            ("Test", evaluation.get("tests")),
            ("Validator", evaluation.get("validator")),
        ):
            if not isinstance(result, dict):
                continue
            sections.extend(
                (
                    f"{label} stdout:",
                    str(result.get("stdout", "")),
                    f"{label} stderr:",
                    str(result.get("stderr", "")),
                )
            )

        return "\n".join(sections) if sections else "The evaluator produced no command output."

    @staticmethod
    def _print_evaluation_output(evaluation: dict[str, Any]) -> None:
        """Print hidden-test diagnostics without dumping build or profiler logs."""
        print(
            "[Benchmark] Evaluation status: "
            f"{evaluation.get('status', 'unknown')}"
        )

        for label, result in (
            ("Test", evaluation.get("tests")),
            ("Validator", evaluation.get("validator")),
        ):
            if not isinstance(result, dict):
                continue

            stdout = str(result.get("stdout", "")).strip()
            stderr = str(result.get("stderr", "")).strip()
            if not stdout and not stderr:
                continue

            print()
            print(f"[Benchmark] {label} output:")
            if stdout:
                print(stdout)
            if stderr:
                print(stderr)

    # ==================================================================
    # PROMPT
    # ==================================================================

    def _build_prompt(
        self,
        case: BenchmarkCase,
        mode: str,
    ) -> str:

        if mode == "direct":
            return self.prompts.build_direct(
                case
            )

        if mode == "full_discopop":
            return self.prompts.build_full_discopop(
                case
            )

        if mode == "mcp":
            return self.prompts.build_mcp(
                case
            )

        if mode == "force_mcp":
            return self.prompts.build_force_mcp(
                case
            )

        raise ValueError(
            f"Unknown benchmark mode: {mode}"
        )

    # ==================================================================
    # WORKSPACE
    # ==================================================================

    @staticmethod
    def _prepare_workspace(
        source: Path,
        destination: Path,
    ) -> None:

        source = Path(source).resolve()
        destination = Path(destination).resolve()

        if not source.is_dir():
            raise FileNotFoundError(
                "Benchmark repository does not exist: "
                f"{source}"
            )

        if destination.exists():
            shutil.rmtree(
                destination
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns(
                "build",
                "tests",
                ".discopop",
                ".git",
                "__pycache__",
                "*.pyc",
            ),
        )

    def _evaluate_hidden_tests(
        self,
        source: Path,
        agent_workspace: Path,
        evaluation_workspace: Path,
        case: BenchmarkCase,
    ) -> dict[str, Any]:
        """Evaluate a copy of the agent's work with hidden tests restored only there."""
        if evaluation_workspace.exists():
            shutil.rmtree(evaluation_workspace)
        shutil.copytree(
            agent_workspace,
            evaluation_workspace,
            ignore=shutil.ignore_patterns("build", ".discopop", ".git", "__pycache__", "*.pyc"),
        )

        source_tests = source / "tests"
        if source_tests.is_dir():
            shutil.copytree(source_tests, evaluation_workspace / "tests")

        reference_workspace = None
        if case.performance_command:
            reference_workspace = evaluation_workspace.parent / "reference_workspace"
            if reference_workspace.exists():
                shutil.rmtree(reference_workspace)
            shutil.copytree(
                source,
                reference_workspace,
                ignore=shutil.ignore_patterns(
                    "build", "tests", ".discopop", ".git", "__pycache__", "*.pyc"
                ),
            )

        evaluation_case = self._case_with_workspace(case, evaluation_workspace)
        return self.evaluator.evaluate(
            case=evaluation_case,
            workspace=evaluation_workspace,
            reference_workspace=reference_workspace,
        )

    @staticmethod
    def _case_with_workspace(
        case: BenchmarkCase,
        workspace: Path,
    ) -> BenchmarkCase:

        values: dict[str, Any] = {
            "index": case.index,
            "repository": case.repository,
            "name": case.name,
            "workspace": workspace,
            "task": case.task,
            "build_command": case.build_command,
            "test_command": case.test_command,
            "profiling_command": case.profiling_command,
            "language": case.language,
            "validator": case.validator,
            "performance_command": case.performance_command,
        }
        # Keep this runner compatible with case definitions created before
        # profiling_timeout_seconds was introduced.
        if hasattr(case, "profiling_timeout_seconds"):
            values["profiling_timeout_seconds"] = case.profiling_timeout_seconds
        return BenchmarkCase(**values)

    # ==================================================================
    # PATCH
    # ==================================================================

    @staticmethod
    def _create_patch(
        source: Path,
        modified: Path,
        output: Path,
    ) -> None:
        """
        Create a unified diff between the original benchmark case
        and the modified OpenCode workspace.

        This does not require the benchmark repository itself to be
        a Git repository.
        """

        source = Path(source).resolve()
        modified = Path(modified).resolve()
        output = Path(output).resolve()

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            process = subprocess.run(
                [
                    "diff",
                    "-ruN",
                    "--exclude=build",
                    "--exclude=tests",
                    "--exclude=.discopop",
                    "--exclude=.git",
                    "--exclude=__pycache__",
                    str(source),
                    str(modified),
                ],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=30,
            )

            # diff returns:
            #
            # 0 = identical
            # 1 = differences found
            # 2 = error
            #
            if process.returncode in {
                0,
                1,
            }:
                output.write_text(
                    process.stdout,
                    encoding="utf-8",
                )
                return

            output.write_text(
                (
                    "Could not create patch.\n\n"
                    f"stderr:\n{process.stderr}"
                ),
                encoding="utf-8",
            )

        except (
            OSError,
            subprocess.SubprocessError,
        ) as exc:

            output.write_text(
                (
                    "Could not create patch.\n\n"
                    f"{exc}"
                ),
                encoding="utf-8",
            )

    # ==================================================================
    # JSON
    # ==================================================================

    @staticmethod
    def _write_json(
        path: Path,
        data: Any,
    ) -> None:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from datetime import datetime

from benchmark.case import BenchmarkCase
from benchmark.evaluator import BenchmarkEvaluator
from benchmark.prompt import TaskPromptBuilder
from discopop.runner import DiscoPoPRunner
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
    """

    MODES = (
        "direct",
        "full_discopop",
        "mcp",
    )

    # The first agent turn is deliberately autonomous.  A coding agent can still
    # stop after making an edit that fails the final, external evaluation, though.
    # Give it the evaluator's concrete compiler/test diagnostics and a bounded
    # opportunity to repair its own work before recording the mode as failed.
    MAX_SESSION_TURNS = 5

    def __init__(
        self,
        llm_client: OpenCodeClient,
        output_root: Path,
    ):
        """
        Parameters
        ----------
        llm_client:
            Despite the historical variable name, this must be an
            OpenCodeClient.

        output_root:
            Directory in which benchmark results are stored.
        """

        if not isinstance(llm_client, OpenCodeClient):
            raise TypeError(
                "BenchmarkRunner requires an OpenCodeClient. "
                "Do not pass LLMClient here."
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
        print("=" * 100)
        print("BENCHMARK RESULTS")
        print("=" * 100)

        print(
            f"{'Mode':<20}"
            f"{'Input token':>15}"
            f"{'Output token':>15}"
            f"{'Total token':>15}"
            f"{'Accuracy':>12}"
            f"{'Latency':>12}"
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

            # ----------------------------------------------------------
            # Print row
            # ----------------------------------------------------------

            display_mode = "mcp" if mode == "mcp" else mode

            if mode == "mcp":
                print(f"{display_mode:<20}")
                display_mode = "  mcp (cold)"

            print(
                f"{display_mode:<20}"
                f"{input_tokens:>15,}"
                f"{output_tokens:>15,}"
                f"{total_tokens:>15,}"
                f"{accuracy:>12}"
                f"{latency_text:>12}"
            )

            if mode == "mcp":
                warm_tokens = tokens.get("warm", {})
                if warm_tokens:
                    warm_latency = warm_tokens.get("latency_seconds")
                    warm_latency_text = (
                        f"{warm_latency:.3f}s"
                        if isinstance(warm_latency, (int, float))
                        else "N/A"
                    )

                    print(
                        f"{'  mcp (warm)':<20}"
                        f"{warm_tokens.get('input', 0):>15,}"
                        f"{warm_tokens.get('output', 0):>15,}"
                        f"{warm_tokens.get('total', 0):>15,}"
                        f"{accuracy:>12}"
                        f"{warm_latency_text:>12}"
                    )

        print("=" * 100)

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
        # MCP:
        #     Run DiscoPoP because the MCP server needs the analysis.
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

                return {
                    "mode": mode,
                    "case": case.name,
                    "success": False,
                    "status": "discopop_failed",
                    "workspace": str(workspace),
                    "discopop": discopop_result,
                }

        elif mode == "mcp":

            print()
            print(
                "[Benchmark] DiscoPoP will be initialized "
                "and executed through MCP by OpenCode."
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
        #
        # This guarantees that only the MCP benchmark condition has
        # access to the DiscoPoP MCP server.
        # --------------------------------------------------------------

        mcp_enabled = (
            mode == "mcp"
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
            "[Benchmark] Starting OpenCode..."
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
                previous_evaluation=(
                    attempts[-1].get("evaluation")
                    if len(attempts) > 1
                    else None
                ),
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

        warm_usage, warm_latency = self._merge_session_warm_usage(
            attempts=attempts,
            mcp_enabled=mcp_enabled,
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

                "warm": (
                    {
                        "steps": warm_usage.get("steps", 0),
                        "input": warm_usage.get("input_tokens", 0),
                        "output": warm_usage.get("output_tokens", 0),
                        "total": warm_usage.get("total_tokens", 0),
                        "last_step": {
                            "input": warm_usage.get(
                                "last_step_input_tokens", 0
                            ),
                            "output": warm_usage.get(
                                "last_step_output_tokens", 0
                            ),
                            "total": warm_usage.get(
                                "last_step_total_tokens", 0
                            ),
                        },
                        "latency_seconds": warm_latency,
                    }
                    if isinstance(warm_usage, dict)
                    else {}
                ),
            },

            "mcp": {
                "enabled": mcp_enabled,

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
        return result

    @staticmethod
    def _result_warm_latency(llm_result: dict[str, Any]) -> float:
        value = llm_result.get("warm_latency_seconds")
        return float(value) if isinstance(value, (int, float)) else 0.0

    @classmethod
    def _merge_session_warm_usage(
        cls,
        attempts: list[dict[str, Any]],
        mcp_enabled: bool,
    ) -> tuple[dict[str, int] | None, float]:
        """Aggregate usage after MCP setup across a continued OpenCode session.

        ``OpenCodeClient.run`` can identify the exact step after setup only in
        the invocation that performs setup.  A continuation has no setup event,
        so it does not return ``warm_usage`` even though it resumes the already
        warm OpenCode session.  Once the first warm segment is found, every
        following agent invocation belongs to the warm measurement.
        """
        if not mcp_enabled:
            return None, 0.0

        warm_usages: list[dict[str, Any]] = []
        warm_latency = 0.0
        session_is_warm = False

        for attempt in attempts:
            llm_result = attempt.get("llm_result", {})
            if not isinstance(llm_result, dict):
                continue

            invocation_warm_usage = llm_result.get("warm_usage")
            if not session_is_warm and isinstance(invocation_warm_usage, dict):
                warm_usages.append(invocation_warm_usage)
                warm_latency += cls._result_warm_latency(llm_result)
                session_is_warm = True
            elif session_is_warm:
                # This invocation is a continuation of the warm session.  Its
                # entire usage occurred after the initial MCP setup boundary.
                usage = llm_result.get("usage")
                if isinstance(usage, dict):
                    warm_usages.append(usage)
                    latency = attempt.get("latency_seconds")
                    if isinstance(latency, (int, float)):
                        warm_latency += float(latency)

        return (
            cls._merge_usage(warm_usages) if warm_usages else None,
            warm_latency,
        )

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
    def _build_remediation_prompt(
        case: BenchmarkCase,
        evaluation: dict[str, Any],
        previous_evaluation: dict[str, Any] | None,
        turn_number: int,
    ) -> str:
        """Give the agent concise, non-repetitive evaluator diagnostics."""
        diagnostics = BenchmarkRunner._summarize_evaluation(
            evaluation=evaluation,
            previous_evaluation=previous_evaluation,
        )
        return f"""You are repairing your previous attempt in {case.workspace}.

Original task: {case.task}

The benchmark's independent evaluator reports:
```text
{diagnostics}
```

Fix the actual cause in the existing workspace. Preserve valid changes already made;
do not restart the task. Tests remain unavailable to you. Make the smallest necessary
source change, then run `{case.build_command}`. This is continuation turn {turn_number}.
"""

    @staticmethod
    def _summarize_evaluation(
        evaluation: dict[str, Any],
        previous_evaluation: dict[str, Any] | None,
    ) -> str:
        """Return actionable test/build status without exposing hidden tests."""
        status = evaluation.get("status", "unknown")
        lines = [f"Evaluator status: {status}."]

        build = evaluation.get("build")
        if isinstance(build, dict):
            if build.get("returncode") == 0:
                lines.append("Build: PASS")
            else:
                lines.append(f"Build: FAIL (exit {build.get('returncode')})")
                lines.extend(
                    BenchmarkRunner._diagnostic_lines(
                        build, limit=24, include_failures=False
                    )
                )

        tests = evaluation.get("tests")
        test_statuses = BenchmarkRunner._test_statuses(tests)
        if isinstance(tests, dict):
            if test_statuses:
                lines.append("Tests:")
                lines.extend(
                    f"  {name}: {result}"
                    for name, result in sorted(test_statuses.items())
                )
            elif tests.get("returncode") == 0:
                lines.append("Tests: PASS")
            else:
                lines.append(f"Tests: FAIL (exit {tests.get('returncode')})")
            lines.extend(
                BenchmarkRunner._diagnostic_lines(
                    tests, limit=12, include_failures=True
                )
            )

        previous_statuses = BenchmarkRunner._test_statuses(
            previous_evaluation.get("tests")
            if isinstance(previous_evaluation, dict)
            else None
        )
        if previous_evaluation:
            changes = [
                f"  {name}: {previous_statuses.get(name, 'not reported')} -> {result}"
                for name, result in sorted(test_statuses.items())
                if previous_statuses.get(name) != result
            ]
            if changes:
                lines.append("Changes since the preceding evaluation:")
                lines.extend(changes)
            elif status == previous_evaluation.get("status"):
                lines.append("Changes since the preceding evaluation: no test-status change.")

        passed = {name for name, result in test_statuses.items() if result == "PASS"}
        failed = {name for name, result in test_statuses.items() if result == "FAIL"}
        if passed and failed and all("sequential" in name for name in passed) and all(
            "parallel" in name for name in failed
        ):
            lines.append(
                "Diagnostic focus: sequential workloads pass while parallel workloads fail; "
                "inspect code paths that share state across OpenMP threads."
            )

        return "\n".join(lines)

    @staticmethod
    def _test_statuses(result: Any) -> dict[str, str]:
        if not isinstance(result, dict):
            return {}
        statuses: dict[str, str] = {}
        output = "\n".join(
            str(result.get(stream, "")) for stream in ("stdout", "stderr")
        )
        for line in output.splitlines():
            match = re.match(r"\[(PASS|FAIL)\]\s+(.+?)\s*$", line.strip())
            if match:
                statuses[match.group(2)] = match.group(1)
        return statuses

    @staticmethod
    def _diagnostic_lines(
        result: dict[str, Any],
        limit: int,
        include_failures: bool,
    ) -> list[str]:
        """Keep compiler/test failure signals, never build command noise or test data."""
        patterns = ("error:", "fatal:", "undefined reference", "exception")
        if include_failures:
            patterns += ("[fail]", "test(s) failed", "assertion failed")
        matches = [
            line.strip()
            for stream in ("stderr", "stdout")
            for line in str(result.get(stream, "")).splitlines()
            if any(pattern in line.lower() for pattern in patterns)
        ]
        return [f"  {line}" for line in matches[-limit:]]

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

        evaluation_case = self._case_with_workspace(case, evaluation_workspace)
        return self.evaluator.evaluate(
            case=evaluation_case,
            workspace=evaluation_workspace,
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
            "validator": case.validator,
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

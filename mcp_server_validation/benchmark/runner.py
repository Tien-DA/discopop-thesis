from __future__ import annotations

import json
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

            print(
                f"{mode:<20}"
                f"{input_tokens:>15,}"
                f"{output_tokens:>15,}"
                f"{total_tokens:>15,}"
                f"{accuracy:>12}"
                f"{latency_text:>12}"
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

        evaluation = self.evaluator.evaluate(
            case=isolated_case,
            workspace=workspace,
        )

        self._write_json(
            mode_output / "evaluation.json",
            evaluation,
        )

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

        usage = llm_result.get(
            "usage",
            {},
        )

        mcp_usage = llm_result.get(
            "mcp_usage",
            {},
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
                    mode_output
                    / "evaluation.json"
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
            "[Benchmark] {mode}: "
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

        if mcp_enabled:

            print(
                f"[Benchmark] MCP calls: "
                f"{result['mcp']['tool_calls']}"
            )

            tools = result["mcp"]["tools"]

            if tools:
                print(
                    "[Benchmark] MCP tools:"
                )

                for tool_name, count in tools.items():
                    print(
                        f"  - {tool_name}: {count}"
                    )

        return result

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
                ".discopop",
                ".git",
                "__pycache__",
                "*.pyc",
            ),
        )

    @staticmethod
    def _case_with_workspace(
        case: BenchmarkCase,
        workspace: Path,
    ) -> BenchmarkCase:

        return BenchmarkCase(
            index=case.index,
            repository=case.repository,
            name=case.name,
            workspace=workspace,
            task=case.task,
            build_command=case.build_command,
            test_command=case.test_command,
            profiling_command=case.profiling_command,
            validator=case.validator,
        )

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

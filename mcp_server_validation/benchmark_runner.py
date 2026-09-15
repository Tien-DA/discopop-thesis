import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from llm_client import LLMClient
from benchmark.repository_manager import RepositoryManager
from benchmark.swebench_loader import SWEBenchLoader
from benchmark.task_prompt import TaskPromptBuilder
from opencode_client import OpenCodeClient
from benchmark.evaluators.swebench import SWEBenchEvaluator

from benchmark.build_detector import BuildSystemDetector
from benchmark.discopop_runner import DiscoPoPRunner


class BenchmarkRunner:

    MODES = (
        #"direct",
        "full_discopop",
        #"mcp",
    )

    def __init__(self, llm_client):

        self.llm_client = llm_client

        self.opencode_client = OpenCodeClient(
            model=(
                "HPC_Lab/"
                "Qwen/Qwen3-Coder-30B-A3B-Instruct"
            ),
        )

        self.loader = SWEBenchLoader()
        self.repository_manager = RepositoryManager()
        self.prompt_builder = TaskPromptBuilder()
        self.swebench_evaluator = SWEBenchEvaluator()

        self.build_detector = BuildSystemDetector()

        self.discopop_runner = DiscoPoPRunner(
            timeout=600
        )

        self.runs_root = Path("runs")

        self.current_case_dir = None
        self.results = {}

    # ============================================================
    # CASE
    # ============================================================

    def create_case_directory(self, case):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        case_dir = (
            self.runs_root
            / f"{timestamp}_{case.instance_id}"
        )

        case_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        for mode in self.MODES:

            (case_dir / mode / "predictions").mkdir(
                parents=True
            )

            (
                case_dir
                / mode
                / "evaluation_reports"
            ).mkdir()

            (
                case_dir
                / mode
                / "logs"
            ).mkdir()

        return case_dir

    def run_case(self, case_index):

        case = self.loader.get_case(
            case_index
        )

        case_dir = self.create_case_directory(
            case
        )

        self.current_case_dir = case_dir

        print()
        print("=" * 80)
        print("                    BENCHMARK CASE")
        print("=" * 80)
        print(f"Instance:   {case.instance_id}")
        print(f"Repository: {case.repo}")
        print(f"Commit:     {case.base_commit}")
        print(f"Dataset:    {case.metadata.get('dataset')}")
        print(f"Split:      {case.metadata.get('split')}")
        print(f"Run dir:    {case_dir}")
        print("=" * 80)

        results = {}

        for mode in self.MODES:

            print()
            print("=" * 80)
            print(f"                    MODE: {mode.upper()}")
            print("=" * 80)

            results[mode] = self._run_mode(
                case=case,
                mode=mode,
                case_dir=case_dir,
            )

        self.results = {
            "instance_id": case.instance_id,
            "repository": case.repo,
            "base_commit": case.base_commit,
            "dataset": case.metadata.get("dataset"),
            "split": case.metadata.get("split"),
            "run_dir": str(case_dir),
            "results": results,
        }

        self.save_results(
            case_dir
        )

        self.print_summary(
            results
        )

        return self.results

    # ============================================================
    # MODE
    # ============================================================

    def _run_mode(
        self,
        case,
        mode,
        case_dir,
    ):

        mode_dir = (
            case_dir
            / mode
        )

        run_id = (
            f"{mode}-{case.instance_id}"
        )

        workspace = (
            Path(__file__).resolve().parent
            / ".workspaces"
            / case.instance_id
            / mode
        ).resolve()

        if workspace.exists():

            print(
                f"Cleaning existing workspace: "
                f"{workspace}"
            )

            shutil.rmtree(
                workspace
            )

        workspace.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        repo_url = (
            f"https://github.com/"
            f"{case.repo}.git"
        )

        print(
            f"Workspace: {workspace}"
        )

        try:

            # ----------------------------------------------------
            # Clone
            # ----------------------------------------------------

            print()
            print("Cloning repository...")

            self.repository_manager._run(
                [
                    "git",
                    "clone",
                    "--no-checkout",
                    repo_url,
                    str(workspace),
                ]
            )

            print(
                "Checking out base commit..."
            )

            self.repository_manager._run(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "checkout",
                    "--detach",
                    case.base_commit,
                ]
            )

            print(
                "Initializing submodules..."
            )

            self.repository_manager.initialize_submodules(
                workspace
            )

            # ----------------------------------------------------
            # Dispatch
            # ----------------------------------------------------

            if mode == "direct":

                return self._run_direct_mode(
                    case=case,
                    workspace=workspace,
                    mode_dir=mode_dir,
                    run_id=run_id,
                )

            if mode == "full_discopop":

                return self._run_full_discopop_mode(
                    case=case,
                    workspace=workspace,
                    mode_dir=mode_dir,
                    run_id=run_id,
                )

            if mode == "mcp":

                return self._run_mcp_mode(
                    case=case,
                    workspace=workspace,
                    mode_dir=mode_dir,
                    run_id=run_id,
                )

            raise ValueError(
                f"Unknown benchmark mode: {mode}"
            )

        finally:

            # ----------------------------------------------------
            # IMPORTANT:
            # Remove temporary benchmark workspace
            # ----------------------------------------------------

            if workspace.exists():

                print()
                print(
                    f"Cleaning workspace: "
                    f"{workspace}"
                )

                shutil.rmtree(
                    workspace
                )

    # ============================================================
    # DIRECT
    # ============================================================

    def _run_direct_mode(
        self,
        case,
        workspace,
        mode_dir,
        run_id,
    ):

        print()
        print("[DIRECT]")
        print("DiscoPoP: OFF")
        print("MCP:      OFF")

        prompt = self.prompt_builder.build(
            case,
            workspace,
        )

        agent_result = self._run_opencode(
            prompt=prompt,
            workspace=workspace,
            mode_dir=mode_dir,
            mcp_enabled=False,
        )

        patch = (
            self.repository_manager.get_diff(
                workspace
            )
        )

        evaluation = (
            self.swebench_evaluator.evaluate(
                instance_id=case.instance_id,
                model_name=self.opencode_client.model,
                patch=patch,
                run_id=run_id,
                predictions_dir=(
                    mode_dir
                    / "predictions"
                ),
                reports_dir=(
                    mode_dir
                    / "evaluation_reports"
                ),
                dataset=case.metadata["dataset"],
                split=case.metadata["split"],
            )
        )

        return {
            "mode": "direct",
            "success": True,
            "repository_path": str(workspace),
            "usage": agent_result["usage"],
            "latency": agent_result["latency"],
            "output": agent_result["output"],
            "patch": patch,
            "evaluation": evaluation,
        }

    # ============================================================
    # FULL DISCOPOP
    # ============================================================
    @staticmethod
    def _tail_text(text, max_lines=40):
        if not text:
            return ""

        lines = text.splitlines()

        if len(lines) <= max_lines:
            return text

        omitted = len(lines) - max_lines

        return "\n".join(
            [
                f"... omitted {omitted} earlier lines ...",
                *lines[-max_lines:],
            ]
        )

    def _summarize_discopop_result(self, result, mode_dir):
        logs_dir = mode_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        compact = dict(result)
        success = compact.get("success", False)
        stage = compact.get("stage", "run")

        for stream_name in ("stdout", "stderr"):
            text = compact.pop(stream_name, "")

            if not text:
                continue

            log_path = logs_dir / f"discopop_{stage}_{stream_name}.log"
            log_path.write_text(text, encoding="utf-8")
            compact[f"{stream_name}_log"] = str(log_path)

            if not success:
                compact[f"{stream_name}_tail"] = self._tail_text(text)

        print()
        print("[DiscoPoP] Result summary:")
        print(f"  success:    {success}")
        print(
            f"  analysis_available: "
            f"{compact.get('analysis_available', False)}"
        )
        print(f"  stage:      {stage}")
        print(f"  returncode: {compact.get('returncode', 'N/A')}")
        print(f"  elapsed:    {compact.get('elapsed', 'N/A')}")

        for stream_name in ("stdout", "stderr"):
            log_key = f"{stream_name}_log"
            tail_key = f"{stream_name}_tail"

            if log_key in compact:
                print(f"  {stream_name} log: {compact[log_key]}")

            if compact.get(tail_key):
                print()
                print(f"[DiscoPoP] {stream_name} tail (fail):")
                print(compact[tail_key])

        return compact

    def _run_full_discopop_mode(
        self,
        case,
        workspace,
        mode_dir,
        run_id,
    ):

        print()
        print("[FULL DISCOPOP]")
        print("DiscoPoP: ON")
        print("MCP:      OFF")

        build_system = (
            self.build_detector.detect(
                workspace
            )
        )

        print(
            f"Detected build system: "
            f"{build_system}"
        )

        if build_system is None:

            return {
                "mode": "full_discopop",
                "success": False,
                "reason": (
                    "Unsupported build system"
                ),
                "build_system": None,
            }

        print(
            "Preparing DiscoPoP build scripts..."
        )

        self.build_detector.prepare_scripts(
            repository=workspace,
            build_system=build_system,
        )

        print(
            "Running DiscoPoP..."
        )

        discopop_result = self.discopop_runner.run(workspace)

        discopop_result = self._summarize_discopop_result(
            result=discopop_result,
            mode_dir=mode_dir,
        )

        if not discopop_result.get(
                "analysis_available",
                False,
        ):
            return {
                "mode": "full_discopop",
                "success": False,
                "build_system": build_system,
                "discopop": discopop_result,
                "reason": "DiscoPoP profiler output is not available.",
            }

        discopop_path = workspace / ".discopop"

        prompt = self.prompt_builder.build_full_discopop_prompt(
            case=case,
            repository_path=workspace,
            discopop_path=discopop_path,
        )

        agent_result = self._run_opencode(
            prompt=prompt,
            workspace=workspace,
            mode_dir=mode_dir,
            mcp_enabled=False,
        )

        patch = (
            self.repository_manager.get_diff(
                workspace
            )
        )

        evaluation = (
            self.swebench_evaluator.evaluate(
                instance_id=case.instance_id,
                model_name=self.opencode_client.model,
                patch=patch,
                run_id=run_id,
                predictions_dir=(
                    mode_dir
                    / "predictions"
                ),
                reports_dir=(
                    mode_dir
                    / "evaluation_reports"
                ),
                dataset=case.metadata["dataset"],
                split=case.metadata["split"],
            )
        )

        return {
            "mode": "full_discopop",
            "success": True,
            "build_system": build_system,
            "discopop": discopop_result,
            "repository_path": str(workspace),
            "usage": agent_result["usage"],
            "latency": agent_result["latency"],
            "output": agent_result["output"],
            "patch": patch,
            "evaluation": evaluation,
        }

    # ============================================================
    # MCP
    # ============================================================

    def _run_mcp_mode(
        self,
        case,
        workspace,
        mode_dir,
        run_id,
    ):

        print()
        print("[MCP]")
        print("DiscoPoP: via MCP")
        print("MCP:      ON")

        prompt = self.prompt_builder.build_mcp_prompt(
            case=case,
            repository_path=workspace,
        )

        agent_result = self._run_opencode(
            prompt=prompt,
            workspace=workspace,
            mode_dir=mode_dir,
            mcp_enabled=True,
        )

        mcp_usage = agent_result.get(
            "mcp_usage",
            {},
        )

        print()
        print("MCP usage:")
        print(
            f"  Tool calls: {mcp_usage.get('tool_calls', 0)}"
        )
        print(
            f"  Tools:      {mcp_usage.get('tools', [])}"
        )
        print(
            f"  Used:       {mcp_usage.get('used', False)}"
        )

        if not mcp_usage.get("used", False):
            return {
                "mode": "mcp",
                "success": False,
                "repository_path": str(workspace),
                "usage": agent_result["usage"],
                "latency": agent_result["latency"],
                "output": agent_result["output"],
                "mcp_usage": mcp_usage,
                "invocation_id": agent_result.get(
                    "invocation_id"
                ),
                "reason": (
                    "MCP mode completed without any observed "
                    "DiscoPoP MCP tool calls."
                ),
                "events_file": agent_result.get(
                    "events_file"
                ),
            }

        patch = (
            self.repository_manager.get_diff(
                workspace
            )
        )

        evaluation = (
            self.swebench_evaluator.evaluate(
                instance_id=case.instance_id,
                model_name=self.opencode_client.model,
                patch=patch,
                run_id=run_id,
                predictions_dir=(
                    mode_dir
                    / "predictions"
                ),
                reports_dir=(
                    mode_dir
                    / "evaluation_reports"
                ),
                dataset=case.metadata["dataset"],
                split=case.metadata["split"],
            )
        )

        return {
            "mode": "mcp",
            "success": True,
            "repository_path": str(workspace),
            "usage": agent_result["usage"],
            "latency": agent_result["latency"],
            "output": agent_result["output"],
            "patch": patch,
            "evaluation": evaluation,
            "mcp_usage": agent_result.get(
                "mcp_usage",
                {},
            ),
            "invocation_id": agent_result.get(
                "invocation_id"
            ),
        }

    # ============================================================
    # OPENCODE
    # ============================================================

    def _run_opencode(
        self,
        prompt,
        workspace,
        mode_dir,
        mcp_enabled,
    ):

        start_time = time.perf_counter()

        events_file = (
            mode_dir
            / "logs"
            / "opencode_events.jsonl"
        )

        result = self.opencode_client.run(
            prompt=prompt,
            workspace=workspace,
            mcp_enabled=mcp_enabled,
            events_file=events_file,
        )

        latency = (
            time.perf_counter()
            - start_time
        )

        return {
            "output": result["output"],
            "usage": result["usage"],
            "latency": round(
                latency,
                3,
            ),
            "mcp_enabled": mcp_enabled,
            "mcp_usage": result.get(
                "mcp_usage",
                {},
            ),
            "invocation_id": result.get(
                "invocation_id"
            ),
            "events_file": str(
                events_file
            ),
        }

    # ============================================================
    # SUMMARY
    # ============================================================

    @staticmethod
    def _accuracy(evaluation):

        if not evaluation:
            return "N/A"

        status = evaluation.get(
            "status"
        )

        if status == "resolved":
            return "100%"

        if status == "unresolved":
            return "0%"

        # Infrastructure/evaluator errors
        return "N/A"

    @staticmethod
    def _usage(result):

        usage = result.get(
            "usage",
            {},
        )

        return {
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
        }

    def print_summary(
        self,
        results,
    ):

        mcp_result = results.get("mcp", {})

        mcp_usage = mcp_result.get(
            "mcp_usage",
            {},
        )

        print(
            f"MCP tool calls: "
            f"{mcp_usage.get('tool_calls', 0)}"
        )

        print(
            f"MCP tools used: "
            f"{mcp_usage.get('tools', [])}"
        )

        print()
        print("=" * 100)
        print("                         BENCHMARK RESULTS")
        print("=" * 100)

        header = (
            f"{'Mode':<18}"
            f"{'Input token':>15}"
            f"{'Output token':>15}"
            f"{'Total token':>15}"
            f"{'Accuracy':>12}"
            f"{'Latency':>12}"
        )

        print(header)
        print("-" * 100)

        for mode in self.MODES:

            result = results.get(
                mode,
                {},
            )

            usage = self._usage(
                result
            )

            accuracy = self._accuracy(
                result.get(
                    "evaluation",
                    {},
                )
            )

            latency = result.get(
                "latency"
            )

            latency_text = (
                f"{latency:.3f}s"
                if isinstance(
                    latency,
                    (int, float),
                )
                else "N/A"
            )

            print(
                f"{mode:<18}"
                f"{usage['input']:>15,}"
                f"{usage['output']:>15,}"
                f"{usage['total']:>15,}"
                f"{accuracy:>12}"
                f"{latency_text:>12}"
            )

        print("=" * 100)

    # ============================================================
    # SAVE
    # ============================================================

    def save_results(
        self,
        run_dir,
    ):

        result_file = (
            run_dir
            / "result.json"
        )

        with result_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                self.results,
                file,
                indent=2,
                ensure_ascii=False,
            )

        print()
        print(
            f"Results saved to: "
            f"{result_file}"
        )

        return result_file


# ================================================================
# MAIN
# ================================================================

def main():

    llm_client = LLMClient()

    api_key = "ppkitestapikey"

    connected = llm_client.connect(
        server_url=(
            "http://localhost:18000/v1"
        ),
        api_key=api_key,
        model=(
            "Qwen/Qwen3-Coder-30B-A3B-Instruct"
        ),
    )

    if not connected:

        print(
            "Could not connect to LLM server."
        )

        return

    runner = BenchmarkRunner(
        llm_client
    )

    # ------------------------------------------------------------
    # ONE CASE = ALL THREE MODES
    # ------------------------------------------------------------

    runner.run_case(
        case_index=135
    )


if __name__ == "__main__":
    main()

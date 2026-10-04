from __future__ import annotations

import os
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from benchmark.case import BenchmarkCase
from benchmark.runner import BenchmarkRunner


class BatchBenchmarkRunner:
    """Run all cases while keeping console output to result summaries."""

    def __init__(self, runner: BenchmarkRunner) -> None:
        self.runner = runner

    def run_all(self, cases: list[BenchmarkCase]) -> None:
        all_results: list[tuple[BenchmarkCase, dict[str, Any]]] = []

        for position, case in enumerate(cases, start=1):
            print()
            print("=" * 100)
            print(f"TASK {position}/{len(cases)}: {case.repository} / {case.name}")
            print("=" * 100)

            # run_case already contains the established benchmark flow.
            # Suppress its detailed per-mode logs for batch execution only.
            with Path(os.devnull).open("w", encoding="utf-8") as devnull:
                with redirect_stdout(devnull):
                    results = self.runner.run_case(case)

            all_results.append((case, results))
            self._print_results(results)

        self._print_averages(all_results)

    @staticmethod
    def _accuracy(result: dict[str, Any]) -> str:
        if result.get("status") in {"discopop_failed", "runner_failed"}:
            return "N/A"
        return "PASS" if result.get("success", False) else "FAIL"

    @staticmethod
    def _latency_text(latency: Any) -> str:
        return f"{latency:.3f}s" if isinstance(latency, (int, float)) else "N/A"

    def _print_results(self, results: dict[str, Any]) -> None:
        print()
        print("BENCHMARK RESULTS")
        print("-" * 100)
        print(
            f"{'Mode':<20}{'Input token':>15}{'Output token':>15}"
            f"{'Total token':>15}{'Accuracy':>12}{'Latency':>12}"
        )

        for mode in self.runner.MODES:
            result = results.get(mode, {})
            tokens = result.get("tokens", {})
            accuracy = self._accuracy(result)

            if mode == "mcp":
                print("mcp")
                self._print_row(
                    "  mcp (cold)",
                    tokens,
                    accuracy,
                    result.get("latency_seconds"),
                )
                warm = tokens.get("warm", {})
                if warm:
                    self._print_row(
                        "  mcp (warm)",
                        warm,
                        accuracy,
                        warm.get("latency_seconds"),
                    )

                tools = result.get("mcp", {}).get("tools", {})
                if tools:
                    print("  MCP functions:")
                    for tool_name, count in tools.items():
                        print(f"    {tool_name}: {count}")
                else:
                    print("  MCP functions: none")
            else:
                self._print_row(
                    mode,
                    tokens,
                    accuracy,
                    result.get("latency_seconds"),
                )

        print("-" * 100)

    def _print_row(
        self,
        label: str,
        tokens: dict[str, Any],
        accuracy: str,
        latency: Any,
    ) -> None:
        print(
            f"{label:<20}"
            f"{tokens.get('input', 0):>15,}"
            f"{tokens.get('output', 0):>15,}"
            f"{tokens.get('total', 0):>15,}"
            f"{accuracy:>12}"
            f"{self._latency_text(latency):>12}"
        )

    def _print_averages(
        self,
        all_results: list[tuple[BenchmarkCase, dict[str, Any]]],
    ) -> None:
        print()
        print("=" * 100)
        print("BENCHMARK AVERAGES")
        print("=" * 100)
        print(
            f"{'Mode':<20}{'Input token':>15}{'Output token':>15}"
            f"{'Total token':>15}{'Accuracy':>12}{'Latency':>12}"
        )

        for mode in self.runner.MODES:
            if mode == "mcp":
                print("mcp")
                self._print_average_row("  mcp (cold)", all_results, mode)
                self._print_average_row("  mcp (warm)", all_results, mode, warm=True)
            else:
                self._print_average_row(mode, all_results, mode)

        print("=" * 100)

    def _print_average_row(
        self,
        label: str,
        all_results: list[tuple[BenchmarkCase, dict[str, Any]]],
        mode: str,
        warm: bool = False,
    ) -> None:
        values: list[tuple[dict[str, Any], dict[str, Any]]] = []
        successes = 0

        for _, results in all_results:
            result = results.get(mode, {})
            tokens = result.get("tokens", {})
            if warm:
                tokens = tokens.get("warm", {})

            if not tokens:
                continue

            values.append((tokens, result))
            successes += bool(result.get("success", False))

        if not values:
            print(f"{label:<20}{'N/A':>15}{'N/A':>15}{'N/A':>15}{'N/A':>12}{'N/A':>12}")
            return

        count = len(values)
        avg_input = sum(item[0].get("input", 0) for item in values) / count
        avg_output = sum(item[0].get("output", 0) for item in values) / count
        avg_total = sum(item[0].get("total", 0) for item in values) / count
        latency_key = "latency_seconds"
        latencies = [
            item[0].get(latency_key) if warm else item[1].get(latency_key)
            for item in values
        ]
        valid_latencies = [value for value in latencies if isinstance(value, (int, float))]
        latency_text = (
            f"{sum(valid_latencies) / len(valid_latencies):.3f}s"
            if valid_latencies
            else "N/A"
        )
        accuracy = f"{successes}/{count}"

        print(
            f"{label:<20}{avg_input:>15,.0f}{avg_output:>15,.0f}"
            f"{avg_total:>15,.0f}{accuracy:>12}{latency_text:>12}"
        )

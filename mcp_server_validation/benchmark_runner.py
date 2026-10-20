from __future__ import annotations

import argparse
import os
from pathlib import Path

from benchmark.case import BenchmarkCase


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run DiscoPoP MCP benchmark cases.",
    )
    parser.add_argument(
        "--case",
        metavar="NAME",
        help="Run the case whose benchmark.json name is NAME without prompting.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List discovered cases and exit.",
    )
    parser.add_argument(
        "--reasoning-effort",
        "--variant",
        dest="reasoning_effort",
        choices=("xhigh", "high", "medium", "low", "off"),
        default=os.environ.get("BENCHMARK_REASONING_EFFORT", "medium"),
        help=(
            "OpenCode reasoning variant (default: %(default)s). "
            "Use low or off to reduce latency."
        ),
    )
    parser.epilog = (
        "Examples:\n"
        "  ./run --help\n"
        "  ./run --list\n"
        "  ./run --case drb009_lastprivate_missing --reasoning-effort low\n"
        "  ./run --case drb009_lastprivate_missing --variant off\n"
        "  ./run                 # select a case interactively"
    )
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    return parser.parse_args()


def _select_case_by_name(
    cases: list[BenchmarkCase],
    name: str,
) -> BenchmarkCase:
    for case in cases:
        if case.name == name:
            return case

    available = ", ".join(case.name for case in cases)
    raise ValueError(
        f"Unknown benchmark case {name!r}. Available cases: {available}"
    )


def main():

    args = _parse_args()

    # Keep ``./run --help`` usable before the optional DiscoPoP packages are
    # installed. The normal benchmark path imports them below.
    from benchmark.loader import BenchmarkLoader
    from benchmark.selector import BenchmarkSelector

    # ==============================================================
    # Paths
    # ==============================================================

    root = (
        Path(__file__)
        .resolve()
        .parent
    )

    workspaces = (
        root
        / ".workspaces"
    )

    output = (
        root
        / "runs"
    )

    # ==============================================================
    # Load benchmark cases
    # ==============================================================

    loader = BenchmarkLoader(
        workspaces
    )

    cases = loader.load_cases()

    print(
        f"\nDiscovered {len(cases)} benchmark task(s)."
    )

    if args.list:
        BenchmarkSelector.display(cases)
        return

    from benchmark.batch_runner import BatchBenchmarkRunner
    from benchmark.runner import BenchmarkRunner
    from llm.opencode import OpenCodeClient

    # ---------------------------------------------------------
    # Select task
    # ---------------------------------------------------------

    case = (
        _select_case_by_name(cases, args.case)
        if args.case
        else BenchmarkSelector.select(cases)
    )

    # ==============================================================
    # LLM configuration
    # ==============================================================

    server_url = os.environ.get(
        "BENCHMARK_LLM_SERVER_URL",
        "http://localhost:18000/v1",
    )

    api_key = os.environ.get(
        "BENCHMARK_LLM_API_KEY",
        "ppkitestapikey",
    )

    model = os.environ.get(
        "BENCHMARK_LLM_MODEL",
        "Qwen/Qwen3.8-27B",
    )

    print()
    print("LLM configuration:")
    print(
        f"  Server: {server_url}"
    )
    print(
        f"  Model:  {model}"
    )
    print(
        f"  Reasoning effort: {args.reasoning_effort}"
    )

    # ==============================================================
    # Create OpenCode client
    #
    # OpenCode is the actual coding agent used by the benchmark.
    # ==============================================================

    opencode = OpenCodeClient(
        model=model,
        server_url=server_url,
        api_key=api_key,
        reasoning_effort=args.reasoning_effort,
    )

    # ==============================================================
    # Create benchmark runner
    # ==============================================================

    runner = BenchmarkRunner(
        llm_client=opencode,
        output_root=output,
    )

    # ==============================================================
    # Run benchmark cases
    # ==============================================================
    if case is None:
        BatchBenchmarkRunner(runner).run_all(cases)
    else:
        runner.run_case(case)


if __name__ == "__main__":
    main()

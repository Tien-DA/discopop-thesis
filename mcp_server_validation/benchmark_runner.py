from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Union

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
        "--agent",
        choices=("opencode", "claude"),
        default=os.environ.get("BENCHMARK_AGENT", "opencode"),
        help=(
            "Coding agent CLI to benchmark (default: %(default)s). Both use "
            "the tool's own existing setup; for claude, 'xhigh' and 'max' "
            "are valid effort levels in addition to low, medium and high."
        ),
    )
    parser.add_argument(
        "--claude-model",
        default=os.environ.get("BENCHMARK_CLAUDE_MODEL"),
        metavar="MODEL",
        help=(
            "Model for --agent claude: an alias such as sonnet, opus or "
            "haiku, or a full model name. Default: the Claude Code default."
        ),
    )
    parser.add_argument(
        "--reasoning-effort",
        "--variant",
        dest="reasoning_effort",
        choices=("max", "xhigh", "high", "medium", "low", "off"),
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
        "  ./run --case DRB095-doall2-taskloop-orig-yes --reasoning-effort low\n"
        "  ./run --case DRB095-doall2-taskloop-orig-yes --variant off\n"
        "  ./run --agent claude --case DRB095-doall2-taskloop-orig-yes\n"
        "  ./run --agent claude --claude-model haiku --case DRB095-doall2-taskloop-orig-yes\n"
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
    from llm.claude_code import ClaudeCodeClient
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
    # Create the coding agent client
    #
    # The selected agent CLI is the actual coding agent used by the
    # benchmark. Both agents default to the user's own existing setup.
    # ==============================================================

    agent_client: Union[OpenCodeClient, ClaudeCodeClient]

    print()
    print(f"Agent: {args.agent}")

    if args.agent == "claude":
        agent_client = ClaudeCodeClient(
            model=args.claude_model,
            reasoning_effort=args.reasoning_effort,
        )
        print(
            f"  Model:  {agent_client.model or '(Claude Code default)'}"
        )
        print(
            f"  Reasoning effort: {args.reasoning_effort}"
        )
    else:
        # Unset means: use the provider from the user's own OpenCode setup.
        server_url = os.environ.get("BENCHMARK_LLM_SERVER_URL")

        api_key = os.environ.get("BENCHMARK_LLM_API_KEY")

        model = os.environ.get(
            "BENCHMARK_LLM_MODEL",
            "Qwen/Qwen3.8-27B",
        )

        print(
            f"  Server: {server_url or '(from OpenCode configuration)'}"
        )
        print(
            f"  Model:  {model}"
        )
        print(
            f"  Reasoning effort: {args.reasoning_effort}"
        )

        agent_client = OpenCodeClient(
            model=model,
            server_url=server_url,
            api_key=api_key,
            reasoning_effort=args.reasoning_effort,
        )

    # ==============================================================
    # Create benchmark runner
    # ==============================================================

    runner = BenchmarkRunner(
        llm_client=agent_client,
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

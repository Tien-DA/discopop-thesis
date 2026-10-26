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
        metavar="VARIANT",
        default=None,
        help=(
            "OpenCode model variant for this run, or Claude Code effort level. "
            "For OpenCode, 'off' selects the 'none' variant; omit this flag "
            "to reuse the variant saved for the last selected model."
        ),
    )
    parser.epilog = (
        "Examples:\n"
        "  ./run --help\n"
        "  ./run --list\n"
        "  ./run --reasoning-effort low --case DRB095-doall2-taskloop-orig-yes\n"
        "  ./run --agent claude --case DRB095-doall2-taskloop-orig-yes\n"
        "  ./run --agent claude --claude-model haiku --case DRB095-doall2-taskloop-orig-yes\n"
        "  ./run --agent claude --reasoning-effort low --case DRB095-doall2-taskloop-orig-yes\n"
        "  ./run                 # select a case interactively"
    )
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    args = parser.parse_args()
    if args.reasoning_effort is not None:
        if not args.reasoning_effort or any(character in args.reasoning_effort for character in "#\r\n"):
            parser.error("--reasoning-effort/--variant requires a variant name without '#' or newlines")
    if args.agent == "claude" and args.reasoning_effort is not None:
        if args.reasoning_effort not in {"max", "xhigh", "high", "medium", "low", "off"}:
            parser.error("Claude reasoning effort must be max, xhigh, high, medium, low, or off")
    return args


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
            f"  Reasoning effort: {agent_client.reasoning_effort}"
        )
    else:
        agent_client = OpenCodeClient(reasoning_effort=args.reasoning_effort)
        if args.reasoning_effort is not None:
            print(f"  Variant override: {args.reasoning_effort}")
        details = agent_client.describe_recent_selection(
            case.workspace if case is not None else root
        )
        print(f"  Provider: {details['provider']}")
        print(f"  Model: {details['model']}")
        print(f"  Variant: {details['variant']}")
        print(f"  Server: {details['server']}")
        print(f"  Credentials: {details['credentials']}")

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

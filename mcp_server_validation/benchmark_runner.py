from __future__ import annotations

from pathlib import Path

from benchmark.loader import BenchmarkLoader
from benchmark.runner import BenchmarkRunner
from llm.client import LLMClient
from llm.opencode import OpenCodeClient
from benchmark.selector import BenchmarkSelector


def main():

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

    # ---------------------------------------------------------
    # Select task
    # ---------------------------------------------------------

    case = BenchmarkSelector.select(cases)

    # ==============================================================
    # LLM configuration
    # ==============================================================

    server_url = (
        "http://localhost:18000/v1"
    )

    api_key = (
        "ppkitestapikey"
    )

    model = (
        "Qwen/Qwen3-Coder-30B-A3B-Instruct"
    )

    print()
    print("LLM configuration:")
    print(
        f"  Server: {server_url}"
    )
    print(
        f"  Model:  {model}"
    )

    # ==============================================================
    # Test LLM connection
    #
    # LLMClient is ONLY used for checking that the
    # OpenAI-compatible server is reachable.
    # ==============================================================

    llm = LLMClient()

    if not llm.connect(
        server_url=server_url,
        api_key=api_key,
        model=model,
    ):
        raise RuntimeError(
            "Could not connect to LLM server."
        )

    # ==============================================================
    # Create OpenCode client
    #
    # OpenCode is the actual coding agent used by the benchmark.
    # ==============================================================

    opencode = OpenCodeClient(
        model=model,
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
    runner.run_case(case)


if __name__ == "__main__":
    main()

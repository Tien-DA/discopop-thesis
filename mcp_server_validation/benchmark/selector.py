from __future__ import annotations

from typing import Optional

from benchmark.case import BenchmarkCase


class BenchmarkSelector:
    """
    Handles interactive benchmark task selection.
    """

    @staticmethod
    def display(cases: list[BenchmarkCase]) -> None:
        print()
        print("=" * 80)
        print("AVAILABLE BENCHMARK TASKS")
        print("=" * 80)

        if not cases:
            print("No benchmark tasks found.")
            return

        for case in cases:
            print(
                f"{case.index:>3}. "
                f"{case.repository:<35} "
                f"{case.name}"
            )

        print("  all. Run all benchmark tasks")

        print("=" * 80)

    @staticmethod
    def select(cases: list[BenchmarkCase]) -> Optional[BenchmarkCase]:
        """
        Display available cases and ask the user to select one.
        """

        if not cases:
            raise RuntimeError(
                "No benchmark tasks were found."
            )

        BenchmarkSelector.display(cases)

        while True:
            try:
                choice = input(
                    "\nSelect benchmark task "
                    f"[1-{len(cases)} or all]: "
                ).strip().lower()

            except EOFError:
                raise RuntimeError("No benchmark task was selected.") from None

            if choice == "all":
                return None

            try:
                index = int(choice)
            except ValueError:
                print("Please enter a valid number or 'all'.")
                continue

            if 1 <= index <= len(cases):
                selected = cases[index - 1]

                print()
                print("Selected benchmark:")
                print(f"  Index:      {selected.index}")
                print(f"  Repository: {selected.repository}")
                print(f"  Task:       {selected.name}")
                print(f"  Workspace:  {selected.workspace}")

                return selected

            print(
                f"Invalid selection. "
                f"Please choose a number between 1 and {len(cases)}, or 'all'."
            )

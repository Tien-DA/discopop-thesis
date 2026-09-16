from __future__ import annotations

import json
from pathlib import Path

from benchmark.case import BenchmarkCase


class BenchmarkLoader:
    """
    Discover benchmark tasks from:

        .workspaces/
            repository/
                task/
                    benchmark.json
                    CMakeLists.txt
                    main.cpp
    """

    REQUIRED_FILE = (
        "benchmark.json",
    )

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def load_cases(self) -> list[BenchmarkCase]:
        """
        Discover benchmark cases from:

            .workspaces/
                repository/
                    benchmark.json
                    ...

        or:

            .workspaces/
                repository/
                    task/
                        benchmark.json
                        ...
        """

        if not self.workspace_root.exists():
            raise FileNotFoundError(
                f"Workspace directory does not exist: "
                f"{self.workspace_root}"
            )

        cases: list[BenchmarkCase] = []

        repositories = sorted(
            path
            for path in self.workspace_root.iterdir()
            if path.is_dir()
        )

        for repository_path in repositories:

            # ---------------------------------------------------------
            # Repository itself is one benchmark task
            # ---------------------------------------------------------
            if self._has_required_file(repository_path):
                case = self._load_case(
                    index=len(cases) + 1,
                    repository_path=repository_path,
                    task_path=repository_path,
                )

                cases.append(case)
                continue

            # ---------------------------------------------------------
            # Repository contains multiple benchmark tasks
            # ---------------------------------------------------------
            task_directories = sorted(
                path
                for path in repository_path.iterdir()
                if path.is_dir()
            )

            for task_path in task_directories:
                if not self._is_valid_task(task_path):
                    continue

                case = self._load_case(
                    index=len(cases) + 1,
                    repository_path=repository_path,
                    task_path=task_path,
                )

                cases.append(case)

        return cases

    def _has_required_file(self, task_path: Path) -> bool:
        return all(
            (task_path / filename).is_file()
            for filename in self.REQUIRED_FILE
        )

    def _is_valid_task(self, task_path: Path) -> bool:
        missing = [
            filename
            for filename in self.REQUIRED_FILE
            if not (task_path / filename).is_file()
        ]

        if missing:
            print(
                f"[Loader] Skipping invalid task: "
                f"{task_path}"
            )
            print(
                f"[Loader] Missing: {', '.join(missing)}"
            )
            return False

        return True

    def _load_case(
        self,
        index: int,
        repository_path: Path,
        task_path: Path,
    ) -> BenchmarkCase:
        """
        Load benchmark metadata from benchmark.json.
        """

        benchmark_file = task_path / "benchmark.json"

        try:
            with benchmark_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in {benchmark_file}: {exc}"
            ) from exc

        name = (
            task_path.name
            if task_path != repository_path
            else "default"
        )

        return BenchmarkCase(
            index=index,
            repository=repository_path.name,
            name=name,
            workspace=task_path,
            task=data["task"],
            build_command=data["build_command"],
            test_command=data["test_command"],
            validator=data.get("validator"),
        )
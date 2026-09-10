from pathlib import Path

from benchmark.case import BenchmarkCase


class RepositoryContextBuilder:
    """
    Builds repository context that can be provided to the LLM.

    This component deliberately keeps repository context separate
    from task prompt construction.
    """

    def build(
        self,
        case: BenchmarkCase,
        workspace: Path,
    ) -> str:
        """
        Build a textual representation of the repository context.

        Args:
            case: Benchmark case.
            workspace: Local repository workspace.

        Returns:
            Repository context as a string.
        """

        files = self._collect_source_files(workspace)

        sections = []

        for file_path in files:
            relative_path = file_path.relative_to(workspace)

            try:
                content = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            except OSError:
                continue

            sections.append(
                f"===== {relative_path} =====\n"
                f"{content}"
            )

        return "\n\n".join(sections)

    def _collect_source_files(
        self,
        workspace: Path,
    ) -> list[Path]:
        """
        Collect source files from the repository.

        For the initial implementation, only common source-code
        extensions are included.
        """

        extensions = {
            ".py",
            ".c",
            ".h",
            ".cpp",
            ".cc",
            ".cxx",
            ".hpp",
            ".java",
            ".js",
            ".ts",
            ".go",
            ".rs",
        }

        files = []

        for path in workspace.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts:
                continue

            if path.suffix.lower() in extensions:
                files.append(path)

        return sorted(files)
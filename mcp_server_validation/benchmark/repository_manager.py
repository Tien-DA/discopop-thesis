import subprocess
from pathlib import Path

from benchmark.case import BenchmarkCase


class RepositoryManager:
    """Manage isolated repositories for benchmark cases."""

    def __init__(self, workspace_root: str = ".workspaces"):
        self.workspace_root = Path(workspace_root)

    def prepare(self, case: BenchmarkCase) -> Path:
        """
        Prepare a repository at the exact base commit of a benchmark case.

        Returns:
            Path to the prepared repository workspace.
        """
        workspace = self.workspace_root / case.instance_id

        workspace.parent.mkdir(parents=True, exist_ok=True)

        repo_url = f"https://github.com/{case.repo}.git"

        self._run(
            [
                "git",
                "clone",
                "--no-checkout",
                repo_url,
                str(workspace),
            ]
        )

        self._run(
            [
                "git",
                "-C",
                str(workspace),
                "checkout",
                "--detach",
                case.base_commit,
            ]
        )

        return workspace

    @staticmethod
    def _run(command: list[str]) -> None:
        """Run a command and raise an error if it fails."""
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed:\n"
                f"{' '.join(command)}\n\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )

    def get_diff(self, workspace: Path) -> str:
        """
        Return the current uncommitted changes as a unified git diff.
        """

        result = subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "diff",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Could not get git diff:\n"
                f"{result.stderr}"
            )

        return result.stdout
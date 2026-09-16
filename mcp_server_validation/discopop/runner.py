import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from benchmark.case import BenchmarkCase

from discopop_library.ProjectManager.ProjectManagerArguments import (
    ProjectManagerArguments,
)
from discopop_library.ProjectManager.configurations.execution import (
    execute_configuration,
)
from discopop_library.ProjectManager.utilities.deriveSettingsFiles import (
    derive_settings_files,
)


class DiscoPoPRunner:

    REQUIRED_PROFILER_FILES = (
        "Data.xml",
        "dynamic_dependencies.txt",
    )

    REQUIRED_ANALYSIS_FILES = (
        "Data.xml",
        "dynamic_dependencies.txt",
        "static_dependencies.txt",
        "ast_dump.json",
    )

    def __init__(self, timeout: int = 600):
        self.timeout = timeout

    def run(
        self,
        case: BenchmarkCase,
    ) -> dict[str, Any]:

        project = case.workspace.resolve()

        self._prepare_project(
            project,
            case,
        )

        configs_dir = (
            project
            / ".discopop"
            / "project"
            / "configs"
        )

        default_dir = configs_dir / "default"

        compile_script = configs_dir / "compile.sh"
        execute_script = default_dir / "execute.sh"

        settings = configs_dir / "dp_settings.json"

        arguments = self._create_arguments(
            project
        )

        # ------------------------------------------------------------
        # BUILD
        # ------------------------------------------------------------

        print()
        print("=" * 80)
        print(
            f"[DiscoPoP] Build: {case.name}"
        )
        print("=" * 80)

        result = execute_configuration(
            arguments=arguments,
            project_copy_root_path=str(project),
            config_path=str(configs_dir),
            settings_path=str(settings),
            script_path=str(compile_script),
            thread_count=1,
            timeout=float(self.timeout),
        )

        if result[0] != 0:
            failure = self._failure(
                "compile",
                result,
            )

            print()
            print("[DiscoPoP] Build failed")
            print(f"[DiscoPoP] Return code: {result[0]}")

            if result[2]:
                print()
                print("[DiscoPoP] STDOUT:")
                print(result[2])

            if result[3]:
                print()
                print("[DiscoPoP] STDERR:")
                print(result[3])

            return failure

        # ------------------------------------------------------------
        # EXECUTE
        # ------------------------------------------------------------

        print()
        print("=" * 80)
        print(
            f"[DiscoPoP] Execute: {case.name}"
        )
        print("=" * 80)

        result = execute_configuration(
            arguments=arguments,
            project_copy_root_path=str(project),
            config_path=str(default_dir),
            settings_path=str(settings),
            script_path=str(execute_script),
            thread_count=1,
            timeout=float(self.timeout),
        )

        if result[0] != 0:
            print()
            print("[DiscoPoP] Execute returned non-zero")
            print(f"[DiscoPoP] Return code: {result[0]}")

            if result[2]:
                print()
                print("[DiscoPoP] STDOUT:")
                print(result[2])

            if result[3]:
                print()
                print("[DiscoPoP] STDERR:")
                print(result[3])

            print()
            print("[DiscoPoP] Continuing because execution output may still be valid.")

        # ------------------------------------------------------------
        # PROFILER OUTPUT
        # ------------------------------------------------------------

        profiler = (
            project
            / ".discopop"
            / "profiler"
        )

        missing = self._missing(
            profiler,
            self.REQUIRED_PROFILER_FILES,
        )

        if missing:
            return {
                "success": False,
                "analysis_available": False,
                "stage": "profiling",
                "missing_artifacts": missing,
            }

        # ------------------------------------------------------------
        # EXPLORER
        # ------------------------------------------------------------

        explorer = self._run_explorer(
            project
        )

        if explorer.returncode != 0:
            return {
                "success": False,
                "analysis_available": False,
                "stage": "pattern_detection",
                "returncode": explorer.returncode,
                "stdout": explorer.stdout,
                "stderr": explorer.stderr,
            }

        # ------------------------------------------------------------
        # FINAL ARTIFACTS
        # ------------------------------------------------------------

        missing = self._missing(
            profiler,
            self.REQUIRED_ANALYSIS_FILES,
        )

        if missing:
            return {
                "success": False,
                "analysis_available": False,
                "stage": "analysis_validation",
                "missing_artifacts": missing,
            }

        return {
            "success": True,
            "analysis_available": True,
            "stage": "completed",
            "profiler": str(profiler),
            "profiler_files": self._files(profiler),
        }

    # ================================================================
    # PREPARATION
    # ================================================================

    def _prepare_project(
        self,
        project: Path,
        case: BenchmarkCase,
    ) -> None:

        configs = (
            project
            / ".discopop"
            / "project"
            / "configs"
        )

        default = configs / "default"

        default.mkdir(
            parents=True,
            exist_ok=True,
        )

        seq_settings = configs / "seq_settings.json"

        if not seq_settings.exists():
            seq_settings.write_text(
                """{
    "CC": "clang",
    "CXX": "clang++",
    "CFLAGS": "",
    "CXXFLAGS": ""
}
""",
                encoding="utf-8",
            )

        derive_settings_files(
            str(configs),
            overwrite=False,
        )

        self._write_compile_script(
            configs / "compile.sh",
            case.build_command,
        )

        self._write_execute_script(
            default / "execute.sh",
            case.test_command,
        )

    @staticmethod
    def _write_compile_script(
        path: Path,
        command: str,
    ) -> None:

        path.write_text(
            f"""#!/bin/bash
set -e

{command}
""",
            encoding="utf-8",
        )

        path.chmod(0o755)

    @staticmethod
    def _write_execute_script(
        path: Path,
        command: str,
    ) -> None:

        path.write_text(
            f"""#!/bin/bash
set -e

{command}
""",
            encoding="utf-8",
        )

        path.chmod(0o755)

    # ================================================================
    # EXPLORER
    # ================================================================

    def _run_explorer(
        self,
        project: Path,
    ) -> subprocess.CompletedProcess:

        env = os.environ.copy()

        venv_bin = str(
            Path(sys.executable).parent
        )

        env["PATH"] = (
            venv_bin
            + os.pathsep
            + env.get("PATH", "")
        )

        return subprocess.run(
            ["discopop_explorer"],
            cwd=project / ".discopop",
            env=env,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

    # ================================================================
    # HELPERS
    # ================================================================

    @staticmethod
    def _missing(
        directory: Path,
        files: tuple[str, ...],
    ) -> list[str]:

        return [
            name
            for name in files
            if not (directory / name).is_file()
        ]

    @staticmethod
    def _files(
        directory: Path,
    ) -> list[str]:

        if not directory.is_dir():
            return []

        return sorted(
            str(p.relative_to(directory))
            for p in directory.rglob("*")
            if p.is_file()
        )

    def _create_arguments(
        self,
        project: Path,
    ) -> ProjectManagerArguments:

        return ProjectManagerArguments(
            project_root=str(project),
            full_execute=False,
            list=False,
            execute_configurations="",
            execute_inplace=True,
            skip_cleanup=False,
            generate_report=False,
            show_report=False,
            initialize_directory=False,
            apply_suggestions=None,
            reset=False,
            reset_execution_results=False,
            gui=False,
            label_prefix="benchmark",
            timeout_execution=float(self.timeout),
            timeout_compilation=float(self.timeout),
            timeout_validation=float(self.timeout),
            log_level="WARNING",
            write_log=False,
        )

    @staticmethod
    def _failure(
        stage: str,
        result: Any,
    ) -> dict[str, Any]:

        return {
            "success": False,
            "analysis_available": False,
            "stage": stage,
            "returncode": result[0],
            "elapsed": result[1],
            "stdout": result[2],
            "stderr": result[3],
        }
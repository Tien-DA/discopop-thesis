import json
import os
import re
import shlex
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

        build_result = execute_configuration(
            arguments=arguments,
            project_copy_root_path=str(project),
            config_path=str(configs_dir),
            settings_path=str(settings),
            script_path=str(compile_script),
            thread_count=1,
            timeout=float(self.timeout),
        )

        if build_result[0] != 0:
            failure = self._failure(
                "compile",
                build_result,
            )

            print()
            print("[DiscoPoP] Build failed")
            print(f"[DiscoPoP] Return code: {build_result[0]}")
            self._print_process_output(build_result)

            return failure

        profile_executable = self._profile_executable(
            project, case.profiling_command
        )
        if profile_executable is not None and not profile_executable.is_file():
            message = (
                f"Build returned success but did not create the profiling "
                f"executable: {profile_executable}. Check the compiler output above."
            )
            failure_result = (
                1,
                build_result[1],
                build_result[2],
                build_result[3] + "\n" + message,
            )
            print()
            print("[DiscoPoP] Build failed")
            self._print_process_output(failure_result)
            return self._failure("compile", failure_result)

        # ------------------------------------------------------------
        # EXECUTE
        # ------------------------------------------------------------

        print()
        print("=" * 80)
        print(
            f"[DiscoPoP] Execute: {case.name}"
        )
        print("=" * 80)

        execution_timeout = getattr(case, "profiling_timeout_seconds", None) or self.timeout

        result = execute_configuration(
            arguments=arguments,
            project_copy_root_path=str(project),
            config_path=str(default_dir),
            settings_path=str(settings),
            script_path=str(execute_script),
            thread_count=1,
            timeout=float(execution_timeout),
        )

        if result[0] != 0:
            print()
            print("[DiscoPoP] Execute returned non-zero")
            print(f"[DiscoPoP] Return code: {result[0]}")
            self._print_process_output(result)

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
            if result[0] == 0:
                print("[DiscoPoP] Execution finished but profiler artifacts are missing.")
                self._print_process_output(result)
            return {
                "success": False,
                "analysis_available": False,
                "stage": "profiling",
                "returncode": result[0],
                "build_returncode": build_result[0],
                "build_stdout": build_result[2],
                "build_stderr": build_result[3],
                "stdout": result[2],
                "stderr": result[3],
                "missing_artifacts": missing,
            }

        # ------------------------------------------------------------
        # EXPLORER
        # ------------------------------------------------------------

        try:
            explorer = self._run_explorer(project)
        except subprocess.TimeoutExpired as exc:
            return {
                "success": False,
                "analysis_available": False,
                "stage": "pattern_detection_timeout",
                "timeout_seconds": self.timeout,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            }

        if explorer.returncode != 0:
            file_mappings = self._referenced_file_mappings(
                project,
                explorer.stderr,
            )
            print()
            print("[DiscoPoP] Pattern detection failed")
            print(f"[DiscoPoP] Return code: {explorer.returncode}")
            if file_mappings:
                print()
                print("[DiscoPoP] Referenced source files:")
                for file_id, path in file_mappings.items():
                    print(f"  {file_id}: {path}")
            if explorer.stdout:
                print()
                print("[DiscoPoP] STDOUT:")
                print(explorer.stdout)
            if explorer.stderr:
                print()
                print("[DiscoPoP] STDERR:")
                print(explorer.stderr)
            return {
                "success": False,
                "analysis_available": False,
                "stage": "pattern_detection",
                "returncode": explorer.returncode,
                "stdout": explorer.stdout,
                "stderr": explorer.stderr,
                "referenced_file_mappings": file_mappings,
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

        configs = (project/ ".discopop"/ "project"/ "configs")

        default = configs / "default"

        default.mkdir(parents=True,exist_ok=True)
        (project / ".discopop" / "profiler").mkdir(
            parents=True,
            exist_ok=True,
        )

        seq_settings = configs / "seq_settings.json"

        if not seq_settings.exists():
            seq_settings.write_text(
                """{
    "CC": "gcc",
    "CXX": "g++",
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

        dp_settings = configs / "dp_settings.json"
        settings = json.loads(
            dp_settings.read_text(encoding="utf-8")
        )
        settings.pop("CFLAGS", None)
        settings.pop("CXXFLAGS", None)
        dp_settings.write_text(
            json.dumps(settings, indent=2) + "\n",
            encoding="utf-8",
        )

        self._write_compile_script(
            configs / "compile.sh",
            case.build_command,
            case.language,
        )

        if not case.profiling_command:
            raise ValueError(
                f"No profiling_command configured for benchmark case "
                f"{case.repository}/{case.name}"
            )

        self._write_execute_script(
            default / "execute.sh",
            case.profiling_command,
        )

    @staticmethod
    def _write_compile_script(
        path: Path,
        command: str,
        language: str,
    ) -> None:

        instrumenting_compiler = (
            "discopop_cxx"
            if "++" in language
            else "discopop_cc"
        )

        path.write_text(
            f"""#!/bin/bash
set -e

cd "$DP_PROJECT_ROOT_DIR"

# Keep the GCC toolchain override separate and attach it to the compiler
# command. This avoids overriding a benchmark Makefile's own CFLAGS/CXXFLAGS
# (such as -fopenmp) while allowing Clang to find libstdc++.so.
compiler_args=""
if [ -n "${{DISCOPOP_GCC_INSTALL_DIR:-}}" ]; then
    if [ ! -f "$DISCOPOP_GCC_INSTALL_DIR/libstdc++.so" ]; then
        echo "DISCOPOP_GCC_INSTALL_DIR does not contain libstdc++.so: $DISCOPOP_GCC_INSTALL_DIR" >&2
        exit 2
    fi

    compiler_args="--gcc-install-dir=$DISCOPOP_GCC_INSTALL_DIR"
fi

# Benchmark task Makefiles use COMPILER rather than CC/CXX.  Set all three
# only for this instrumented build, so the executable emits DiscoPoP profiler
# data while a normal `make all` continues to use its plain compiler.
# OpenMPI and MPICH use these variables to replace their underlying compiler
# while retaining the MPI include and link flags supplied by mpicxx/mpicc.
COMPILER="{instrumenting_compiler} $compiler_args" CC="{instrumenting_compiler} $compiler_args" CXX="{instrumenting_compiler} $compiler_args" OMPI_CC="discopop_cc $compiler_args" OMPI_CXX="discopop_cxx $compiler_args" MPICH_CC="discopop_cc $compiler_args" MPICH_CXX="discopop_cxx $compiler_args" {command}
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

cd "$DP_PROJECT_ROOT_DIR"

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
    def _profile_executable(project: Path, command: str | None) -> Path | None:
        """Find the task executable in a profiling command when it is relative."""

        if not command:
            return None
        for token in shlex.split(command):
            if token.startswith("./"):
                return project / token
        return None

    @staticmethod
    def _print_process_output(
        result: tuple[int, float, str, str],
    ) -> None:
        """Print captured script output when a benchmark stage fails."""

        stdout = result[2].strip()
        stderr = result[3].strip()

        if stdout:
            print()
            print("[DiscoPoP] STDOUT:")
            print(stdout)

        if stderr:
            print()
            print("[DiscoPoP] STDERR:")
            print(stderr)

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

    @staticmethod
    def _referenced_file_mappings(
        project: Path,
        output: str,
    ) -> dict[str, str]:
        """Resolve file IDs mentioned by Explorer diagnostics."""
        referenced_ids = set(
            re.findall(r"(?:line |Start Loop )(\d+):", output)
        )

        if not referenced_ids:
            return {}

        mapping_file = project / ".discopop" / "FileMapping.txt"
        try:
            lines = mapping_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}

        mappings: dict[str, str] = {}
        for line in lines:
            file_id, separator, path = line.partition("\t")
            if separator and file_id in referenced_ids:
                mappings[file_id] = path

        return mappings

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

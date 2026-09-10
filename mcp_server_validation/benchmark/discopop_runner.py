import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from discopop_library.ProjectManager.ProjectManagerArguments import ProjectManagerArguments
from discopop_library.ProjectManager.configurations.execution import execute_configuration
from discopop_library.ProjectManager.utilities.deriveSettingsFiles import derive_settings_files


class DiscoPoPRunner:
    """
    Runs DiscoPoP directly through its Python library.

    The MCP protocol is intentionally not used here.
    This class represents the benchmark-side DiscoPoP
    preprocessing step.
    """

    def __init__(self, timeout: int = 600):
        self.timeout = timeout

    def prepare_project(self, project: Path) -> None:
        """
        Create the basic .discopop project structure and
        generate the derived DiscoPoP settings files.
        """

        configs_dir = (
            project
            / ".discopop"
            / "project"
            / "configs"
        )

        configs_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        seq_settings = configs_dir / "seq_settings.json"

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
            str(configs_dir),
            overwrite=False,
        )

    def run(
        self,
        project: Path,
    ) -> Dict[str, Any]:
        """
        Run the DiscoPoP preprocessing pipeline:

        1. Initialize DiscoPoP settings
        2. Compile/instrument the project
        3. Execute the instrumented program
        4. Run DiscoPoP pattern detection
        """

        self.prepare_project(project)

        configs_dir = (
            project
            / ".discopop"
            / "project"
            / "configs"
        )

        default_config = configs_dir / "default"

        default_config.mkdir(
            parents=True,
            exist_ok=True,
        )

        compile_script = configs_dir / "compile.sh"
        execute_script = default_config / "execute.sh"
        dp_settings = configs_dir / "dp_settings.json"

        required_files = (
            compile_script,
            execute_script,
            dp_settings,
        )

        for path in required_files:
            if not path.exists():
                raise RuntimeError(
                    f"Required DiscoPoP file does not exist: {path}"
                )

        arguments = self._create_arguments(project)

        print()
        print("[DiscoPoP] Starting instrumentation/build...")
        print("[DiscoPoP] This may take several minutes...")

        compile_result = execute_configuration(
            arguments=arguments,
            project_copy_root_path=str(project),
            config_path=str(configs_dir),
            settings_path=str(dp_settings),
            script_path=str(compile_script),
            thread_count=1,
            timeout=float(self.timeout),
        )

        print()
        print(
            f"[DiscoPoP] Instrumentation finished "
            f"with return code {compile_result[0]}"
        )
        print(
            f"[DiscoPoP] Elapsed: {compile_result[1]:.2f}s"
        )

        if compile_result[0] != 0:
            return self._create_failure_result(
                stage="compile",
                result=compile_result,
            )

        print()
        print("[DiscoPoP] Starting profiling execution...")
        print("[DiscoPoP] Running execute.sh...")

        execute_result = execute_configuration(
            arguments=arguments,
            project_copy_root_path=str(project),
            config_path=str(default_config),
            settings_path=str(dp_settings),
            script_path=str(execute_script),
            thread_count=1,
            timeout=float(self.timeout),
        )

        print()
        print(
            f"[DiscoPoP] Profiling finished "
            f"with return code {execute_result[0]}"
        )
        print(
            f"[DiscoPoP] Elapsed: {execute_result[1]:.2f}s"
        )

        profiler = project / ".discopop" / "profiler"

        data_xml = profiler / "Data.xml"
        dynamic_dependencies = profiler / "dynamic_dependencies.txt"

        if execute_result[0] != 0:
            print(
                f"[DiscoPoP] Execution returned {execute_result[0]}."
            )

            if data_xml.exists() and dynamic_dependencies.exists():
                print(
                    "[DiscoPoP] WARNING: instrumented program failed, "
                    "but required profiler output exists."
                )
                print("[DiscoPoP] Continuing with pattern detection...")
            else:
                return self._create_failure_result(
                    stage="execute",
                    result=execute_result,
                )

        print()
        print("[DiscoPoP] Starting pattern detection...")

        explorer_result = self._run_pattern_detection(project)

        profiler = project / ".discopop" / "profiler"

        data_xml = profiler / "Data.xml"
        dynamic_dependencies = profiler / "dynamic_dependencies.txt"
        static_dependencies = profiler / "static_dependencies.txt"
        ast_dump = profiler / "ast_dump.json"

        required_artifacts = [
            data_xml,
            dynamic_dependencies,
            static_dependencies,
            ast_dump,
        ]

        missing_artifacts = [
            str(path)
            for path in required_artifacts
            if not path.exists()
        ]

        if missing_artifacts:
            return {
                "success": False,
                "stage": "pattern_detection",
                "returncode": explorer_result.returncode,
                "stdout": explorer_result.stdout,
                "stderr": explorer_result.stderr,
                "missing_artifacts": missing_artifacts,
            }

        if explorer_result.returncode != 0:
            print(
                "[DiscoPoP] Pattern detection returned a non-zero "
                "code, but required profiler artifacts exist."
            )
            print(
                "[DiscoPoP] Continuing because the benchmark only "
                "requires the analysis artifacts."
            )

        return {
            "success": True,
            "stage": "completed",
            "profiler": str(profiler),
            "data_xml": data_xml.exists(),
            "dynamic_dependencies": dynamic_dependencies.exists(),
            "static_dependencies": static_dependencies.exists(),
            "ast_dump": ast_dump.exists(),
            "pattern_detection_returncode": explorer_result.returncode,
        }

    def _create_arguments(
        self,
        project: Path,
    ) -> ProjectManagerArguments:
        """
        Create the ProjectManagerArguments object required
        by DiscoPoP's execution infrastructure.
        """

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

    def _run_pattern_detection(
        self,
        project: Path,
    ) -> subprocess.CompletedProcess:
        """
        Run discopop_explorer after profiling.
        """

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

    @staticmethod
    def _create_failure_result(
        stage: str,
        result: Any,
    ) -> Dict[str, Any]:
        """
        Convert DiscoPoP execution output into a
        benchmark-friendly result dictionary.
        """

        return {
            "success": False,
            "stage": stage,
            "returncode": result[0],
            "elapsed": result[1],
            "stdout": result[2],
            "stderr": result[3],
        }

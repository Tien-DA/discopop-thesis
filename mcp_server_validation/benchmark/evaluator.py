import json
import os
import subprocess
from pathlib import Path
from typing import Any

from benchmark.case import BenchmarkCase


class BenchmarkEvaluator:

    def evaluate(
        self,
        case: BenchmarkCase,
        workspace: Path,
        reference_workspace: Path | None = None,
    ) -> dict:

        build = self._run(
            case.build_command,
            workspace,
        )

        if build.returncode != 0:
            return {
                "passed": False,
                "status": "build_failed",
                "build": self._result(build),
            }

        test = self._run(
            case.test_command,
            workspace,
        )

        if test.returncode != 0:
            return {
                "passed": False,
                "status": "test_failed",
                "build": self._result(build),
                "tests": self._result(test),
            }

        validator_result = None

        if case.validator:
            validator_result = self._run(
                case.validator,
                workspace,
            )

            if validator_result.returncode != 0:
                return {
                    "passed": False,
                    "status": "validator_failed",
                    "build": self._result(build),
                    "tests": self._result(test),
                    "validator": self._result(
                        validator_result
                    ),
                }

        performance = None

        if case.performance_command:
            performance_result = self._run(
                case.performance_command,
                workspace,
                environment={
                    "BENCHMARK_REFERENCE_WORKSPACE": str(reference_workspace)
                    if reference_workspace
                    else "",
                    "BENCHMARK_PERFORMANCE_TOOL": str(
                        Path(__file__).with_name("performance_repair.py").resolve()
                    ),
                },
            )
            performance = self._performance_result(performance_result)

        return {
            "passed": True,
            "status": "passed",
            "build": self._result(build),
            "tests": self._result(test),
            "validator": (
                self._result(validator_result)
                if validator_result
                else None
            ),
            # Performance is observational: a failed or malformed measurement
            # never changes a correctness PASS into a FAIL.
            "performance": performance,
        }

    @staticmethod
    def _run(
        command: str,
        workspace: Path,
        environment: dict[str, str] | None = None,
    ):

        env = os.environ.copy()
        if environment:
            env.update(environment)

        return subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            errors="replace",
            env=env,
        )

    @staticmethod
    def _result(result):

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    @classmethod
    def _performance_result(cls, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        """Read a versioned performance report without changing correctness.

        A task's ``performance_command`` must write one JSON object to stdout.
        The task selects its trusted reference and workload. The runner stores
        and displays the report, including any task-specific performance point.
        """
        command_result = cls._result(result)

        if result.returncode != 0:
            return {
                "available": False,
                "error": "performance command failed",
                "command": command_result,
            }

        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return {
                "available": False,
                "error": f"performance command did not emit valid JSON: {exc.msg}",
                "command": command_result,
            }

        if not isinstance(report, dict):
            return {
                "available": False,
                "error": "performance command must emit a JSON object",
                "command": command_result,
            }

        if report.get("schema_version") != 1:
            return {
                "available": False,
                "error": "performance report must declare schema_version 1",
                "command": command_result,
            }

        return {
            "available": True,
            "report": report,
            "command": command_result,
        }

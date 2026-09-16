import subprocess
from pathlib import Path

from benchmark.case import BenchmarkCase


class BenchmarkEvaluator:

    def evaluate(
        self,
        case: BenchmarkCase,
        workspace: Path,
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
        }

    @staticmethod
    def _run(
        command: str,
        workspace: Path,
    ):

        return subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _result(result):

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
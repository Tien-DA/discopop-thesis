"""Validate repair performance policy and correctness oracles on references.

Run from mcp_server_validation on Linux:
    python3 -B tests/test_repair_validation.py ReferenceOracleTests -v

Each stage prints its status and captured output immediately after completion.
No report or log files are created by this runner. The unchanged test_race.sh
may create its own files inside the isolated workspace; diagnostics are printed
before that workspace is automatically removed. A PASS establishes acceptance
of this reference in this environment, not rejection of every incorrect repair.
The Linux oracle checks are skipped on macOS.
For tasks with tests/expected.out, each unsanitized reference control is also
checked against that file using the oracle's grep -E rules. Reference adapters
are applied before this check; this does not validate untouched upstream stdout.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.case import BenchmarkCase
from benchmark.evaluator import BenchmarkEvaluator
from benchmark.performance.performance_repair import (
    MIN_PERFORMANCE_RATIO, bootstrap_interval, performance_point,
)


class PerformanceRepairTests(unittest.TestCase):
    def test_performance_runs_only_after_correctness(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            command = (
                'test -f "$BENCHMARK_PERFORMANCE_TOOL" && '
                'test -f "$BENCHMARK_PARALLEL_PERFORMANCE_TOOL" && '
                "touch performance_ran && "
                "printf '%s' '{\"schema_version\":1,\"status\":\"pass\","
                "\"performance_point\":1,\"comparisons\":[]}'"
            )
            base = dict(
                index=1, repository="openmp_correctness_repair",
                name="synthetic", workspace=workspace, task="repair",
                build_command="true", profiling_command=None,
                performance_command=command,
            )
            failed = BenchmarkEvaluator().evaluate(
                BenchmarkCase(**base, test_command="false"), workspace
            )
            self.assertFalse(failed["passed"])
            self.assertFalse((workspace / "performance_ran").exists())

            passed = BenchmarkEvaluator().evaluate(
                BenchmarkCase(**base, test_command="true"), workspace
            )
            self.assertTrue(passed["passed"])
            self.assertTrue((workspace / "performance_ran").exists())
            self.assertEqual(passed["performance"]["report"]["performance_point"], 1)

    def test_paired_confidence_interval(self):
        self.assertEqual(bootstrap_interval([1.0] * 9), [1.0, 1.0])
        self.assertGreater(bootstrap_interval([1.0] * 9)[0], MIN_PERFORMANCE_RATIO)

    def test_performance_point_threshold(self):
        self.assertEqual(performance_point([0.91, 1.01]), ("pass", 1))
        self.assertEqual(performance_point([0.70, 0.89]), ("fail", 0))
        self.assertEqual(performance_point([0.85, 0.96]), ("inconclusive", None))


# These are integration tests: on Linux, execute the real hidden oracle against
# its known race-free reference in an isolated copy.
TASK_ROOT = Path(__file__).resolve().parents[1] / ".workspaces/openmp_correctness_repair"


def correctness_tasks():
    return sorted(path.parent for path in TASK_ROOT.glob("*/benchmark.json"))


def prepare_reference(task, workspace):
    shutil.copytree(
        task, workspace,
        ignore=shutil.ignore_patterns("build", ".discopop", ".git", "__pycache__"),
    )
    references = list((task / "tests/reference").glob("DRB*.c"))
    if task.name == "loopb_bad2":
        reference = task / "tests/reference/c_loopB.pipelineSolution.c"
        candidate = workspace / "src/c_loopB.badSolution2.c"
    else:
        if len(references) != 1:
            raise ValueError(f"{task.name}: expected exactly one DRB reference")
        reference = references[0]
        candidates = list((workspace / "src").glob("*.c"))
        if len(candidates) != 1:
            raise ValueError(f"{task.name}: expected exactly one candidate source")
        candidate = candidates[0]

    source = reference.read_bytes().decode("latin-1")
    adaptations = []
    if task.name.startswith("DRB027-"):
        # The upstream reference asserts the result, while the task prints it.
        if source.count("assert (i==2);") != 1:
            raise ValueError("DRB027 reference layout changed; review adapter")
        source = "#include <stdio.h>\n" + source.replace(
            "assert (i==2);", 'assert (i==2);\n  printf("i=%d\\n", i);'
        )
        adaptations.append("Add task stdout interface i=<value>; retain assertion")
    elif task.name.startswith("DRB106-"):
        # Preserve the race-free fib implementation, matching the task's n=10.
        for old, new in (
            ("unsigned int input = 30;", "unsigned int input = 10;"),
            ("assert (result==832040);", "assert (result==55);"),
        ):
            if source.count(old) != 1:
                raise ValueError("DRB106 reference layout changed; review adapter")
            source = source.replace(old, new)
        adaptations.append("Use task input fib(10) and assert result == 55")
    candidate.write_bytes(source.encode("latin-1"))
    return {
        "reference": str(reference),
        "candidate": str(candidate.relative_to(workspace)),
        "adaptations": adaptations,
    }


def print_output(text, limit=18):
    """Keep useful diagnostic context without dumping every stack frame."""
    lines = text.strip().splitlines()
    if len(lines) > limit:
        head, tail = limit // 2, limit // 2 - 1
        selected = lines[:head] + ["..."] + lines[-tail:]
        summaries = [line for line in lines if line.startswith("SUMMARY:")]
        for line in summaries:
            if line not in selected:
                selected.append(line)
        lines = selected
    for line in lines:
        print("      " + line, flush=True)


def run_stage(label, command, workspace, environment=None, timeout=420):
    """Capture command output in memory and print the result of each stage."""
    env = os.environ.copy()
    if environment:
        env.update(environment)
    print(f"  {label}: RUNNING", flush=True)
    process = subprocess.Popen(
        command, cwd=workspace, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    except BaseException:
        # Do not leave compiler/application processes running on interruption.
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    stdout = stdout.decode(errors="replace")
    stderr = stderr.decode(errors="replace")
    passed = process.returncode == 0 and not timed_out
    print(f"  {label}: {'PASS' if passed else 'FAIL'} "
          f"(exit={process.returncode}{', TIMEOUT' if timed_out else ''})",
          flush=True)
    if stdout.strip():
        print("    stdout:", flush=True)
        print_output(stdout, limit=6 if passed else 18)
    if stderr.strip():
        print("    stderr:", flush=True)
        print_output(stderr)
    return {
        "returncode": process.returncode, "timed_out": timed_out,
        "stdout": stdout, "stderr": stderr,
    }


def sanitizer_diagnostics(workspace):
    """Read files created by the unchanged oracle, before workspace cleanup."""
    build = workspace / "build"
    paths = sorted(build.glob("tsan-*.err")) + sorted(build.glob("test-*.vector"))
    return [(path.relative_to(workspace), path.read_text(errors="replace"))
            for path in paths]


def check_reference_expected(output, expected_file, workers):
    """Match Bash's $(<file) and grep -Eq semantics without writing output files."""
    pattern = expected_file.read_bytes().decode("utf-8").rstrip("\n")
    if pattern == "__EMPTY__":
        code, error = (0 if output == "" else 1), ""
    else:
        result = subprocess.run(
            ["grep", "-E", "-q", "--", pattern], input=output,
            capture_output=True, text=True, timeout=10,
        )
        code, error = result.returncode, result.stderr
    status = "PASS" if code == 0 else "FAIL" if code == 1 else "ERROR"
    print(f"  Reference vs expected.out OMP_NUM_THREADS={workers}: {status}", flush=True)
    print(f"    Expected (ERE pattern or __EMPTY__): {pattern!r}", flush=True)
    if code:
        print(f"    Actual stdout: {output!r}", flush=True)
        if error:
            print_output(error)
    return {"status": status, "returncode": code, "workers": workers}


def diagnose_reference(entry):
    """Describe evidence; a TSan report alone does not establish a real race."""
    if entry.get("error"):
        return "setup_error: " + entry["error"]
    if entry["build"]["returncode"] != 0:
        return "build_timeout" if entry["build"]["timed_out"] else "build_failed"
    controls = entry["controls"]
    if len(controls) != 3 or any(r["returncode"] != 0 for r in controls):
        return "reference_control_failed (without sanitizer)"
    expected_checks = entry.get("expected_checks")
    if expected_checks is not None:
        if any(check["status"] == "ERROR" for check in expected_checks):
            return "expected_check_error (invalid pattern or grep failure)"
        if any(check["status"] == "FAIL" for check in expected_checks):
            return "reference_expected_mismatch (check expected.out and reference interface/input)"
        if len(expected_checks) != 3:
            return "reference_expected_check_incomplete"
    oracle = entry["oracle"]
    if oracle["timed_out"]:
        return "oracle_timeout"
    if oracle["returncode"] == 0:
        return "accepted_reference"
    diagnostics = oracle["stderr"] + "\n" + entry.get("sanitizer", "")
    if "[Archer setup] ERROR:" in diagnostics:
        return "archer_setup_failed (compiler/runtime/self-check; not a reference verdict)"
    if "FATAL: ThreadSanitizer" in diagnostics:
        return "tsan_runtime_error"
    if "WARNING: ThreadSanitizer: data race" in diagnostics:
        return "tsan_reported_race (not proof of a genuine race)"
    if "ThreadSanitizer reported a data race" in diagnostics:
        return "script_reported_race (raw report missing)"
    if any(text in diagnostics for text in (
        "output differs", "output did not match", "Expected no output",
        "result differs", "Final vector differs",
    )):
        return "output_mismatch"
    if "construct was removed" in diagnostics:
        return "openmp_structure_rejected"
    return "oracle_failed (see diagnostics above)"


def show_oracle_details(entry, workspace):
    """Expose sanitizer reports that test_race.sh does not forward to stderr."""
    raw_logs = sanitizer_diagnostics(workspace)
    entry["sanitizer"] = "\n".join(text for _, text in raw_logs)
    seen = entry["oracle"]["stderr"]
    for path, raw in raw_logs:
        if "ThreadSanitizer" not in raw:
            continue
        # Do not print the same report twice when the script already printed it.
        if raw.strip() and raw.strip() in seen:
            continue
        print(f"    Sanitizer details ({path}):", flush=True)
        start = raw.find("WARNING: ThreadSanitizer")
        if start < 0:
            start = raw.find("FATAL: ThreadSanitizer")
        print_output(raw[max(0, start):])
    if "output_mismatch" in diagnose_reference(entry):
        build = workspace / "build"
        paths = sorted(set(build.glob("test-*.out")) |
                       set(build.glob("reference-*.out")) |
                       set(build.glob("test-*.vector")) |
                       set(build.glob("reference-*.vector")))
        expected = workspace / "tests/expected.out"
        if expected.exists():
            print("    Expected output pattern:", flush=True)
            print_output(expected.read_text())
        for path in paths:
            print(f"    {path.relative_to(workspace)}:", flush=True)
            print_output(path.read_text(errors="replace"), limit=10)


class ReferenceDiagnosticTests(unittest.TestCase):
    def test_diagnoses_preserve_failing_stage(self):
        entry = {
            "build": {"returncode": 0, "timed_out": False},
            "controls": [{"returncode": 0} for _ in range(3)],
            "oracle": {"returncode": 2, "timed_out": False, "stderr": ""},
            "sanitizer": "WARNING: ThreadSanitizer: data race",
        }
        self.assertIn("tsan_reported_race", diagnose_reference(entry))
        entry["sanitizer"] = "FATAL: ThreadSanitizer: unexpected memory mapping"
        self.assertEqual("tsan_runtime_error", diagnose_reference(entry))
        entry["sanitizer"] = ""
        entry["oracle"]["stderr"] = "Program output did not match"
        self.assertEqual("output_mismatch", diagnose_reference(entry))
        entry["controls"][0]["returncode"] = -11
        self.assertIn("reference_control_failed", diagnose_reference(entry))
        entry["build"]["returncode"] = 2
        self.assertEqual("build_failed", diagnose_reference(entry))

    def test_setup_failure_is_not_a_reference_race(self):
        entry = {
            "build": {"returncode": 0},
            "controls": [{"returncode": 0} for _ in range(3)],
            "oracle": {"returncode": 2, "timed_out": False,
                       "stderr": "WARNING: ThreadSanitizer: data race\n"
                                 "[Archer setup] ERROR: Known-correct probe failed"},
        }
        self.assertIn("archer_setup_failed", diagnose_reference(entry))

    def test_archer_helper_rejects_gcc_before_running_oracles(self):
        helper = Path(__file__).resolve().parents[1] / "benchmark/validation/archer.sh"
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            fake_cc = workspace / "fake-gcc"
            fake_cc.write_text("#!/bin/sh\nprintf 'gcc version 14\\n'\n")
            fake_cc.chmod(0o755)
            result = subprocess.run(
                ["bash", "-c", 'set -euo pipefail; source "$1"', "probe", str(helper)],
                cwd=workspace, env={**os.environ, "CC": str(fake_cc)},
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("[Archer setup] ERROR: Use Clang", result.stderr)
            self.assertFalse((workspace / "build").exists())

    def test_stage_prints_output_and_oracle_exposes_hidden_report(self):
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "build").mkdir()
            script = (
                "from pathlib import Path; import sys; "
                "Path('build/tsan-2.err').write_text("
                "'WARNING: ThreadSanitizer: data race\\nSUMMARY: hidden report\\n'); "
                "print('ThreadSanitizer reported a data race', file=sys.stderr); "
                "sys.exit(2)"
            )
            output = io.StringIO()
            entry = {
                "build": {"returncode": 0},
                "controls": [{"returncode": 0} for _ in range(3)],
            }
            with contextlib.redirect_stdout(output):
                entry["oracle"] = run_stage(
                    "Oracle", [sys.executable, "-c", script], workspace
                )
                show_oracle_details(entry, workspace)
            self.assertEqual(entry["oracle"]["returncode"], 2)
            self.assertIn("Oracle: RUNNING", output.getvalue())
            self.assertIn("Oracle: FAIL (exit=2)", output.getvalue())
            self.assertIn("SUMMARY: hidden report", output.getvalue())
            # Only the unchanged oracle's own file was written.
            self.assertEqual(
                [str(path.relative_to(workspace)) for path in workspace.rglob("*")
                 if path.is_file()], ["build/tsan-2.err"],
            )

    def test_stage_timeout_is_reported(self):
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = run_stage(
                    "Control", [sys.executable, "-c", "import time; time.sleep(10)"],
                    Path(temporary), timeout=0.1,
                )
            self.assertTrue(result["timed_out"])
            self.assertIn("TIMEOUT", output.getvalue())


class ReferenceExpectedTests(unittest.TestCase):
    def test_expected_numbers_cannot_match_longer_numbers(self):
        import contextlib
        import io

        invalid = {"DRB013": "error = 510\n", "DRB109": "x=1000\n",
                   "DRB106": "Fib(10)=550\n"}
        with contextlib.redirect_stdout(io.StringIO()):
            for prefix, output in invalid.items():
                expected = next(TASK_ROOT.glob(prefix + "*/tests/expected.out"))
                self.assertEqual(check_reference_expected(output, expected, 2)["status"], "FAIL")
            fib = next(TASK_ROOT.glob("DRB106*/tests/expected.out"))
            self.assertEqual(check_reference_expected(
                "Fib(10)=55 (correct answer should be 55)\n", fib, 2,
            )["status"], "PASS")

    def test_actual_expected_files_match_known_reference_outputs(self):
        import contextlib
        import io

        examples = {
            "DRB013": ("error = 51\n", "error = 50\n"),
            "DRB027": ("i=2\n", "i=1\n"),
            "DRB106": ("Fib(10)=55\n", "Fib(10)=54\n"),
            "DRB109": ("x=100\n", "x=99\n"),
            "DRB119": ("2\n", "1\n"),
        }
        files = list(TASK_ROOT.glob("*/tests/expected.out"))
        self.assertEqual(len(files), len(examples))
        with contextlib.redirect_stdout(io.StringIO()):
            for expected in files:
                name = expected.parent.parent.name[:6]
                with self.subTest(task=name):
                    correct, wrong = examples[name]
                    self.assertEqual(check_reference_expected(correct, expected, 2)["status"], "PASS")
                    self.assertEqual(check_reference_expected(wrong, expected, 2)["status"], "FAIL")

    def test_empty_output_invalid_pattern_and_diagnosis(self):
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as temporary:
            expected = Path(temporary) / "expected.out"
            terminal = io.StringIO()
            with contextlib.redirect_stdout(terminal):
                expected.write_text("__EMPTY__\n")
                self.assertEqual(check_reference_expected("", expected, 1)["status"], "PASS")
                failure = check_reference_expected("\n", expected, 1)
                self.assertEqual(failure["status"], "FAIL")
                expected.write_text("[\n")
                error = check_reference_expected("anything", expected, 1)
                self.assertEqual(error["status"], "ERROR")
            self.assertIn("Actual stdout:", terminal.getvalue())
            entry = {
                "build": {"returncode": 0},
                "controls": [{"returncode": 0} for _ in range(3)],
                "oracle": {"returncode": 0, "timed_out": False, "stderr": ""},
                "expected_checks": [failure],
            }
            self.assertIn("reference_expected_mismatch", diagnose_reference(entry))
            entry["expected_checks"] = [error]
            self.assertIn("expected_check_error", diagnose_reference(entry))
            entry["expected_checks"] = None
            self.assertEqual("accepted_reference", diagnose_reference(entry))


class ReferencePreparationTests(unittest.TestCase):
    def test_prepare_all_references_without_changing_oracles(self):
        tasks = correctness_tasks()
        self.assertEqual(len(tasks), 15)
        with tempfile.TemporaryDirectory() as temporary:
            for task in tasks:
                with self.subTest(task=task.name):
                    workspace = Path(temporary) / task.name
                    metadata = prepare_reference(task, workspace)
                    for name in ("Makefile", "tests/test_race.sh", "benchmark.json"):
                        self.assertEqual(
                            (task / name).read_bytes(), (workspace / name).read_bytes()
                        )
                    self.assertEqual(
                        (Path(__file__).resolve().parents[1] / "benchmark/validation/archer.sh").read_bytes(),
                        (workspace / "tests/archer.sh").read_bytes(),
                    )
                    self.assertFalse((workspace / "tests/archer.sh").is_symlink())
                    expected = task / "tests/expected.out"
                    if expected.exists():
                        self.assertEqual(
                            expected.read_bytes(),
                            (workspace / "tests/expected.out").read_bytes(),
                        )
                    source = (workspace / metadata["candidate"]).read_bytes().decode("latin-1")
                    if task.name.startswith("DRB027-"):
                        self.assertIn('printf("i=%d\\n", i);', source)
                        self.assertIn("assert (i==2);", source)
                    if task.name.startswith("DRB106-"):
                        self.assertIn("unsigned int input = 10;", source)
                        self.assertIn("assert (result==55);", source)


class ArcherSetupTests(unittest.TestCase):
    def test_helper_requires_activation_and_race_detection(self):
        # Exercise shell orchestration without pretending to run LLVM on macOS.
        helper = Path(__file__).resolve().parents[1] / "benchmark/validation/archer.sh"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archer = root / "libarcher.so"
            archer.touch()
            cc = root / "fake-clang"
            cc.write_text(
                f"#!{sys.executable}\n"
                "import os, sys\nfrom pathlib import Path\n"
                "args = sys.argv[1:]\n"
                "if args == ['--version']: print('clang version 19'); sys.exit(0)\n"
                "if args == ['-print-resource-dir']: print('/fake/lib/clang/19'); sys.exit(0)\n"
                "if args == ['-print-file-name=libarcher.so']: print('libarcher.so'); sys.exit(0)\n"
                "assert '-fopenmp=libomp' in args and '-fsanitize=thread' in args\n"
                "target = Path(args[args.index('-o') + 1])\n"
                "if target.name == 'archer-good':\n"
                "    text = '#!/bin/sh\\n' + ('' if os.environ.get('FAKE_NO_ARCHER') else "
                "\"echo 'Archer detected OpenMP application with TSan'\\n\") + 'exit 0\\n'\n"
                "else:\n"
                "    text = '#!/bin/sh\\n' + ('exit 0\\n' if os.environ.get('FAKE_MISS_RACE') else "
                "\"echo 'WARNING: ThreadSanitizer: data race' >&2\\nexit 66\\n\")\n"
                "target.write_text(text)\ntarget.chmod(0o755)\n"
            )
            cc.chmod(0o755)
            for name, text in {
                "uname": "echo Linux\n",
                "ldd": "echo 'libomp.so.5 => /fake/libomp.so.5'\n",
                "timeout": 'shift\nexec "$@"\n',
            }.items():
                shim = root / name
                shim.write_text("#!/bin/sh\n" + text)
                shim.chmod(0o755)
            base_env = {
                **os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                "CC": str(cc), "ARCHER_LIBRARY": str(archer),
            }
            for overrides, expected in (
                ({}, "[Archer setup] PASS"),
                ({"FAKE_NO_ARCHER": "1"}, "Archer did not activate"),
                ({"FAKE_MISS_RACE": "1"}, "Race detector self-check failed"),
                ({"ARCHER_LIBRARY": str(root / "missing.so")}, "libarcher.so not found"),
            ):
                with self.subTest(expected=expected):
                    result = subprocess.run(
                        ["bash", "-c", 'set -euo pipefail; source "$1"', "probe", str(helper)],
                        cwd=root, env={**base_env, **overrides}, capture_output=True, text=True,
                        timeout=20,
                    )
                    self.assertIn(expected, result.stdout + result.stderr)
                    self.assertEqual(result.returncode == 0, not overrides)


class OracleOutputRoutingTests(unittest.TestCase):
    def test_real_oracle_scripts_accept_and_reject_outputs(self):
        # Run the actual Makefile/test_race.sh on every platform. Only compiler
        # and Archer setup are stubbed; this tests output routing, not C or TSan.
        outputs = {
            "DRB013": "error = 51\n", "DRB027": "i=2\n",
            "DRB106": "Fib(10)=55 (correct answer should be 55)\n",
            "DRB109": "x=100\n", "DRB119": "2\n",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiler = root / "fake-clang"
            program = (
                "import os, sys\n"
                "kind = KIND\n"
                "with open('executions', 'a') as log:\n"
                "    log.write(kind + ':' + os.environ['OMP_NUM_THREADS'] + '\\n')\n"
                "if kind == 'tsan-app' and os.environ.get('FAKE_RACE'):\n"
                "    print('WARNING: ThreadSanitizer: data race', file=sys.stderr)\n"
                "    sys.exit(66)\n"
                "text = os.environ['FAKE_OUTPUT']\n"
                "if kind == 'tsan-app':\n"
                "    text = os.environ.get('FAKE_CANDIDATE', text)\n"
                "stream = sys.stderr if os.environ.get('FAKE_VECTOR') else sys.stdout\n"
                "stream.write(text)\n"
            )
            compiler.write_text(
                f"#!{sys.executable}\n"
                "import sys\nfrom pathlib import Path\n"
                "args = sys.argv[1:]\n"
                "for arg in args:\n"
                "    if arg.endswith('.c'): assert Path(arg).is_file(), arg\n"
                "target = Path(args[args.index('-o') + 1])\n"
                "with open('compilations', 'a') as log: log.write(target.name + '\\n')\n"
                f"program = {program!r}\n"
                f"target.write_text('#!{sys.executable}\\n' + "
                "program.replace('KIND', repr(target.name)))\n"
                "target.chmod(0o755)\n"
            )
            compiler.chmod(0o755)
            timeout = root / "timeout"
            timeout.write_text('#!/bin/sh\nshift\nexec "$@"\n')
            timeout.chmod(0o755)
            for task in correctness_tasks():
                has_expected = (task / "tests/expected.out").exists()
                for mode in ("correct", "wrong", "race"):
                    with self.subTest(task=task.name, mode=mode):
                        workspace = root / (task.name + "-" + mode)
                        shutil.copytree(task, workspace, ignore=shutil.ignore_patterns(
                            "build", ".discopop", ".git", "__pycache__",
                        ))
                        # No reference files at all for the expected.out route.
                        if has_expected:
                            shutil.rmtree(workspace / "tests/reference")
                        (workspace / "tests/archer.sh").write_text(
                            'compiler="$CC"\nrepair_openmp_flags=(-fopenmp=libomp)\n'
                            "REPAIR_TSAN_OPTIONS='halt_on_error=1 exitcode=66'\n"
                        )
                        env = {**os.environ, "CC": str(compiler),
                               "COMPILER": str(compiler),
                               "PATH": str(root) + os.pathsep + os.environ["PATH"],
                               "FAKE_OUTPUT": outputs.get(task.name[:6], "same result\n")}
                        if task.name == "loopb_bad2":
                            env["FAKE_VECTOR"] = "1"
                        if mode == "wrong":
                            env["FAKE_CANDIDATE"] = "wrong result\n"
                        if mode == "race":
                            env["FAKE_RACE"] = "1"
                        result = subprocess.run(
                            ["make", "test"], cwd=workspace, env=env,
                            capture_output=True, text=True, timeout=20,
                        )
                        self.assertEqual(result.returncode == 0, mode == "correct",
                                         result.stdout + result.stderr)
                        compiled = (workspace / "compilations").read_text().splitlines()
                        self.assertEqual(compiled.count("tsan-app"), 1)
                        self.assertEqual(compiled.count("reference-app"), 0 if has_expected else 1)
                        executions = (workspace / "executions").read_text()
                        if has_expected:
                            self.assertNotIn("reference-app", executions)
                        else:
                            self.assertIn("reference-app:1", executions)
                        if mode == "correct":
                            self.assertIn("tsan-app:4", executions)
                        elif mode == "wrong":
                            self.assertIn("expected behavior" if has_expected else "differs", result.stderr)
                        else:
                            self.assertTrue("data race" in result.stderr or task.name == "loopb_bad2")


@unittest.skipUnless(sys.platform.startswith("linux"), "Requires Linux Clang/libomp/Archer/TSan")
class ReferenceOracleTests(unittest.TestCase):
    def test_all_correctness_oracles_accept_their_reference(self):
        tasks = correctness_tasks()
        self.assertEqual(len(tasks), 15)
        results = []
        print("\nReference validation: 15 tasks; output shown below.", flush=True)
        print("Controls set OMP_NUM_THREADS; source num_threads clauses may override it.",
              flush=True)
        for position, task in enumerate(tasks, 1):
            print(f"\n[{position}/{len(tasks)}] {task.name}", flush=True)
            entry = {"task": task.name, "status": "ERROR"}
            results.append(entry)
            try:
                with tempfile.TemporaryDirectory(prefix="repair-reference-") as temporary:
                    workspace = Path(temporary) / "workspace"
                    metadata = prepare_reference(task, workspace)
                    print(f"  Reference: {Path(metadata['reference']).name}", flush=True)
                    for adaptation in metadata["adaptations"]:
                        print(f"  Adapter: {adaptation}", flush=True)
                    config = json.loads((workspace / "benchmark.json").read_text())
                    entry["build"] = run_stage(
                        "Build", ["bash", "-c", config["build_command"]], workspace,
                    )
                    entry["controls"] = []
                    expected_file = workspace / "tests/expected.out"
                    entry["expected_checks"] = [] if expected_file.exists() else None
                    if not expected_file.exists():
                        print("  Reference vs expected.out: N/A (no expected.out)", flush=True)
                    if entry["build"]["returncode"] == 0:
                        args = ["1000", "20"] if task.name == "loopb_bad2" else []
                        for workers in (1, 2, 4):
                            entry["controls"].append(run_stage(
                                f"Control OMP_NUM_THREADS={workers}",
                                ["./build/app", *args], workspace,
                                {"OMP_NUM_THREADS": str(workers)}, timeout=60,
                            ))
                            control = entry["controls"][-1]
                            if expected_file.exists():
                                if control["returncode"] == 0:
                                    entry["expected_checks"].append(check_reference_expected(
                                        control["stdout"], expected_file, workers,
                                    ))
                                else:
                                    print(f"  Reference vs expected.out OMP_NUM_THREADS={workers}: "
                                          "SKIP (control failed)", flush=True)
                    else:
                        print("  Controls: SKIP (build failed)", flush=True)
                    print(f"  Oracle command: {config['test_command']}", flush=True)
                    entry["oracle"] = run_stage(
                        "Oracle (test_race.sh)",
                        ["bash", "-c", config["test_command"]], workspace,
                    )
                    show_oracle_details(entry, workspace)
                    entry["diagnosis"] = diagnose_reference(entry)
                    entry["status"] = (
                        "PASS" if entry["diagnosis"] == "accepted_reference" else "FAIL"
                    )
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
                entry["diagnosis"] = diagnose_reference(entry)
            print(f"  Result: {entry['status']} — {entry['diagnosis']}", flush=True)

        print("\nREFERENCE VALIDATION SUMMARY", flush=True)
        for entry in results:
            print(f"  {entry['status']:<5} {entry['task']}: {entry['diagnosis']}",
                  flush=True)
        failed = [entry["task"] for entry in results if entry["status"] != "PASS"]
        print(f"Passed: {len(tasks) - len(failed)}/{len(tasks)}; "
              f"failed: {len(failed)}", flush=True)
        self.assertFalse(failed, "Reference validation failed: " + ", ".join(failed))


if __name__ == "__main__":
    unittest.main()

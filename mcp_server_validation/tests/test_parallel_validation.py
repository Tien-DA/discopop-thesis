"""Exercise the real correctness oracles with positive and negative controls.

Run from mcp_server_validation (Linux recommended for full coverage):
    python3 -B tests/test_parallel_validation.py -v
    python3 -B tests/test_parallel_validation.py PolyBenchValidationTests -v
    python3 -B tests/test_parallel_validation.py HotspotValidationTests -v
    python3 -B tests/test_parallel_validation.py MiniMDValidationTests -v
    python3 -B tests/test_parallel_validation.py OracleGapTests -v
    python3 -B tests/test_parallel_validation.py OracleSupportTests -v

Only temporary candidate sources are changed. Task oracles, inputs, and hidden
references are copied unchanged. No LLM, DiscoPoP, or performance measurement is
invoked. Oracle regressions are ordinary FAILs, not expected failures: accepting
an incorrect control must remain visible. Missing native toolchains are SKIPs.
These controls establish behavior for the existing test inputs, not race freedom
or correctness on arbitrary inputs. Some upstream dumps round floating values.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.evaluator import BenchmarkEvaluator
from benchmark.validation.parallel_validation import (
    Statements, ValidationFailure, compare_thermo, instrument, parse_thermo,
    require_parallel, run_bounded,
)

TASKS = Path(__file__).resolve().parents[1] / ".workspaces/parallelization"

# Each insertion targets a dependency-independent kernel loop. Outer sequential
# recurrence/reduction order is retained; private variables are explicit.
# dynprog's parallel phase is its required in-kernel c-matrix reset.
LOOPS = {
    "2mm": ("for (i = 0; i < _PB_NI; i++)", "j,k"),
    "3mm": ("for (i = 0; i < _PB_NI; i++)", "j,k"),
    "adi": ("for (i1 = 0; i1 < _PB_N; i1++)", "i2"),
    "atax": ("for (j = 0; j < _PB_NY; j++)\n\ty[j]", ""),
    "cholesky": ("for (j = i + 1; j < _PB_N; ++j)", "x,k"),
    "correlation": ("for (j = 0; j < _PB_M; j++)", "i"),
    "covariance": ("for (j = 0; j < _PB_M; j++)", "i"),
    "doitgen": ("for (r = 0; r < _PB_NR; r++)", "q,p,s"),
    "durbin": ("for (i = 0; i <= k-1; i++)", ""),
    "dynprog": ("for (i = 0; i <= _PB_LENGTH - 1; i++)", "j"),
    "fdtd_2d": ("for (i = 1; i < _PB_NX; i++)", "j"),
    "fdtd_apml": ("for (iz = 0; iz < _PB_CZ; iz++)", "iy,ix"),
    "gemm": ("for (i = 0; i < _PB_NI; i++)", "j,k"),
    "gemver": ("for (i = 0; i < _PB_N; i++)", "j"),
    "gesummv": ("for (i = 0; i < _PB_N; i++)", "j"),
    "gramschmidt": ("for (j = k + 1; j < _PB_NJ; j++)", "i"),
    "jacobi_1d_imper": ("for (i = 1; i < _PB_N - 1; i++)", ""),
    "jacobi_2d_imper": ("for (i = 1; i < _PB_N - 1; i++)", "j"),
    "lu": ("for(i = k + 1; i < _PB_N; i++)", "j"),
    "ludcmp": ("for (j = i+1; j <= _PB_N; j++)", "w,k"),
    "mvt": ("for (i = 0; i < _PB_N; i++)", "j"),
    "reg_detect": ("for (j = 0; j <= _PB_MAXGRID - 1; j++)", "i,cnt"),
    "symm": ("for (j = 0; j < _PB_NJ; j++)", "k,acc"),
    "syr2k": ("for (i = 0; i < _PB_NI; i++)", "j,k"),
    "syrk": ("for (i = 0; i < _PB_NI; i++)", "j,k"),
}
SPECIAL = {"bicg", "floyd_warshall", "seidel_2d", "trisolv", "trmm"}
PLACEHOLDER = "\nvoid unused_parallel_region(void) {\n#pragma omp parallel\n  { ; }\n}\n"


def placeholder_control(source, variant):
    if variant == "placeholder":
        return source + PLACEHOLDER
    if variant == "called_placeholder":
        return PLACEHOLDER + main_entry(source, "unused_parallel_region();")
    return source


def restrict_parallel(source, variant):
    clause = {"disabled_parallel": "if(0)", "single_thread": "num_threads(1)"}.get(variant)
    if clause:
        return re.sub(r"(#pragma omp parallel[^\n]*)", lambda match: match[0] + " " + clause, source)
    return source


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise AssertionError(f"control adapter needs review: expected one occurrence of {old!r}")
    return source.replace(old, new, 1)


def parallel_loop(body, loop, private=""):
    if loop not in body:
        raise AssertionError(f"control adapter needs review: loop not found: {loop!r}")
    clause = f" private({private})" if private else ""
    return body.replace(loop, f"#pragma omp parallel for{clause}\n  {loop}", 1)


def polybench_control(source, name):
    """Construct a small, deterministic OpenMP control from trusted source."""
    before, body = source.split("#pragma scop", 1)
    body, after = body.split("#pragma endscop", 1)
    if name in LOOPS:
        body = parallel_loop(body, *LOOPS[name])
    elif name == "bicg":
        old = "s[j] = s[j] + r[i] * A[i][j];"
        body = replace_once(body, old, "")
        body = replace_once(body, "q[i] = 0;", """q[i] = 0;
      #pragma omp parallel for
      for (j = 0; j < _PB_NY; j++)
        s[j] = s[j] + r[i] * A[i][j];""")
    elif name == "floyd_warshall":
        # Snapshot row k before any worker writes it. The fixture initializes
        # nonnegative distances; cache each row's path[i][k] before its j loop.
        body = """
  DATA_TYPE pivot[N];
  for (k = 0; k < _PB_N; k++) {
    for (j = 0; j < _PB_N; j++) pivot[j] = path[k][j];
    #pragma omp parallel for private(j)
    for (i = 0; i < _PB_N; i++) {
      DATA_TYPE ik = path[i][k];
      for (j = 0; j < _PB_N; j++)
        path[i][j] = path[i][j] < ik + pivot[j] ? path[i][j] : ik + pivot[j];
    }
  }
"""
    elif name == "seidel_2d":
        # Wavefront 2*i+j preserves dependencies on the left and previous row,
        # including the previous row's j+1 cell. Same-wave cells are independent.
        assignment = body[body.index("A[i][j] ="):].strip()
        body = """
  int wave;
  #pragma omp parallel private(t,i,j,wave)
  for (t = 0; t <= _PB_TSTEPS - 1; t++)
    for (wave = 3; wave <= 3 * (_PB_N - 2); wave++) {
      #pragma omp for
      for (i = 1; i <= _PB_N - 2; i++) {
        j = wave - 2*i;
        if (j >= 1 && j <= _PB_N - 2) { ASSIGNMENT }
      }
    }
""".replace("ASSIGNMENT", assignment)
    elif name == "trisolv":
        body = """
  DATA_TYPE products[N];
  for (i = 0; i < _PB_N; i++) {
    x[i] = c[i];
    #pragma omp parallel for
    for (j = 0; j <= i - 1; j++) products[j] = A[i][j] * x[j];
    for (j = 0; j <= i - 1; j++) x[i] = x[i] - products[j];
    x[i] = x[i] / A[i][i];
  }
"""
    elif name == "trmm":
        body = """
  DATA_TYPE products[NI];
  for (i = 1; i < _PB_NI; i++)
    for (j = 0; j < _PB_NI; j++) {
      #pragma omp parallel for
      for (k = 0; k < i; k++) products[k] = alpha * A[i][k] * B[j][k];
      for (k = 0; k < i; k++) B[i][j] += products[k];
    }
"""
    else:
        raise AssertionError(f"missing PolyBench control adapter: {name}")
    return "#include <omp.h>\n" + before + "#pragma scop" + body + "#pragma endscop" + after


def output_target(source):
    signature = source[source.index("void print_array"):]
    signature = signature[:signature.index("{")]
    array = re.search(r"POLYBENCH_([1-5])D\(\s*(\w+)", signature)
    return f"(POLYBENCH_ARRAY({array[2]}))" + "[0]" * int(array[1]) if array else "out"


def main_entry(source, statement):
    start = source.index("int main(")
    brace = source.index("{", start)
    return source[:brace + 1] + "\n" + statement + "\n" + source[brace + 1:]


def mutate_polybench(source, variant):
    if variant in {"wrong_output", "wrong_four_threads"}:
        condition = "if (omp_get_max_threads() == 4) " if variant == "wrong_four_threads" else ""
        statement = f"{condition}{output_target(source)} = (DATA_TYPE)123456789;\n"
        return replace_once(source, "  polybench_stop_instruments;", statement + "  polybench_stop_instruments;")
    if variant == "missing_output":
        return source.replace("polybench_prevent_dce(", "if (0) (")
    if variant == "compile_error":
        return source + "\n#error oracle_self_test_compile_error\n"
    if variant == "runtime_error":
        return main_entry(source, "_Exit(7);")
    if variant == "hang":
        return main_entry(source, "for (;;) { }")
    return source


def hotspot_control(source):
    return parallel_loop(source, "for ( chunk = 0; chunk < num_chunk; ++chunk )", "delta,r,c")


def mutate_hotspot(source, variant):
    anchor = "void writeoutput(FLOAT *vect, int grid_rows, int grid_cols, char *file) {"
    if variant in {"wrong_output", "wrong_four_threads"}:
        condition = "if (num_omp_threads == 4) " if variant == "wrong_four_threads" else ""
        return replace_once(source, anchor, anchor + f"\n{condition}vect[0] = 123456789;")
    if variant == "missing_output":
        return replace_once(source, anchor, anchor + "\nreturn;")
    if variant == "compile_error":
        return source + "\n#error oracle_self_test_compile_error\n"
    if variant in {"runtime_error", "hang"}:
        return main_entry(source, "_Exit(7);" if variant == "runtime_error" else "for (;;) { }")
    return source


def run_command(args, root, timeout=300, environment=None):
    env = os.environ.copy()
    env.update(OMP_DYNAMIC="FALSE", OMP_THREAD_LIMIT="4", OMPI_MCA_hwloc_base_binding_policy="none",
               TMPDIR=str(root), PS4="+ ")
    env.update(environment or {})
    with subprocess.Popen(args, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors="replace", start_new_session=True) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output, _ = process.communicate()
            raise AssertionError(f"oracle did not terminate within {timeout}s; "
                                 f"the self-test killed its process group\n{output[-2000:]}") from None
    return process.returncode, output


def require_toolchain(compiler, mpi=False):
    if mpi and (not shutil.which("mpicxx") or not shutil.which("mpirun")):
        raise unittest.SkipTest("miniMD integration requires mpicxx and mpirun")
    driver = ["mpicxx"] if mpi else shlex.split(os.environ.get("CXX" if compiler == "c++" else "CC") or compiler)
    if not shutil.which(driver[0]):
        raise unittest.SkipTest(f"compiler unavailable: {driver[0]}")
    flags = ["-fopenmp"]
    if sys.platform == "darwin":
        flags = ["-Xpreprocessor", "-fopenmp", "-I/usr/local/opt/libomp/include",
                 "-L/usr/local/opt/libomp/lib", "-lomp"]
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / ("probe.cpp" if compiler == "c++" else "probe.c")
        source.write_text("#include <omp.h>\n" + ("#include <mpi.h>\n" if mpi else "")
                          + "int main(int argc, char **argv) {\n"
                          + ("MPI_Init(&argc, &argv);\n" if mpi else "")
                          + "int n=0;\n#pragma omp parallel num_threads(4) reduction(max:n)\n"
                          + "{ n=omp_get_num_threads(); }\n"
                          + ("MPI_Finalize();\n" if mpi else "") + "return n != 4; }\n")
        code, output = run_command([*driver, *flags, str(source), "-o", str(root / "probe")], root)
        if code:
            raise unittest.SkipTest("OpenMP compiler unavailable: " + output[-500:])
        args = (["mpirun", "-np", "1"] if mpi else []) + [str(root / "probe")]
        code, output = run_command(args, root)
        if code:
            raise unittest.SkipTest("OpenMP/MPI runtime unavailable: " + output[-500:])


class OracleTests(unittest.TestCase):
    def check(self, task, variant, *, reject=False, timeout=300, environment=None):
        """Run the task's unchanged oracle against an isolated source control."""
        with tempfile.TemporaryDirectory(prefix="parallel-oracle-") as temporary:
            root = Path(temporary) / "task"
            shutil.copytree(TASKS / task, root, ignore=shutil.ignore_patterns(
                "build", "Obj_*", "miniMD", ".discopop", ".git", "__pycache__", "*.pyc"))
            if task.startswith("polybench_"):
                trusted = next(path for path in (root / "tests/reference").glob("*.c") if path.name != "polybench.c")
                source = root / "src" / trusted.name
                original = trusted.read_text()
                if variant in {"serial", "placeholder", "called_placeholder"}:
                    text = placeholder_control(original, variant)
                else:
                    text = mutate_polybench(polybench_control(original, task.removeprefix("polybench_")), variant)
                    text = restrict_parallel(text, variant)
                source.write_text(text)
            elif task == "rodinia_hotspot":
                original = (root / "tests/reference/hotspot.cpp").read_text()
                text = original if variant in {"serial", "placeholder", "called_placeholder"} else hotspot_control(original)
                text = mutate_hotspot(text, variant)
                text = restrict_parallel(placeholder_control(text, variant), variant)
                (root / "src/hotspot.cpp").write_text(text)
            else:
                self.prepare_minimd(root, variant)
                config = json.loads((root / "benchmark.json").read_text())
                code, output = run_command(["bash", "-c", config["build_command"]], root, timeout=180)
                if variant == "compile_error":
                    self.assertNotEqual(code, 0, "miniMD build accepted #error control")
                    self.assertIn("oracle_self_test_compile_error", output)
                    return
                self.assertEqual(code, 0, "miniMD control did not build:\n" + output[-4000:])
            code, output = run_command(["bash", "-x", "tests/test_parallelization.sh"], root,
                                       timeout=timeout, environment=environment)
            context = f"{task}/{variant}: oracle returned {code}\n{output[-4000:]}"
            if reject:
                self.assertNotEqual(code, 0, f"ORACLE GAP: {task}/{variant} returned PASS; expected rejection.")
            else:
                self.assertEqual(code, 0, "positive control rejected. " + context)
                self.assertIn("parallel execution: multiple workers executed a computational loop", output, context)
            if variant == "compile_error":
                self.assertIn("oracle_self_test_compile_error", output, context)
            if task != "mantevo_minimd":
                if variant in {"wrong_output", "wrong_four_threads", "missing_output"}:
                    self.assertIn("output comparison:", output, "control failed before output comparison. " + context)
                if variant == "wrong_four_threads":
                    self.assertIn("output comparison: candidate", output, context)
                    self.assertIn("workers=4", output, context)
                if variant in {"serial", "placeholder", "called_placeholder", "disabled_parallel", "single_thread"}:
                    self.assertIn("no computational loop site executed by multiple OpenMP workers", output, context)
                if variant == "runtime_error":
                    self.assertEqual(code, 7, context)
            if variant == "hang":
                self.assertEqual(code, 124, context)
                self.assertIn("validation timeout", output, context)
            if task == "mantevo_minimd" and variant in {"wrong_output", "wrong_four_threads"}:
                self.assertIn("output comparison:", output, context)
                self.assertIn("miniMD reference mismatch", output, context)

    @staticmethod
    def prepare_minimd(root, variant):
        for trusted in (root / "tests/reference").iterdir():
            if trusted.suffix in {".cpp", ".h"} or trusted.name in {"Makefile.default", "in.lj.miniMD"}:
                shutil.copy2(trusted, root / "src" / trusted.name)
        main = root / "src/ljs.cpp"
        output = root / "src/output.cpp"
        text = output.read_text()
        if variant in {"wrong_output", "wrong_four_threads", "nonfinite"}:
            value = {"wrong_output": "0.0", "nonfinite": "(0.0/0.0)",
                     "wrong_four_threads": "(neighbor.threads->omp_num_threads == 4 ? 0.0 : thermo.tmparr[i])"}[variant]
            old = "thermo.tmparr[i]);"
            if text.count(old) != 2:
                raise AssertionError("miniMD output adapter needs review")
            text = text.replace(old, value + ");")
        elif variant == "wrong_threads":
            old = '"  threads: %i\\n", neighbor.threads->omp_num_threads'
            if text.count(old) != 2:
                raise AssertionError("miniMD thread adapter needs review")
            text = text.replace(old, '"  threads: %i\\n", 1')
        elif variant == "missing_output":
            call = "output(in, atom, force, neighbor, comm, thermo, integrate, timer, screen_yaml);"
            main.write_text(replace_once(main.read_text(), call, ";"))
        elif variant == "compile_error":
            main.write_text(main.read_text() + "\n#error oracle_self_test_compile_error\n")
        elif variant in {"runtime_error", "hang"}:
            main.write_text(main_entry(main.read_text(), "_Exit(7);" if variant == "runtime_error" else "for (;;) { }"))
        elif variant == "serial":
            for path in (root / "src").glob("*.cpp"):
                path.write_text(re.sub(r"^[ \t]*#pragma omp[^\n]*\n", "", path.read_text(), flags=re.M))
        output.write_text(text)


class PolyBenchValidationTests(OracleTests):
    @classmethod
    def setUpClass(cls):
        require_toolchain("cc")

    def test_control_catalog_covers_every_kernel(self):
        actual = {path.name.removeprefix("polybench_") for path in TASKS.glob("polybench_*")}
        self.assertEqual(actual, set(LOOPS) | SPECIAL)


def polybench_test(task):
    def test(self):
        # Do not count negative controls as useful evidence if the valid
        # OpenMP control cannot first pass the same oracle/toolchain.
        self.check(task, "valid")
        for variant in ("serial", "placeholder", "called_placeholder", "disabled_parallel", "single_thread",
                        "wrong_output", "wrong_four_threads", "missing_output", "compile_error", "runtime_error"):
            with self.subTest(control=variant):
                self.check(task, variant, reject=True)
    return test


for _task in sorted(TASKS.glob("polybench_*")):
    setattr(PolyBenchValidationTests, "test_" + _task.name, polybench_test(_task.name))


class HotspotValidationTests(OracleTests):
    @classmethod
    def setUpClass(cls):
        require_toolchain("c++")

    def test_controls(self):
        self.check("rodinia_hotspot", "valid")
        for variant in ("serial", "placeholder", "called_placeholder", "disabled_parallel", "single_thread",
                        "wrong_output", "wrong_four_threads", "missing_output", "compile_error", "runtime_error"):
            with self.subTest(control=variant):
                self.check("rodinia_hotspot", variant, reject=True)


class MiniMDValidationTests(OracleTests):
    @classmethod
    def setUpClass(cls):
        require_toolchain("c++", mpi=True)

    def test_upstream_is_accepted(self):
        self.check("mantevo_minimd", "valid")

    def test_invalid_controls_are_rejected(self):
        self.check("mantevo_minimd", "valid")
        for variant in ("serial", "wrong_output", "wrong_four_threads", "wrong_threads", "nonfinite", "missing_output", "compile_error", "runtime_error"):
            with self.subTest(control=variant):
                self.check("mantevo_minimd", variant, reject=True)


class OracleGapTests(OracleTests):
    """Regression tests for independently identified oracle weaknesses."""
    def test_polybench_rejects_unused_parallel_region(self):
        require_toolchain("cc")
        self.check("polybench_gesummv", "valid")
        self.check("polybench_gesummv", "placeholder", reject=True)

    def test_hotspot_rejects_unused_parallel_region(self):
        require_toolchain("c++")
        self.check("rodinia_hotspot", "valid")
        self.check("rodinia_hotspot", "placeholder", reject=True)

    def test_minimd_rejects_consistently_wrong_results(self):
        require_toolchain("c++", mpi=True)
        self.check("mantevo_minimd", "valid")
        self.check("mantevo_minimd", "wrong_output", reject=True)

    def test_polybench_oracle_bounds_hanging_programs(self):
        require_toolchain("cc")
        self.check("polybench_gesummv", "valid")
        self.check("polybench_gesummv", "hang", reject=True, timeout=180,
                   environment={"PARALLEL_VALIDATION_TIMEOUT": "1",
                                "PARALLEL_VALIDATION_BUILD_TIMEOUT": "60"})


# Portable infrastructure tests: no native compilation or MPI.
def thermo_output(workers=4):
    return (f"miniMD\n  threads: {workers}\nthermodynamic_output:\n"
            "  timestep: 0\n    T*: 1.44\n    U*: -6.2\n    P*: 0.8\n    Conservation: 1\n"
            "  timestep: 10\n    T*: 1.3\n    U*: -6.1\n    P*: 0.7\n    Conservation: 0.999\n"
            "\ntime:\n  total:\n    time: 0.1\n")


class OracleSupportTests(unittest.TestCase):
    def test_every_control_can_be_instrumented_without_unbalanced_source(self):
        for task in sorted(TASKS.glob("polybench_*")):
            with self.subTest(task=task.name):
                reference = next(path for path in (task / "tests/reference").glob("*.c")
                                 if path.name != "polybench.c")
                original = polybench_control(reference.read_text(), task.name.removeprefix("polybench_"))
                text, sites = instrument(original, r"kernel_\w+")
                self.assertGreater(sites, 0)
                Statements(text)
        original = (TASKS / "rodinia_hotspot/tests/reference/hotspot.cpp").read_text()
        text, sites = instrument(hotspot_control(original), r"single_iteration")
        self.assertEqual(sites, 2)
        Statements(text)
        original = (TASKS / "mantevo_minimd/tests/reference/force_lj.cpp").read_text()
        text, sites = instrument(original, r"compute_(?:original|halfneigh|halfneigh_threaded|fullneigh)")
        self.assertGreater(sites, 0)
        Statements(text)

    def test_collapsed_nest_and_dangling_else_remain_inside_original_statement(self):
        source = """
void kernel_example(int a[8][8]) {
  #pragma omp parallel for collapse(2)
  for (int i=0; i<8; ++i)
    for (int j=0; j<8; ++j)
      if (i) a[i][j]++; else a[i][j]--;
}
"""
        text, sites = instrument(source, r"kernel_\w+")
        self.assertEqual(sites, 1)
        self.assertIn("for (int i=0; i<8; ++i)\n    for", text)
        self.assertIn("if (i) a[i][j]++; else a[i][j]--; }", text)
        Statements(text)

    def test_comments_strings_and_preprocessor_tokens_are_not_code(self):
        source = r'''
#define BOGUS for ( { )
void kernel_example(int *a) {
  const char *message = "for ({not_code};)";
  // for (int k=0; k<4; ++k) { }
  for (int i=0; i<4; ++i) { /* } for (;;) { */ a[i]++; }
}
'''
        _, sites = instrument(source, r"kernel_\w+")
        self.assertEqual(sites, 1)

    def test_empty_loops_and_parallel_regions_outside_kernel_are_not_evidence(self):
        source = """
void dummy(void) { for (int i=0; i<8; ++i) { int a=i; } }
void kernel_example(void) { for (int i=0; i<8; ++i) { ; } }
"""
        with self.assertRaisesRegex(ValidationFailure, "no supported nonempty"):
            instrument(source, r"kernel_\w+")

    def test_report_requires_multiple_workers_at_the_same_loop_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report"
            report.write_text("0 1\n1 2\n")
            with self.assertRaisesRegex(ValidationFailure, "multiple OpenMP workers"):
                require_parallel(report, 2)
            report.write_text("0 1\n1 f\n")
            require_parallel(report, 2)
            report.write_text("0 f\n")
            with self.assertRaisesRegex(ValidationFailure, "incomplete"):
                require_parallel(report, 2)

    def test_copied_hidden_tests_have_a_standalone_helper(self):
        for task in sorted(TASKS.iterdir()):
            helper = task / "tests/parallel_validation.py"
            if not helper.is_symlink():
                continue
            with self.subTest(task=task.name), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "tests"
                shutil.copytree(task / "tests", copied)
                self.assertTrue((copied / helper.name).is_file())
                self.assertFalse((copied / helper.name).is_symlink())
                compile((copied / helper.name).read_text(), str(copied / helper.name), "exec")

    def test_miniMD_rejects_consistently_wrong_temperature_against_reference(self):
        expected = parse_thermo(thermo_output(), 4)
        actual = parse_thermo(thermo_output().replace("T*: 1.44", "T*: 0").replace("T*: 1.3", "T*: 0"), 4)
        with self.assertRaisesRegex(ValidationFailure, "reference mismatch"):
            compare_thermo(actual, expected, "wrong temperature in both worker configurations")

    def test_miniMD_parses_by_field_name_not_print_order(self):
        expected = parse_thermo(thermo_output(), 4)
        reordered = thermo_output().replace("    T*: 1.44\n    U*: -6.2", "    U*: -6.2\n    T*: 1.44")
        self.assertEqual(parse_thermo(reordered, 4), expected)

    def test_miniMD_rejects_missing_duplicate_nonfinite_and_wrong_steps(self):
        output = thermo_output()
        for malformed in (
            output.replace("    P*: 0.8\n", ""),
            output.replace("    P*: 0.8\n", "    P*: 0.8\n    P*: 0.8\n"),
            output.replace("T*: 1.44", "T*: nan"),
            output.replace("T*: 1.44", "T*: inf"),
            output.replace("timestep: 10", "timestep: 9"),
            output.replace("timestep: 10", "timestep: 0"),
            output.replace("threads: 4", "threads: 1"),
        ):
            with self.subTest(output=malformed), self.assertRaises(ValidationFailure):
                parse_thermo(malformed, 4)

    def test_timeout_kills_descendants_that_keep_output_pipe_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('child ready',flush=True); time.sleep(60)"
            parent = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}])"
            result = run_bounded([sys.executable, "-c", parent], cwd=temporary, timeout=0.5)
            self.assertEqual(result.returncode, 124)
            self.assertIn("child ready", result.stdout)
            self.assertIn("validation timeout", result.stderr)

    def test_outer_timeout_cleans_inner_oracles_separate_process_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('nested ready',flush=True); time.sleep(60)"
            inner = (
                "import sys; from benchmark.validation.parallel_validation import run_bounded; "
                "print('oracle ready',flush=True); "
                f"run_bounded([sys.executable,'-c',{child!r}],cwd={temporary!r},timeout=30)"
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
            result = run_bounded([sys.executable, "-c", inner], cwd=temporary, env=env, timeout=2)
            self.assertEqual(result.returncode, 124)
            self.assertIn("oracle ready", result.stdout)
            self.assertIn("validation interrupted", result.stderr)

    def test_evaluator_preserves_failed_command_exit_and_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = BenchmarkEvaluator._run("printf diagnostic >&2; exit 7", Path(temporary))
            self.assertEqual(result.returncode, 7)
            self.assertEqual(result.stderr, "diagnostic")


if __name__ == "__main__":
    unittest.main()

"""Standalone, evaluator-owned correctness oracle for parallelization tasks.

Task-local symlinks are dereferenced when hidden tests are copied into an
evaluation workspace. No third-party Python packages or OpenMP tooling APIs
are required. Instrumentation is used only in a separate diagnostic build.
"""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading


class ValidationFailure(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code if code > 0 else 128 - code


def run_bounded(args, *, cwd, env=None, timeout=30):
    """Capture a command and kill its entire session on timeout, including MPI.

    Return a CompletedProcess even on timeout so evaluator result handling does
    not confuse a timed-out validation with an agent/infrastructure exception.
    """
    with subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, errors="replace",
                          start_new_session=True) as process:
        def kill_group(sig):
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass

        def interrupted(signum, frame):
            raise ValidationFailure(f"validation interrupted by signal {signum}", 128 + signum)

        # An evaluator may wrap this oracle in another bounded command. Give
        # the inner oracle a chance to clean its separate child session before
        # escalating to SIGKILL. Worker threads cannot install signal handlers.
        handlers = {}
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGTERM, signal.SIGINT):
                handlers[sig] = signal.signal(sig, interrupted)
        try:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                kill_group(signal.SIGTERM)
                try:
                    stdout, stderr = process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    kill_group(signal.SIGKILL)
                    stdout, stderr = process.communicate()
                return subprocess.CompletedProcess(
                    args, 124, stdout, stderr + f"\nvalidation timeout after {timeout:g}s\n")
        finally:
            kill_group(signal.SIGKILL)
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def positive_timeout(name, default):
    value = float(os.environ.get(name, default))
    if not math.isfinite(value) or value <= 0:
        raise ValidationFailure(f"{name} must be a finite positive number")
    return value


def checked(args, *, cwd, workers=None, report=None, build=False):
    env = os.environ.copy()
    env.update(OMP_DYNAMIC="FALSE", OMP_THREAD_LIMIT="4")
    if workers is not None:
        env["OMP_NUM_THREADS"] = str(workers)
    env.pop("PARALLEL_VALIDATION_REPORT", None)
    if report is not None:
        report.unlink(missing_ok=True)
        env["PARALLEL_VALIDATION_REPORT"] = str(report)
    timeout = positive_timeout(
        "PARALLEL_VALIDATION_BUILD_TIMEOUT" if build else "PARALLEL_VALIDATION_TIMEOUT",
        240 if build else 30,
    )
    print(f"validation command: {shlex.join(map(str, args))}", file=sys.stderr, flush=True)
    result = run_bounded(list(map(str, args)), cwd=cwd, env=env, timeout=timeout)
    if result.returncode:
        raise ValidationFailure(
            f"command failed ({result.returncode}, workers={workers}):\n"
            + result.stdout[-4000:] + result.stderr[-4000:], result.returncode)
    return result


# Keep string/comment lengths unchanged so insertions use original offsets.
# Preprocessor directives (including continuation lines) are also masked: their
# tokens must never be interpreted as C statements or brace delimiters.
LEXICAL = re.compile(
    r"//[^\n]*|/\*[\s\S]*?\*/|\"(?:\\[\s\S]|[^\"\\])*\"|'(?:\\[\s\S]|[^'\\])*'"
    r"|^[ \t]*\#(?:[^\n\\]|\\[^\n]|\\\n)*", re.M)


def code_tokens(source):
    masked = LEXICAL.sub(lambda match: re.sub(r"[^\n]", " ", match[0]), source)
    return list(re.finditer(r"[A-Za-z_]\w*|[^\s]", masked))


class Statements:
    """Locate statement boundaries in the benchmark's C/C++ loop subset.

    This is deliberately not a compiler frontend. Unsupported/ambiguous syntax
    fails closed; it must not silently produce evidence of parallel execution.
    The compiler still validates the instrumented translation unit afterwards.
    """
    def __init__(self, source):
        self.tokens = code_tokens(source)
        self.words = [token[0] for token in self.tokens]
        self.pairs = {}
        stack = []
        for index, word in enumerate(self.words):
            if word in ("(", "[", "{"):
                stack.append(index)
            elif word in (")", "]", "}"):
                if not stack or self.words[stack[-1]] != {")": "(", "]": "[", "}": "{"}[word]:
                    raise ValidationFailure("unsupported unbalanced source in kernel instrumentation")
                start = stack.pop()
                self.pairs[start] = index
        if stack:
            raise ValidationFailure("unsupported unbalanced source in kernel instrumentation")

    def end(self, start):
        words = self.words
        word = words[start]
        if word == "{":
            return self.pairs[start] + 1
        if word in ("for", "while", "switch", "if"):
            opening = start + 1
            if words[opening] != "(":
                raise ValidationFailure(f"unsupported {word} syntax in kernel")
            end = self.end(self.pairs[opening] + 1)
            if word == "if" and end < len(words) and words[end] == "else":
                end = self.end(end + 1)
            return end
        if word == "do":
            end = self.end(start + 1)
            if words[end:end + 2] != ["while", "("]:
                raise ValidationFailure("unsupported do/while syntax in kernel")
            end = self.pairs[end + 1] + 1
            if words[end] != ";":
                raise ValidationFailure("missing do/while terminator")
            return end + 1
        index = start
        while index < len(words):
            if words[index] == ";":
                return index + 1
            if words[index] in ("(", "[", "{"):
                index = self.pairs[index] + 1
            elif words[index] == "}":
                break
            else:
                index += 1
        raise ValidationFailure("unsupported loop body in kernel instrumentation")

    def functions(self, pattern):
        ranges = []
        for index, word in enumerate(self.words[:-1]):
            if re.fullmatch(pattern, word) and self.words[index + 1] == "(":
                closing = self.pairs[index + 1]
                if closing + 1 < len(self.words) and self.words[closing + 1] == "{":
                    start = closing + 1
                    ranges.append((start + 1, self.pairs[start]))
        return ranges


def instrument(source, function_pattern):
    """Record distinct team workers at nonempty innermost kernel loop sites.

    Keeping enclosing loop nests untouched preserves OpenMP collapse syntax.
    A worker is recorded only while executing an iteration in an active team.
    Empty regions outside the kernel, initialization and print routines cannot
    satisfy this requirement. This is execution evidence, not a race detector
    or a proof against deliberately adversarial source transformations.
    """
    statements = Statements(source)
    words, tokens = statements.words, statements.tokens
    ranges = statements.functions(function_pattern)
    if not ranges:
        raise ValidationFailure(f"cannot locate computational kernel: {function_pattern}")
    edits = []
    sites = 0
    for lower, upper in ranges:
        for index in range(lower, upper):
            if words[index] != "for":
                continue
            if words[index + 1] != "(":
                raise ValidationFailure("unsupported kernel loop syntax")
            body = statements.pairs[index + 1] + 1
            end = statements.end(body)
            if end > upper:
                raise ValidationFailure("kernel loop extends outside function")
            # Leave all enclosing loops intact, including perfectly nested
            # collapse(n) loops and vectorization directives on inner loops.
            if any(word in ("for", "while", "do") for word in words[body:end]):
                continue
            content = words[body:end]
            if not any(word in ("=", "+", "-", "*", "/", "(") for word in content):
                continue
            hit = f" pv_hit({sites}); "
            if words[body] == "{":
                edits.append((tokens[body].end(), hit))
            else:
                edits.extend(((tokens[body].start(), "{ " + hit),
                              (tokens[end - 1].end(), " }")))
            sites += 1
    if not sites:
        raise ValidationFailure("no supported nonempty computational loop to instrument")
    for offset, insertion in sorted(edits, reverse=True):
        source = source[:offset] + insertion + source[offset:]
    preamble = r'''
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef __cplusplus
#define PV_TLS thread_local
#else
#define PV_TLS _Thread_local
#endif
static unsigned long long pv_workers[PV_SITES];
static PV_TLS unsigned char pv_seen[PV_SITES];
static void pv_hit(unsigned int site) {
  if (pv_seen[site]) return;
  if (!omp_in_parallel() || omp_get_num_threads() < 2) return;
  int worker = omp_get_thread_num();
  if (worker < 0 || worker >= 64) return;
  pv_seen[site] = 1;
  __atomic_fetch_or(&pv_workers[site], 1ULL << worker, __ATOMIC_RELAXED);
}
static void pv_report(void) {
  const char *path = getenv("PARALLEL_VALIDATION_REPORT");
  if (!path) return;
  FILE *file = fopen(path, "w");
  if (!file) return;
  for (unsigned int site = 0; site < PV_SITES; ++site)
    fprintf(file, "%u %llx\n", site, pv_workers[site]);
  fclose(file);
}
__attribute__((constructor)) static void pv_init(void) { atexit(pv_report); }
'''
    return f"#define PV_SITES {sites}\n" + preamble + "\n" + source, sites


def require_parallel(report, sites):
    if not report.is_file():
        raise ValidationFailure("missing kernel execution report")
    rows = report.read_text().splitlines()
    if len(rows) != sites:
        raise ValidationFailure("incomplete kernel execution report")
    masks = []
    for expected, row in enumerate(rows):
        fields = row.split()
        if len(fields) != 2 or fields[0] != str(expected):
            raise ValidationFailure("invalid kernel execution report")
        try:
            masks.append(int(fields[1], 16))
        except ValueError as error:
            raise ValidationFailure("invalid kernel worker mask") from error
    if not any(mask > 0 and mask & (mask - 1) for mask in masks):
        raise ValidationFailure("no computational loop site executed by multiple OpenMP workers")
    print("parallel execution: multiple workers executed a computational loop", file=sys.stderr)


def omp_flags():
    if sys.platform == "darwin":
        prefix = next((path for path in (Path("/opt/homebrew/opt/libomp"),
                                        Path("/usr/local/opt/libomp")) if path.is_dir()), None)
        if prefix is None:
            raise ValidationFailure("libomp is required on macOS")
        return ["-Xpreprocessor", "-fopenmp", f"-I{prefix / 'include'}",
                f"-L{prefix / 'lib'}", "-lomp"]
    return ["-fopenmp"]


def compare_bytes(actual, expected, label):
    print(f"output comparison: {label}", file=sys.stderr)
    if not actual or not expected:
        raise ValidationFailure(f"missing output: {label}")
    if actual != expected:
        raise ValidationFailure(f"output differs from reference: {label}")


def validate_polybench(root, work):
    trusted = root / "tests/reference"
    kernels = [path for path in trusted.glob("*.c") if path.name != "polybench.c"]
    if len(kernels) != 1:
        raise ValidationFailure("expected exactly one trusted PolyBench kernel")
    kernel = kernels[0]
    source = root / "src" / kernel.name
    compiler = shlex.split(os.environ.get("CC") or "cc")
    common = ["-O3", "-std=c11", "-D_POSIX_C_SOURCE=200112L", "-D_XOPEN_SOURCE=600",
              "-DMEDIUM_DATASET" if kernel.stem == "gemm" else "-DSMALL_DATASET",
              "-DPOLYBENCH_DUMP_ARRAYS"]

    def build(path, support, output, parallel):
        checked([*compiler, *common, *(omp_flags() if parallel else ()),
                 f"-I{path.parent}", path, support, "-lm", "-o", output], cwd=root, build=True)

    # Compile and validate the real source before requesting instrumentation.
    build(source, source.parent / "polybench.c", work / "candidate", True)
    build(kernel, trusted / "polybench.c", work / "reference", False)
    reference = checked([work / "reference"], cwd=work).stderr
    for workers in (1, 4):
        result = checked([work / "candidate"], cwd=work, workers=workers)
        compare_bytes(result.stderr, reference, f"candidate workers={workers}")
    text, sites = instrument(source.read_text(), r"kernel_\w+")
    diagnostic = work / source.name
    diagnostic.write_text(text)
    # The diagnostic source lives outside src; headers still come from src.
    checked([*compiler, *common, *omp_flags(), f"-I{source.parent}", diagnostic,
             source.parent / "polybench.c", "-lm", "-o", work / "diagnostic"], cwd=root, build=True)
    report = work / "workers.txt"
    result = checked([work / "diagnostic"], cwd=work, workers=4, report=report)
    compare_bytes(result.stderr, reference, "diagnostic workers=4")
    require_parallel(report, sites)


def validate_hotspot(root, work):
    source = root / "src/hotspot.cpp"
    reference = root / "tests/reference/hotspot.cpp"
    compiler = shlex.split(os.environ.get("CXX") or "c++")
    for path, name in ((source, "candidate"), (reference, "reference")):
        checked([*compiler, "-O3", *omp_flags(), path, "-o", work / name], cwd=root, build=True)

    def execute(binary, size, workers, report=None):
        output = work / "temperature.out"
        output.unlink(missing_ok=True)
        checked([binary, size, size, 2, workers, root / f"input/temp_{size}",
                 root / f"input/power_{size}", output], cwd=work, workers=workers, report=report)
        return output.read_bytes() if output.is_file() else b""

    references = {}
    for size in (64, 128):
        references[size] = execute(work / "reference", size, 1)
        for workers in (1, 4):
            compare_bytes(execute(work / "candidate", size, workers), references[size],
                          f"candidate size={size} workers={workers}")
    text, sites = instrument(source.read_text(), r"single_iteration")
    diagnostic = work / "hotspot.cpp"
    diagnostic.write_text(text)
    checked([*compiler, "-O3", *omp_flags(), f"-I{source.parent}", diagnostic,
             "-o", work / "diagnostic"], cwd=root, build=True)
    for size in (64, 128):
        report = work / "workers.txt"
        compare_bytes(execute(work / "diagnostic", size, 4, report), references[size],
                      f"diagnostic size={size} workers=4")
        require_parallel(report, sites)


THERMO_FIELDS = ("T*", "U*", "P*", "Conservation")


def parse_thermo(output, workers):
    if "minimd" not in output.lower() or "thermodynamic_output:" not in output:
        raise ValidationFailure("missing miniMD banner or thermodynamic output")
    counts = re.findall(r"^\s*threads:\s*(\d+)\s*$", output, re.M)
    if not counts or any(int(value) != workers for value in counts):
        raise ValidationFailure(f"miniMD did not report {workers} thread(s)")
    section = output.split("thermodynamic_output:", 1)[1].split("\ntime:", 1)[0]
    values = {}
    step = None
    for line in section.splitlines():
        match = re.fullmatch(r"\s*timestep:\s*(\d+)\s*", line)
        if match:
            step = int(match[1])
            if step in values:
                raise ValidationFailure(f"duplicate miniMD timestep {step}")
            values[step] = {}
            continue
        match = re.fullmatch(r"\s*(T\*|U\*|P\*|Conservation):\s*(\S+)\s*", line)
        if not match:
            continue
        if step is None or match[1] in values[step]:
            raise ValidationFailure("misplaced or duplicate miniMD thermodynamic field")
        try:
            value = float(match[2])
        except ValueError as error:
            raise ValidationFailure("invalid miniMD thermodynamic value") from error
        if not math.isfinite(value):
            raise ValidationFailure("non-finite miniMD thermodynamic value")
        values[step][match[1]] = value
    # -n 10 with the trusted input's thermo interval 100 emits start and end.
    if set(values) != {0, 10} or any(set(row) != set(THERMO_FIELDS) for row in values.values()):
        raise ValidationFailure("miniMD requires all thermodynamic fields at timesteps 0 and 10")
    return values


def compare_thermo(actual, expected, label):
    print(f"output comparison: {label}", file=sys.stderr)
    if actual.keys() != expected.keys():
        raise ValidationFailure(f"miniMD timestep mismatch: {label}")
    for step, fields in expected.items():
        for name, value in fields.items():
            if abs(actual[step][name] - value) > 1e-7 + 1e-7 * abs(value):
                raise ValidationFailure(
                    f"miniMD reference mismatch ({label}, timestep={step}, {name}): "
                    f"candidate={actual[step][name]}, reference={value}")


def validate_minimd(root, work):
    trusted = root / "tests/reference"
    reference = work / "reference"
    shutil.copytree(trusted, reference)
    checked(["make", "-f", "Makefile.default", "copy", "CC=mpicxx", "LINK=mpicxx"],
            cwd=reference, build=True)
    input_path = reference / "in.lj.miniMD"

    def execute(binary, workers, report=None):
        result = checked(["mpirun", "-np", "1", binary, "-i", input_path, "-n", "10",
                          "-t", workers, "-o", "1", "--yaml_screen"],
                         cwd=work, workers=workers, report=report)
        return parse_thermo(result.stdout, workers)

    expected = execute(reference / "miniMD", 1)
    for workers in (1, 4):
        compare_thermo(execute(root / "src/miniMD", workers), expected,
                       f"candidate workers={workers}")
    # Probe only the Lennard-Jones force kernel, excluding setup and output.
    diagnostic = work / "diagnostic"
    shutil.copytree(root / "src", diagnostic, ignore=shutil.ignore_patterns(
        "Obj_*", "miniMD", "*.o", "*.2.cpp"))
    kernel = diagnostic / "force_lj.cpp"
    text, sites = instrument(kernel.read_text(), r"compute_(?:original|halfneigh|halfneigh_threaded|fullneigh)")
    kernel.write_text(text)
    checked(["make", "-f", "Makefile.default", "copy", "CC=mpicxx", "LINK=mpicxx"],
            cwd=diagnostic, build=True)
    report = work / "workers.txt"
    compare_thermo(execute(diagnostic / "miniMD", 4, report), expected, "diagnostic workers=4")
    require_parallel(report, sites)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", choices=("polybench", "hotspot", "minimd"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="parallel-validation-") as temporary:
            {"polybench": validate_polybench, "hotspot": validate_hotspot,
             "minimd": validate_minimd}[args.family](args.root.resolve(), Path(temporary))
    except (ValidationFailure, OSError, ValueError) as error:
        print(f"parallel validation failed: {error}", file=sys.stderr)
        return error.code if isinstance(error, ValidationFailure) else 1
    print(f"{args.family}: reference output and parallel kernel execution validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Evaluator-owned builds and paired performance measurements for parallel tasks.

The hidden tests/performance.json selects sources and bounded workloads. No
candidate Makefile or candidate-built executable is used. PolyBench reports
both a trusted monotonic kernel timer and complete process latency; other
applications report process latency only. Correctness remains a separate gate.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import re
import shlex
import signal
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

if __package__:
    from .performance_repair import bootstrap_interval
else:
    from performance_repair import bootstrap_interval

ROUNDS = 15
TARGET_SECONDS = 0.1
MAX_BATCH = 20
TIMEOUT = 30

TIMER = r'''
#include <stdio.h>
#include <time.h>
static struct timespec started, finished;
void polybench_timer_start(void) { clock_gettime(CLOCK_MONOTONIC, &started); }
void polybench_timer_stop(void) { clock_gettime(CLOCK_MONOTONIC, &finished); }
void polybench_timer_print(void) {
  double seconds = (finished.tv_sec - started.tv_sec)
    + (finished.tv_nsec - started.tv_nsec) * 1e-9;
  printf("BENCHMARK_KERNEL_SECONDS=%.9f\n", seconds);
}
'''

# Validation binaries buffer their normal stderr dump. Hashing happens in Python,
# without replacing stdio symbols or retaining the complete output in memory.
VALIDATION_BUFFER = r'''
#include <stdio.h>
static char output_buffer[65536];
__attribute__((constructor)) static void buffer_validation_output(void) {
  setvbuf(stderr, output_buffer, _IOFBF, sizeof(output_buffer));
}
'''


def output_digest(args, *, cwd, env, timeout=TIMEOUT):
    """Hash real stderr bytes with bounded memory and a process-group timeout."""
    digest = hashlib.sha256()
    state = {"bytes": 0, "tail": b"", "error": None}
    with subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.DEVNULL,
                          stderr=subprocess.PIPE, bufsize=0, start_new_session=True) as process:
        def read_output():
            try:
                while chunk := process.stderr.read(65536):
                    digest.update(chunk)
                    state["bytes"] += len(chunk)
                    state["tail"] = (state["tail"] + chunk)[-2000:]
            except Exception as error:
                state["error"] = error

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            reader.join(timeout=5)
            raise RuntimeError("PolyBench output validation timed out") from error
        reader.join(timeout=5)
        if reader.is_alive():
            # A descendant can keep the pipe open after the main process exits.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            reader.join(timeout=5)
            raise RuntimeError("PolyBench output validation stream did not close")
        if state["error"] is not None:
            raise RuntimeError(f"could not read PolyBench validation output: {state['error']}")
        if process.returncode:
            detail = state["tail"].decode("utf-8", errors="replace")
            raise RuntimeError(f"PolyBench validation exited {process.returncode}: {detail}")
    if not state["bytes"]:
        raise RuntimeError("empty PolyBench array dump during output validation")
    return digest.hexdigest(), state["bytes"]


def command(args, *, cwd=None, env=None, timeout=TIMEOUT):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                            text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {shlex.join(args)}\n"
                           + result.stdout + result.stderr)
    return result


def omp_flags():
    if platform.system() != "Darwin":
        return ["-fopenmp"]
    for prefix in (Path("/opt/homebrew/opt/libomp"), Path("/usr/local/opt/libomp")):
        if (prefix / "include/omp.h").exists():
            return ["-Xpreprocessor", "-fopenmp", f"-I{prefix / 'include'}",
                    f"-L{prefix / 'lib'}", "-lomp"]
    raise RuntimeError("libomp is required for controlled OpenMP performance builds")


def environment(workers):
    env = os.environ.copy()
    # Neutralize inherited runtime limits/affinity that conflict with this run.
    for key in ("GOMP_CPU_AFFINITY", "KMP_AFFINITY"):
        env.pop(key, None)
    env.update(OMP_NUM_THREADS=str(workers), OMP_THREAD_LIMIT=str(workers),
               OMP_DYNAMIC="FALSE", OMP_MAX_ACTIVE_LEVELS="1",
               OMP_PROC_BIND="close", OMP_PLACES="cores",
               OMPI_MCA_hwloc_base_binding_policy="none")
    return env


def select_cpus(allowed):
    """Prefer four different physical cores inside the inherited CPU allowance."""
    if not allowed:
        return None
    cores = {}
    try:
        for cpu in allowed:
            topology = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
            key = ((topology / "physical_package_id").read_text().strip(),
                   (topology / "core_id").read_text().strip())
            cores.setdefault(key, cpu)
        if len(cores) >= 4:
            return list(cores.values())[:4]
    except OSError:
        pass
    return allowed[:4]


def comparisons(samples, pairs):
    result = []
    for label, numerator, denominator, direction in pairs:
        ratios = [a / b for a, b in zip(samples[numerator], samples[denominator])]
        interval = bootstrap_interval(ratios)
        result.append(dict(label=label, numerator=numerator, denominator=denominator,
                           ratio=statistics.median(ratios), direction=direction,
                           confidence_interval_95=interval, paired_ratios=ratios,
                           evidence=("above_one" if interval[0] > 1 else
                                     "below_one" if interval[1] < 1 else "inconclusive")))
    return result


class Experiment:
    def __init__(self, root, reference, work, config):
        self.root, self.reference, self.work, self.config = root, reference, work, config
        self.kind = config["kind"]
        self.compiler = shlex.split(os.environ.get("CXX" if self.kind != "polybench" else "CC",
                                                   "mpicxx" if self.kind == "minimd" else
                                                   "c++" if self.kind == "hotspot" else "cc"))
        if self.kind == "minimd":
            self.compiler = shlex.split(os.environ.get("MPICXX", "mpicxx"))
        self.flags = ["-O3", *omp_flags()]
        self.build_commands = []
        self.build_cache = {}
        self.affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
        self.cpu_set = select_cpus(self.affinity)
        if self.cpu_set and len(self.cpu_set) < 4:
            raise RuntimeError("performance comparison requires at least four allowed logical CPUs")

    def compile(self, args, cwd=None):
        self.build_commands.append(args)
        command(args, cwd=cwd, timeout=180)

    def invocation(self, executable, workers, workload):
        args = [str(executable)]
        if self.kind == "hotspot":
            inputs = self.reference / "input"
            args += ["512", "512", str(workload["iterations"]), str(workers),
                     str(inputs / "temp_512"), str(inputs / "power_512"),
                     str(self.work / "hotspot-output")]
        elif self.kind == "minimd":
            args = ["mpirun", "-np", "1", *args, "-i",
                    str(self.reference / "src/in.lj.miniMD"), "-n", str(workload["iterations"]),
                    "-t", str(workers), "-o", "1", "--yaml_screen"]
        if self.cpu_set and shutil.which("taskset"):
            args = ["taskset", "--cpu-list", ",".join(map(str, self.cpu_set)), *args]
        return args

    def run(self, executable, workers, workload):
        args = self.invocation(executable, workers, workload)
        start = time.perf_counter_ns()
        process = command(args, cwd=self.work, env=environment(workers))
        wall = (time.perf_counter_ns() - start) / 1e9
        kernel = None
        if self.kind == "polybench":
            matches = re.findall(r"^BENCHMARK_KERNEL_SECONDS=([0-9.eE+-]+)$",
                                 process.stdout, re.MULTILINE)
            if len(matches) != 1:
                raise RuntimeError("missing or ambiguous trusted PolyBench kernel timer")
            kernel = float(matches[0])
            if not math.isfinite(kernel) or kernel <= 0 or kernel > wall:
                raise RuntimeError("invalid PolyBench kernel timing")
        elif self.kind == "minimd":
            counts = re.findall(r"^\s*threads:\s*(\d+)\s*$", process.stdout, re.M)
            if not counts or any(int(value) != workers for value in counts):
                raise RuntimeError("miniMD did not confirm the requested OpenMP worker count")
        return wall, kernel, process.stdout

    def build(self, candidate, workload, validation=False):
        key = (candidate, json.dumps(workload, sort_keys=True), validation)
        if key in self.build_cache:
            return self.build_cache[key]
        directory = self.work / f"build-{len(self.build_cache)}"
        directory.mkdir()
        source = self.root if candidate else self.reference
        executable = directory / "program"
        flags = list(self.flags)
        if self.kind == "polybench":
            trusted = self.root / "tests/reference"
            header = trusted / self.config["header"]
            common = ["-std=c11", "-D_POSIX_C_SOURCE=200112L", "-DSMALL_DATASET",
                      "-DPOLYBENCH_TIME", "-DPOLYBENCH_NO_FLUSH_CACHE",
                      *[f"-D{name}={value}" for name, value in workload["dimensions"].items()],
                      "-include", str(trusted / "polybench.h"), "-include", str(header),
                      f"-I{trusted}"]
            extra_sources = []
            if validation:
                common += ["-DPOLYBENCH_DUMP_ARRAYS"]
                buffer = directory / "validation_buffer.c"
                buffer.write_text(VALIDATION_BUFFER)
                extra_sources.append(str(buffer))
            # Use the original trusted support code for allocation. Rename its
            # timers so the evaluator's monotonic implementation owns timing.
            support = directory / "support.o"
            renames = [f"-Dpolybench_timer_{name}=upstream_timer_{name}"
                       for name in ("start", "stop", "print")]
            self.compile([*self.compiler, *flags, *common, *renames, "-c",
                          str(trusted / "polybench.c"), "-o", str(support)])
            timer = directory / "timer.c"
            timer.write_text(TIMER)
            kernel = (self.root / "src" if candidate else trusted) / self.config["source"]
            self.compile([*self.compiler, *flags, *common, str(kernel), str(support),
                          str(timer), *extra_sources, "-lm", "-o", str(executable)])
        elif self.kind == "hotspot":
            kernel = (self.root / "src" if candidate else self.root / "tests/reference") / "hotspot.cpp"
            self.compile([*self.compiler, *flags, str(kernel), "-o", str(executable)])
        else:
            flags += ["-DMPICH_IGNORE_CXX_SEEK", "-DDEVICE=1", "-DUSE_SIMD", "-DNOCHUNK", "-mavx"]
            src = source / "src"
            objects = []
            # Match upstream Makefile.default's two-pass build. OMPFORSCHEDULE
            # expands to a literal #pragma; it becomes a directive only when
            # the preprocessed .2.cpp is compiled in a second invocation.
            # Build both sides this way, without modifying either source tree.
            for index, name in enumerate(self.config["sources"]):
                preprocessed = directory / f"{index}-{Path(name).stem}.2.cpp"
                obj = directory / f"{index}-{Path(name).stem}.o"
                self.compile([*self.compiler, *flags, f"-I{src}", "-E",
                              str(src / name), "-o", str(preprocessed)])
                self.compile([*self.compiler, *flags, f"-I{src}", "-c",
                              str(preprocessed), "-o", str(obj)])
                objects.append(str(obj))
            self.compile([*self.compiler, *flags, *objects, "-o", str(executable)])
        self.build_cache[key] = executable
        return executable

    def probe_threads(self):
        source = self.work / "threads.c"
        source.write_text('#include <stdio.h>\n#include <omp.h>\nint main(void) {\n'
                          'int n=0;\n#pragma omp parallel reduction(max:n)\n'
                          '{ n=omp_get_num_threads(); }\nprintf("%d\\n",n);\n}\n')
        executable = self.work / "threads"
        compiler = shlex.split(os.environ.get("CC", "cc"))
        self.compile([*compiler, *self.flags, str(source), "-o", str(executable)])
        observed = {}
        for workers in (1, 4):
            actual = int(command([str(executable)], env=environment(workers)).stdout.strip())
            observed[str(workers)] = actual
            if actual != workers:
                raise RuntimeError(f"OpenMP runtime created {actual} threads, requested {workers}")
        return observed

    def plan(self):
        # Share one reference-calibrated workload across modes of the same case.
        path = self.root.parent.parent / "parallel_performance_plan.json"
        fingerprint = hashlib.sha256(json.dumps(self.config, sort_keys=True).encode()).hexdigest()
        if path.exists():
            saved = json.loads(path.read_text())
            if saved.get("config_sha256") != fingerprint:
                raise RuntimeError("shared performance plan does not match task specification")
            return saved
        small = self.config["small_workload"]
        selected, elapsed = small, 0.0
        calibration = []
        for workload in self.config["calibration_workloads"]:
            binary = self.build(False, workload)
            timings = [self.run(binary, 1, workload) for _ in range(2)]
            elapsed = statistics.median(item[1] if item[1] is not None else item[0] for item in timings)
            calibration.append(dict(workload=workload, seconds=elapsed))
            selected = workload
            if elapsed >= TARGET_SECONDS:
                break
        saved = dict(config_sha256=fingerprint, target_seconds=TARGET_SECONDS,
                     target_reached=elapsed >= TARGET_SECONDS, calibration=calibration,
                     workloads=[dict(label="small", parameters=small),
                                dict(label="performance", parameters=selected)])
        pending = path.with_suffix(".tmp")
        pending.write_text(json.dumps(saved, indent=2) + "\n")
        pending.replace(path)
        return saved

    def validate(self, workload):
        controls = []
        for candidate, workers in ((False, 1), (True, 1), (True, 4)):
            binary = self.build(candidate, workload, validation=self.kind == "polybench")
            if self.kind == "polybench":
                side = "candidate" if candidate else "reference"
                try:
                    controls.append(output_digest(self.invocation(binary, workers, workload),
                                                  cwd=self.work, env=environment(workers)))
                except RuntimeError as error:
                    raise RuntimeError(f"{side}, workers={workers}, workload={workload}: {error}") from error
                continue
            stdout = self.run(binary, workers, workload)[2]
            if self.kind == "hotspot":
                output = self.work / "hotspot-output"
                if not output.is_file() or not output.stat().st_size:
                    raise RuntimeError("Hotspot did not produce validation output")
                controls.append(hashlib.sha256(output.read_bytes()).hexdigest())
                output.unlink()
            else:
                values = [float(value) for value in re.findall(
                    r"^\s*(?:T\*|U\*|P\*|Conservation):\s*(\S+)", stdout, re.M)]
                if not values or not all(math.isfinite(value) for value in values):
                    raise RuntimeError("missing or non-finite miniMD thermodynamic validation output")
                controls.append(values)
        for candidate in controls[1:]:
            if self.kind == "minimd":
                equal = len(candidate) == len(controls[0]) and all(
                    math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-7)
                    for a, b in zip(candidate, controls[0]))
            else:
                equal = candidate == controls[0]
            if not equal:
                raise RuntimeError("candidate output differs from reference at performance workload")
        return dict(passed=True, workers=[1, 4],
                    method={"polybench": "formatted_array_dump_sha256_and_byte_count",
                            "hotspot": "output_file_sha256", "minimd": "thermodynamic_values_tolerance_1e-7"}[self.kind])

    def measure(self, workload):
        validation = self.validate(workload)
        reference, candidate = self.build(False, workload), self.build(True, workload)
        configs = [("upstream_serial_reference" if self.kind != "minimd" else "upstream_reference", reference, 1),
                   ("candidate", candidate, 1), ("candidate", candidate, 4)]
        if self.kind == "minimd":
            configs.insert(1, ("upstream_reference", reference, 4))
        ids = [f"{label}_{workers}_worker" for label, _, workers in configs]
        # Independent process warmups warm pages/files, not a persistent OpenMP team.
        for _, binary, workers in configs:
            for _ in range(2):
                self.run(binary, workers, workload)
        wall, kernel, _ = self.run(reference, 1, workload)
        batch = min(MAX_BATCH, max(1, math.ceil(TARGET_SECONDS / wall)))
        metrics = {"end_to_end_wall_time_seconds": {key: [] for key in ids}}
        if kernel is not None:
            metrics["kernel_wall_time_seconds"] = {key: [] for key in ids}
        rng = random.Random(20261112)
        orders = []
        for _ in range(ROUNDS):
            order = list(range(len(configs)))
            rng.shuffle(order)
            orders.append([ids[index] for index in order])
            for index in order:
                _, binary, workers = configs[index]
                observations = [self.run(binary, workers, workload) for _ in range(batch)]
                metrics["end_to_end_wall_time_seconds"][ids[index]].append(
                    statistics.mean(item[0] for item in observations))
                if kernel is not None:
                    metrics["kernel_wall_time_seconds"][ids[index]].append(
                        statistics.mean(item[1] for item in observations))
        baseline = ids[0]
        pairs = [("candidate_1_worker_vs_serial_reference", baseline, "candidate_1_worker", "higher_is_faster"),
                 ("candidate_4_workers_vs_serial_reference", baseline, "candidate_4_worker", "higher_is_faster"),
                 ("candidate_scaling_1_to_4_workers", "candidate_1_worker", "candidate_4_worker", "higher_is_better_scaling")]
        if self.kind == "minimd":
            pairs = [("candidate_vs_reference_1_worker", baseline, "candidate_1_worker", "higher_is_faster"),
                     ("candidate_vs_reference_4_workers", ids[1], "candidate_4_worker", "higher_is_faster"),
                     ("reference_scaling_1_to_4_workers", baseline, ids[1], "higher_is_better_scaling"),
                     pairs[-1]]
        reports = []
        for metric, samples in metrics.items():
            reports.append(dict(metric=metric, unit="seconds", measurements=[
                dict(id=key, label=label, workers=workers, samples=samples[key],
                     median=statistics.median(samples[key]))
                for key, (label, _, workers) in zip(ids, configs)],
                comparisons=comparisons(samples, pairs)))
        return dict(parameters=workload, validation=validation,
                    batch_invocations=batch, round_order=orders, metrics=reports)


def measure(root):
    config = json.loads((root / "tests/performance.json").read_text())
    reference = Path(os.environ["BENCHMARK_REFERENCE_WORKSPACE"]).resolve()
    with tempfile.TemporaryDirectory(prefix="parallel-performance-") as temporary:
        experiment = Experiment(root, reference, Path(temporary), config)
        observed = experiment.probe_threads()
        plan = experiment.plan()
        workloads = []
        for item in plan["workloads"]:
            measured = experiment.measure(item["parameters"])
            workloads.append(dict(label=item["label"], **measured))
        primary = workloads[-1]["metrics"][0]
        return dict(schema_version=1, methodology="paired_rounds_v1", repetitions=ROUNDS,
                    warmup_invocations=2, ratio_method="median_of_paired_round_ratios",
                    confidence_method="paired_percentile_bootstrap_2000_draws",
                    **primary, workloads=workloads, calibration=plan,
                    compiler=command([*experiment.compiler, "--version"]).stdout.splitlines()[0],
                    build_flags=experiment.flags, build_commands=experiment.build_commands,
                    environment={key: value for key, value in environment(4).items()
                                 if key.startswith("OMP_") or key == "OMPI_MCA_hwloc_base_binding_policy"},
                    runtime_probe_threads=observed, allowed_cpus=experiment.affinity,
                    process_cpu_set=experiment.cpu_set if shutil.which("taskset") else None,
                    machine=dict(system=platform.platform(), architecture=platform.machine()),
                    kernel_timing=("trusted_monotonic_polybench_timer_no_cache_flush" if experiment.kind == "polybench"
                                   else "unavailable: application timer is not evaluator-controlled"),
                    performance_workload_correctness="validated against reference at both measured workloads")


if __name__ == "__main__":
    try:
        print(json.dumps(measure(Path(sys.argv[1]).resolve())))
    except Exception as error:
        print(f"Parallel performance measurement failed: {error}", file=sys.stderr)
        sys.exit(1)

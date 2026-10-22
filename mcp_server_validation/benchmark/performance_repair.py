"""Measure repaired OpenMP task latency against its hidden official reference.

This is an end-to-end process latency metric. DataRaceBench cases are too small
for it to be interpreted as isolated kernel performance.
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROUNDS = 9
MIN_BATCH_SECONDS = 0.15
MAX_BATCH_INVOCATIONS = 100
MIN_PERFORMANCE_RATIO = 0.90
BOOTSTRAP_DRAWS = 2000


def compile_binary(command: list[str], root: Path) -> None:
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("compilation failed: " + result.stderr[-3000:])


def build(root: Path, config: dict, directory: Path) -> tuple[Path, Path]:
    compiler = os.environ.get("CC", "gcc")
    candidate = directory / "candidate"
    reference = directory / "reference"
    flags = ["-std=c11", "-O2", "-fopenmp"]
    source = str(root / config["candidate"])
    official = str(root / config["reference"])
    kind = config.get("kind", "drb")

    if kind == "ompscr":
        support = [str(root / "src/common/ompscrCommon.c"),
                   str(root / "src/common/wtime.c")]
        official_support = [
            str(root / "tests/reference/common/ompscrCommon.c"),
            str(root / "tests/reference/common/wtime.c"),
        ]
        compile_binary([compiler, *flags, "-Isrc/include", "-Isrc/common",
                        source, *support, "-lm", "-o", str(candidate)], root)
        compile_binary([compiler, *flags, "-Itests/reference/include",
                        official, *official_support, "-lm", "-o", str(reference)], root)
    else:
        compile_binary([compiler, *flags, source, "-lm", "-o", str(candidate)], root)
        if config.get("reference_driver"):
            obj = directory / "reference.o"
            compile_binary([compiler, *flags, "-Dmain=official_reference_main",
                            "-c", official, "-o", str(obj)], root)
            compile_binary([compiler, *flags, str(root / config["reference_driver"]),
                            str(obj), "-lm", "-o", str(reference)], root)
        else:
            compile_binary([compiler, *flags, official, "-lm", "-o",
                            str(reference)], root)
    return candidate, reference


def timed_batch(executable: Path, args: list[str], count: int, env: dict) -> float:
    start = time.perf_counter_ns()
    for _ in range(count):
        result = subprocess.run(
            [str(executable), *args], stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, env=env, timeout=15,
        )
        if result.returncode:
            message = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"{executable.name} exited {result.returncode}: {message[-1000:]}")
    return (time.perf_counter_ns() - start) / 1e9 / count


def bootstrap_interval(paired_ratios: list[float]) -> list[float]:
    rng = random.Random(20261022)
    n = len(paired_ratios)
    ratios = []
    for _ in range(BOOTSTRAP_DRAWS):
        ratios.append(statistics.median(
            paired_ratios[rng.randrange(n)] for _ in range(n)
        ))
    ratios.sort()
    return [ratios[int(0.025 * (BOOTSTRAP_DRAWS - 1))],
            ratios[int(0.975 * (BOOTSTRAP_DRAWS - 1))]]


def performance_point(interval: list[float]) -> tuple[str, int | None]:
    if interval[0] >= MIN_PERFORMANCE_RATIO:
        return "pass", 1
    if interval[1] < MIN_PERFORMANCE_RATIO:
        return "fail", 0
    return "inconclusive", None


def measure(root: Path) -> dict:
    config = json.loads((root / "tests/performance.json").read_text(encoding="utf-8"))
    args = [str(arg) for arg in config.get("args", [])]
    workers = int(config["workers"])
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS=str(workers), OMP_DYNAMIC="FALSE")

    with tempfile.TemporaryDirectory(prefix="openmp-performance-") as temporary:
        candidate, reference = build(root, config, Path(temporary))

        # Warm both binaries before timing. Calibration uses the trusted reference.
        timed_batch(reference, args, 1, env)
        timed_batch(candidate, args, 1, env)
        single = timed_batch(reference, args, 1, env)
        invocations = min(MAX_BATCH_INVOCATIONS,
                          max(1, math.ceil(MIN_BATCH_SECONDS / max(single, 1e-9))))

        reference_samples = []
        candidate_samples = []
        for round_index in range(ROUNDS):
            order = (("reference", reference), ("candidate", candidate))
            if round_index % 2:
                order = tuple(reversed(order))
            for label, binary in order:
                elapsed = timed_batch(binary, args, invocations, env)
                if label == "reference":
                    reference_samples.append(elapsed)
                else:
                    candidate_samples.append(elapsed)

    reference_median = statistics.median(reference_samples)
    candidate_median = statistics.median(candidate_samples)
    paired_ratios = [ref / cand for ref, cand in
                     zip(reference_samples, candidate_samples)]
    ratio = statistics.median(paired_ratios)
    interval = bootstrap_interval(paired_ratios)
    status, point = performance_point(interval)

    return {
        "schema_version": 1,
        "metric": "end_to_end_wall_time_seconds_per_process",
        "unit": "seconds",
        "repetitions": ROUNDS,
        "batch_invocations": invocations,
        "workers": workers,
        "arguments": args,
        "compiler": os.environ.get("CC", "gcc"),
        "build_flags": ["-std=c11", "-O2", "-fopenmp"],
        "threshold_ratio": MIN_PERFORMANCE_RATIO,
        "ratio_method": "median_of_paired_reference_over_candidate_rounds",
        "status": status,
        "performance_point": point,
        "confidence_interval_95": interval,
        "paired_ratios": paired_ratios,
        "measurements": [
            {"label": "official_reference", "workers": workers,
             "samples": reference_samples, "median": reference_median},
            {"label": "candidate", "workers": workers,
             "samples": candidate_samples, "median": candidate_median},
        ],
        "comparisons": [
            {"label": "candidate_vs_official_reference",
             "numerator": "official_reference",
             "denominator": "candidate",
             "ratio": ratio, "direction": "higher_is_faster"},
        ],
    }


if __name__ == "__main__":
    try:
        print(json.dumps(measure(Path.cwd()), separators=(",", ":")))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Performance measurement unavailable: {exc}", file=sys.stderr)
        sys.exit(1)

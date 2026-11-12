#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
: "${BENCHMARK_REFERENCE_WORKSPACE:?}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
compiler=${CC:-cc}
"$compiler" -O3 -std=c11 -D_POSIX_C_SOURCE=200112L -DSMALL_DATASET -I"$root/tests/reference" "$root/tests/reference/symm.c" "$root/tests/reference/polybench.c" -lm -o "$work/reference"
python3 - "$work/reference" "$root/build/symm" <<'PYMEASURE'
import json, os, subprocess, sys, time, statistics
reference, candidate = sys.argv[1:]
measurements=[]
for label, executable, workers in [('upstream_serial_reference',reference,1),('candidate',candidate,1),('candidate',candidate,4)]:
    samples=[]
    for _ in range(5):
        env=os.environ.copy();env['OMP_NUM_THREADS']=str(workers)
        start=time.perf_counter();subprocess.run([executable],env=env,stdout=subprocess.DEVNULL,check=True);samples.append(time.perf_counter()-start)
    measurements.append(dict(label=label,workers=workers,samples=samples,median=statistics.median(samples)))
a,b,c=(m['median'] for m in measurements)
print(json.dumps(dict(schema_version=1,metric='wall_time_seconds',unit='seconds',repetitions=5,measurements=measurements,comparisons=[dict(label='candidate_1_worker_vs_serial_reference',ratio=a/b,direction='higher_is_faster'),dict(label='candidate_4_workers_vs_serial_reference',ratio=a/c,direction='higher_is_faster'),dict(label='candidate_scaling_1_to_4_workers',ratio=b/c,direction='higher_is_better_scaling')])))
PYMEASURE

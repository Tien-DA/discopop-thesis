#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
: "${BENCHMARK_REFERENCE_WORKSPACE:?}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
if [[ $(uname) == Darwin ]]; then flags=(-Xpreprocessor -fopenmp -I/usr/local/opt/libomp/include -L/usr/local/opt/libomp/lib -lomp); else flags=(-fopenmp); fi
"${CXX:-c++}" -O3 "${flags[@]}" "$root/tests/reference/hotspot.cpp" -o "$work/reference"
python3 - "$root" "$work/reference" "$root/build/hotspot" "$work" <<'PY'
import json,os,subprocess,sys,time,statistics
root,reference,candidate,work=sys.argv[1:]
measurements=[]
for label,exe,workers in [('upstream_serial_reference',reference,1),('candidate',candidate,1),('candidate',candidate,4)]:
 samples=[]
 for _ in range(5):
  env=os.environ.copy();env['OMP_NUM_THREADS']=str(workers)
  args=[exe,'512','512','2',str(workers),root+'/input/temp_512',root+'/input/power_512',work+'/out']
  start=time.perf_counter();subprocess.run(args,env=env,stdout=subprocess.DEVNULL,check=True);samples.append(time.perf_counter()-start)
 measurements.append(dict(label=label,workers=workers,samples=samples,median=statistics.median(samples)))
a,b,c=[x['median'] for x in measurements]
print(json.dumps(dict(schema_version=1,metric='wall_time_seconds',unit='seconds',repetitions=5,measurements=measurements,comparisons=[dict(label='candidate_1_worker_vs_serial_reference',ratio=a/b,direction='higher_is_faster'),dict(label='candidate_4_workers_vs_serial_reference',ratio=a/c,direction='higher_is_faster'),dict(label='candidate_scaling_1_to_4_workers',ratio=b/c,direction='higher_is_better_scaling')])))
PY

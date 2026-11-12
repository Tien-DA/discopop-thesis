#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
compiler=${CC:-cc}
if [[ $(uname) == Darwin ]]; then
  omp_flags=(-Xpreprocessor -fopenmp -I/usr/local/opt/libomp/include -L/usr/local/opt/libomp/lib -lomp)
else
  omp_flags=(-fopenmp)
fi
"$compiler" -O3 -std=c11 -D_POSIX_C_SOURCE=200112L "${omp_flags[@]}" -DSMALL_DATASET -DPOLYBENCH_DUMP_ARRAYS -I"$root/src" "$root/src/floyd-warshall.c" "$root/src/polybench.c" -lm -o "$work/candidate"
"$compiler" -O3 -std=c11 -D_POSIX_C_SOURCE=200112L -DSMALL_DATASET -DPOLYBENCH_DUMP_ARRAYS -I"$root/tests/reference" "$root/tests/reference/floyd-warshall.c" "$root/tests/reference/polybench.c" -lm -o "$work/reference"
"$work/reference" >"$work/reference.time" 2>"$work/reference.out"
for workers in 1 4; do
  OMP_NUM_THREADS="$workers" "$work/candidate" >"$work/candidate-${workers}.time" 2>"$work/candidate-${workers}.out"
  cmp "$work/candidate-${workers}.out" "$work/reference.out"
done
grep -Eq '#[[:space:]]*pragma[[:space:]]+omp[[:space:]]+parallel' "$root/src/floyd-warshall.c"
echo "PolyBench floyd-warshall: output matches the serial reference with 1 and 4 workers."

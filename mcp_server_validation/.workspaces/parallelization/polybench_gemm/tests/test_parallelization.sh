#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

cc -O3 -std=c11 -fopenmp -DMEDIUM_DATASET -DPOLYBENCH_DUMP_ARRAYS -I"$root/src" "$root/src/gemm.c" "$root/src/polybench.c" -lm -o "$work/candidate"
cc -O3 -std=c11 -DMEDIUM_DATASET -DPOLYBENCH_DUMP_ARRAYS -I"$root/tests/reference" "$root/tests/reference/gemm.c" "$root/tests/reference/polybench.c" -lm -o "$work/reference"
"$work/reference" >"$work/reference.time" 2>"$work/reference.out"
for workers in 1 4; do
  OMP_NUM_THREADS="$workers" "$work/candidate" >"$work/candidate-${workers}.time" 2>"$work/candidate-${workers}.out"
  cmp "$work/candidate-${workers}.out" "$work/reference.out"
done
grep -Eq '#[[:space:]]*pragma[[:space:]]+omp[[:space:]]+parallel' "$root/src/gemm.c"
echo "PolyBench GEMM: serial and four-worker output match the upstream sequential implementation."

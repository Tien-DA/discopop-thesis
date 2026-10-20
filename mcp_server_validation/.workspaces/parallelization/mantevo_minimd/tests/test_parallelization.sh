#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

grep -Rqs '#pragma omp[[:space:]]\+parallel' "$root/src"

for workers in 1 4; do
  output="$work/output-${workers}.txt"
  (cd "$root/src" && OMP_NUM_THREADS="$workers" mpirun -np 1 ./miniMD -i in.lj.miniMD -n 10) >"$output"
  grep -q 'MiniMD' "$output"
  grep -Eq "^[[:space:]]*threads:[[:space:]]+${workers}[[:space:]]*$" "$output"
  grep -q 'thermodynamic_output:' "$output"
  awk '/T\*:|U\*:|P\*:|Conservation:/ {print $NF}' "$output" >"$work/values-${workers}.txt"
  test -s "$work/values-${workers}.txt"
done

paste "$work/values-1.txt" "$work/values-4.txt" | awk '
  NF != 2 { exit 1 }
  {
    a = $1 + 0
    b = $2 + 0
    scale = (a < 0 ? -a : a)
    if ((b < 0 ? -b : b) > scale) scale = (b < 0 ? -b : b)
    if (scale < 1) scale = 1
    if ((a - b < 0 ? b - a : a - b) > 1e-7 * scale) exit 1
  }
'

echo "miniMD: one-worker and four-worker thermodynamic output agree."

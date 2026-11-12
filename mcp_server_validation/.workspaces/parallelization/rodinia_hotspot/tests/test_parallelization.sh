#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
if [[ $(uname) == Darwin ]]; then flags=(-Xpreprocessor -fopenmp -I/usr/local/opt/libomp/include -L/usr/local/opt/libomp/lib -lomp); else flags=(-fopenmp); fi
compiler=${CXX:-c++}
"$compiler" -O3 "${flags[@]}" "$root/src/hotspot.cpp" -o "$work/candidate"
"$compiler" -O3 "${flags[@]}" "$root/tests/reference/hotspot.cpp" -o "$work/reference"
for size in 64 128; do
  "$work/reference" "$size" "$size" 2 1 "$root/input/temp_$size" "$root/input/power_$size" "$work/ref" >/dev/null
  for workers in 1 4; do
    OMP_NUM_THREADS="$workers" "$work/candidate" "$size" "$size" 2 "$workers" "$root/input/temp_$size" "$root/input/power_$size" "$work/out" >/dev/null
    cmp "$work/ref" "$work/out"
  done
done
grep -Eq '#[[:space:]]*pragma[[:space:]]+omp[[:space:]]+parallel' "$root/src/hotspot.cpp"

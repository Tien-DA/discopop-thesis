#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
reference_root=${BENCHMARK_REFERENCE_WORKSPACE:?BENCHMARK_REFERENCE_WORKSPACE is required}
repetitions=5
compiler=${CC:-cc}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# The serial source lives in tests/ and is restored only in the evaluator
# workspace. It is the trusted upstream reference for this task.
"$compiler" -O3 -std=c11 -DMEDIUM_DATASET -I"$root/tests/reference" \
  "$root/tests/reference/gemm.c" "$root/tests/reference/polybench.c" -lm \
  -o "$work/reference-gemm"

collect_samples() {
  local executable=$1
  local workers=$2
  local samples=''
  local elapsed
  local repeat
  local started
  local finished
  for repeat in $(seq 1 "$repetitions"); do
    started=$(date +%s%N)
    env OMP_NUM_THREADS="$workers" "$executable" >/dev/null
    finished=$(date +%s%N)
    elapsed=$(awk -v started="$started" -v finished="$finished" 'BEGIN {
      printf "%.9f", (finished - started) / 1000000000
    }')
    samples="${samples}${elapsed}\n"
  done
  printf '%b' "$samples"
}

median() {
  sort -g | sed -n "$((repetitions / 2 + 1))p"
}

json_samples() {
  paste -sd, -
}

ratio() {
  awk -v numerator="$1" -v denominator="$2" 'BEGIN {
    if (denominator <= 0) exit 1
    printf "%.9f", numerator / denominator
  }'
}

baseline_samples=$(collect_samples "$work/reference-gemm" 1)
candidate_one_samples=$(collect_samples "$root/build/gemm" 1)
candidate_four_samples=$(collect_samples "$root/build/gemm" 4)

baseline_median=$(printf '%s\n' "$baseline_samples" | median)
candidate_one_median=$(printf '%s\n' "$candidate_one_samples" | median)
candidate_four_median=$(printf '%s\n' "$candidate_four_samples" | median)

baseline_json=$(printf '%s\n' "$baseline_samples" | json_samples)
candidate_one_json=$(printf '%s\n' "$candidate_one_samples" | json_samples)
candidate_four_json=$(printf '%s\n' "$candidate_four_samples" | json_samples)

printf '{'
printf '"schema_version":1,'
printf '"metric":"wall_time_seconds","unit":"seconds","repetitions":%s,' "$repetitions"
printf '"reference_workspace":"%s",' "${reference_root##*/}"
printf '"measurements":['
printf '{"label":"upstream_serial_reference","workers":1,"samples":[%s],"median":%s},' "$baseline_json" "$baseline_median"
printf '{"label":"candidate","workers":1,"samples":[%s],"median":%s},' "$candidate_one_json" "$candidate_one_median"
printf '{"label":"candidate","workers":4,"samples":[%s],"median":%s}' "$candidate_four_json" "$candidate_four_median"
printf '],"comparisons":['
printf '{"label":"candidate_1_worker_vs_serial_reference","numerator":"upstream_serial_reference","denominator":"candidate_1_worker","ratio":%s,"direction":"higher_is_faster"},' "$(ratio "$baseline_median" "$candidate_one_median")"
printf '{"label":"candidate_4_workers_vs_serial_reference","numerator":"upstream_serial_reference","denominator":"candidate_4_workers","ratio":%s,"direction":"higher_is_faster"},' "$(ratio "$baseline_median" "$candidate_four_median")"
printf '{"label":"candidate_scaling_1_to_4_workers","numerator":"candidate_1_worker","denominator":"candidate_4_workers","ratio":%s,"direction":"higher_is_better_scaling"}' "$(ratio "$candidate_one_median" "$candidate_four_median")"
printf ']}'

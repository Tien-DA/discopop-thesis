#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
reference_root=${BENCHMARK_REFERENCE_WORKSPACE:?BENCHMARK_REFERENCE_WORKSPACE is required}
repetitions=5

# The benchmark runner creates this pristine source copy immediately before
# evaluation. It never appears in the agent workspace.
make -C "$reference_root" clean >/dev/null 2>&1 || true
make -C "$reference_root" all >/dev/null

collect_samples() {
  local source_root=$1
  local workers=$2
  local samples=''
  local elapsed
  local repeat
  local started
  local finished
  for repeat in $(seq 1 "$repetitions"); do
    started=$(date +%s%N)
    (cd "$source_root/src" && env OMP_NUM_THREADS="$workers" mpirun -np 1 ./miniMD -i in.lj.miniMD -n 100 >/dev/null)
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

baseline_one_samples=$(collect_samples "$reference_root" 1)
baseline_four_samples=$(collect_samples "$reference_root" 4)
candidate_one_samples=$(collect_samples "$root" 1)
candidate_four_samples=$(collect_samples "$root" 4)

baseline_one_median=$(printf '%s\n' "$baseline_one_samples" | median)
baseline_four_median=$(printf '%s\n' "$baseline_four_samples" | median)
candidate_one_median=$(printf '%s\n' "$candidate_one_samples" | median)
candidate_four_median=$(printf '%s\n' "$candidate_four_samples" | median)

baseline_one_json=$(printf '%s\n' "$baseline_one_samples" | json_samples)
baseline_four_json=$(printf '%s\n' "$baseline_four_samples" | json_samples)
candidate_one_json=$(printf '%s\n' "$candidate_one_samples" | json_samples)
candidate_four_json=$(printf '%s\n' "$candidate_four_samples" | json_samples)

printf '{'
printf '"schema_version":1,'
printf '"metric":"wall_time_seconds","unit":"seconds","repetitions":%s,' "$repetitions"
printf '"measurements":['
printf '{"label":"upstream_reference","workers":1,"samples":[%s],"median":%s},' "$baseline_one_json" "$baseline_one_median"
printf '{"label":"upstream_reference","workers":4,"samples":[%s],"median":%s},' "$baseline_four_json" "$baseline_four_median"
printf '{"label":"candidate","workers":1,"samples":[%s],"median":%s},' "$candidate_one_json" "$candidate_one_median"
printf '{"label":"candidate","workers":4,"samples":[%s],"median":%s}' "$candidate_four_json" "$candidate_four_median"
printf '],"comparisons":['
printf '{"label":"candidate_vs_reference_1_worker","numerator":"upstream_reference_1_worker","denominator":"candidate_1_worker","ratio":%s,"direction":"higher_is_faster"},' "$(ratio "$baseline_one_median" "$candidate_one_median")"
printf '{"label":"candidate_vs_reference_4_workers","numerator":"upstream_reference_4_workers","denominator":"candidate_4_workers","ratio":%s,"direction":"higher_is_faster"},' "$(ratio "$baseline_four_median" "$candidate_four_median")"
printf '{"label":"reference_scaling_1_to_4_workers","numerator":"upstream_reference_1_worker","denominator":"upstream_reference_4_workers","ratio":%s,"direction":"higher_is_better_scaling"},' "$(ratio "$baseline_one_median" "$baseline_four_median")"
printf '{"label":"candidate_scaling_1_to_4_workers","numerator":"candidate_1_worker","denominator":"candidate_4_workers","ratio":%s,"direction":"higher_is_better_scaling"}' "$(ratio "$candidate_one_median" "$candidate_four_median")"
printf ']}'

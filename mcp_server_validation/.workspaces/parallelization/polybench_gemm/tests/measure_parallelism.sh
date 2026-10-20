#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
for workers in 1 4; do
  samples=''
  for repeat in 1 2 3; do
    elapsed=$({ /usr/bin/time -p env OMP_NUM_THREADS="$workers" "$root/build/gemm" >/dev/null; } 2>&1 | awk '/^real / { print $2 }')
    test -n "$elapsed"
    samples="${samples}${elapsed}\n"
  done
  median=$(printf '%b' "$samples" | sort -g | sed -n '2p')
  printf 'workers=%s samples_seconds=%s median_seconds=%s\n' "$workers" "$(printf '%b' "$samples" | paste -sd, -)" "$median"
done

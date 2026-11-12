#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
: "${BENCHMARK_PARALLEL_PERFORMANCE_TOOL:?Evaluator performance tool is required}"
python3 "$BENCHMARK_PARALLEL_PERFORMANCE_TOOL" "$root"

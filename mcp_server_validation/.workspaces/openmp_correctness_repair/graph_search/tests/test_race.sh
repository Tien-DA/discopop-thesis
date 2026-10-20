#!/usr/bin/env bash
set -euo pipefail

app=$1
shift

if ! grep -Rqs '#pragma omp' src; then
    echo 'OpenMP parallelism was removed.' >&2
    exit 1
fi

for workers in 2 4; do
    output="build/test-${workers}.out"
    errors="build/tsan-${workers}.err"
    if ! TSAN_OPTIONS='halt_on_error=1 exitcode=66' OMP_NUM_THREADS="$workers" "$app" "$@" >"$output" 2>"$errors"; then
        if grep -qi 'data race' "$errors"; then
            echo "ThreadSanitizer reported a data race with ${workers} workers." >&2
        else
            echo "The ${workers}-worker ThreadSanitizer run exited unsuccessfully:" >&2
            tail -n 20 "$errors" >&2 || true
        fi
        exit 1
    fi
    if grep -qi 'data race' "$errors"; then
        echo "ThreadSanitizer reported a data race with ${workers} workers." >&2
        exit 1
    fi
done

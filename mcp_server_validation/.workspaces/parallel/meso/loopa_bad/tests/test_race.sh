#!/usr/bin/env bash
set -euo pipefail

app=$1
shift

if ! grep -Rqs '#pragma omp' src; then
    echo 'OpenMP parallelism was removed.' >&2
    exit 1
fi

TSAN_OPTIONS='halt_on_error=1 exitcode=66' OMP_NUM_THREADS=4 "$app" "$@" >build/test.out 2>build/tsan.err
if grep -qi 'data race' build/tsan.err; then
    echo 'ThreadSanitizer reported a data race.' >&2
    exit 1
fi

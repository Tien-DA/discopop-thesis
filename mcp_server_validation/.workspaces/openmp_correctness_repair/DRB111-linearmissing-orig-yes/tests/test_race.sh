#!/usr/bin/env bash
set -euo pipefail

source_file=$1
reference_file=$2
compiler=${CC:-gcc}

mkdir -p build
"$compiler" -std=c11 -O0 -g -fopenmp -fsanitize=thread "$source_file" -o build/tsan-app
"$compiler" -std=c11 -O0 -g -fopenmp "$reference_file" -o build/reference-app

if ! grep -Eq '^[[:space:]]*#[[:space:]]*pragma[[:space:]]+omp[[:space:]]+(parallel|taskloop|for|sections|task)([[:space:]]|$)' "$source_file"; then
    echo "The OpenMP parallel work construct was removed." >&2
    exit 1
fi

for workers in 1 2 4; do
    reference_output="build/reference-${workers}.out"
    output="build/test-${workers}.out"
    errors="build/tsan-${workers}.err"

    OMP_NUM_THREADS="$workers" timeout 60s ./build/reference-app >"$reference_output"
    if ! TSAN_OPTIONS="halt_on_error=1 exitcode=66" OMP_NUM_THREADS="$workers" \
        timeout 60s ./build/tsan-app >"$output" 2>"$errors"; then
        if grep -qi 'data race' "$errors"; then
            echo "ThreadSanitizer reported a data race with ${workers} workers." >&2
        else
            echo "The ${workers}-worker run failed or timed out." >&2
            tail -n 20 "$errors" >&2 || true
        fi
        exit 1
    fi
    if ! cmp -s "$output" "$reference_output"; then
        echo "Program output differs from the official race-free reference with ${workers} workers." >&2
        exit 1
    fi
done

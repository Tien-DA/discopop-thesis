#!/usr/bin/env bash
set -euo pipefail

source_file=$1
expected_output_file=$2
source tests/archer.sh

mkdir -p build
"$compiler" -std=c11 -O0 -g "${repair_openmp_flags[@]}" -fsanitize=thread "$source_file" -o build/tsan-app

if ! grep -Eq '^[[:space:]]*#[[:space:]]*pragma[[:space:]]+omp[[:space:]]+(parallel[[:space:]]+(for|sections)|for|sections|task)' "$source_file"; then
    echo "The OpenMP work-sharing construct was removed." >&2
    exit 1
fi

expected_output=$(<"$expected_output_file")
for workers in 2 4; do
    output="build/test-${workers}.out"
    errors="build/tsan-${workers}.err"
    if ! TSAN_OPTIONS="$REPAIR_TSAN_OPTIONS" OMP_NUM_THREADS="$workers" ./build/tsan-app >"$output" 2>"$errors"; then
        cat "$errors" >&2
        exit 1
    fi
    if grep -qi "data race" "$errors"; then
        echo "ThreadSanitizer reported a data race with ${workers} workers." >&2
        exit 1
    fi
    if [[ "$expected_output" == "__EMPTY__" ]]; then
        if [[ -s "$output" ]]; then
            echo "Expected no output with ${workers} workers." >&2
            exit 1
        fi
    elif ! grep -Eq "$expected_output" "$output"; then
        echo "Program output did not match the expected behavior with ${workers} workers." >&2
        exit 1
    fi
done

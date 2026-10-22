#!/usr/bin/env bash
set -euo pipefail

source_file=$1
expected_output_file=$2
compiler=${CC:-gcc}

mkdir -p build
"$compiler" -std=c11 -O0 -g -fopenmp -fsanitize=thread "$source_file" -o build/tsan-app
"$compiler" -std=c11 -O0 -g -fopenmp -Dmain=official_reference_main -c \
    tests/reference/DRB105-taskwait-orig-no.c -o build/reference.o
"$compiler" -std=c11 -O0 -g -fopenmp tests/reference/run_fib10.c \
    build/reference.o -o build/reference-app

if ! grep -Eq '^[[:space:]]*#[[:space:]]*pragma[[:space:]]+omp[[:space:]]+(parallel[[:space:]]+(for|sections)|for|sections|task)' "$source_file"; then
    echo "The OpenMP work-sharing construct was removed." >&2
    exit 1
fi

expected_output=$(<"$expected_output_file")
for workers in 2 4; do
    reference_result=$(OMP_NUM_THREADS="$workers" ./build/reference-app)
    output="build/test-${workers}.out"
    errors="build/tsan-${workers}.err"
    if ! TSAN_OPTIONS="halt_on_error=1 exitcode=66" OMP_NUM_THREADS="$workers" ./build/tsan-app >"$output" 2>"$errors"; then
        cat "$errors" >&2
        exit 1
    fi
    if grep -qi "data race" "$errors"; then
        echo "ThreadSanitizer reported a data race with ${workers} workers." >&2
        exit 1
    fi
    candidate_result=$(sed -nE 's/^Fib\(10\)=([0-9]+).*/\1/p' "$output")
    if [[ "$candidate_result" != "$reference_result" ]]; then
        echo "Fibonacci result differs from the official race-free reference with ${workers} workers." >&2
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

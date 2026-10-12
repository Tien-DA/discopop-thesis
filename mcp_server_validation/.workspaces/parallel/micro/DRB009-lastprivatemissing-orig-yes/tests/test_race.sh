#!/usr/bin/env bash
set -euo pipefail

source_file=$1
expected_output_file=$2
compiler=${CC:-gcc}

mkdir -p build
"$compiler" -std=c11 -O0 -g -fopenmp -fsanitize=thread "$source_file" -o build/tsan-app
TSAN_OPTIONS="halt_on_error=1 exitcode=66" OMP_NUM_THREADS=4 ./build/tsan-app >build/test.out 2>build/tsan.err
if grep -qi "data race" build/tsan.err; then
    echo "ThreadSanitizer reported a data race." >&2
    exit 1
fi
expected_output=$(<"$expected_output_file")
if [[ "$expected_output" == "__EMPTY__" ]]; then
    test ! -s build/test.out
    exit 0
fi
grep -Eq "$expected_output" build/test.out

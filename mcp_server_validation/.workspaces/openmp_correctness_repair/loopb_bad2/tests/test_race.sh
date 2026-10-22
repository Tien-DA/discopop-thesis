#!/usr/bin/env bash
set -euo pipefail

compiler=${COMPILER:-gcc}
source_file=src/c_loopB.badSolution2.c
reference_file=tests/reference/c_loopB.pipelineSolution.c
support=(src/common/ompscrCommon.c src/common/wtime.c)
reference_support=(tests/reference/common/ompscrCommon.c tests/reference/common/wtime.c)
flags=(-std=c11 -O0 -g -fopenmp -DDEBUG)

mkdir -p build
"$compiler" "${flags[@]}" -Isrc/include -Isrc/common -Itests/reference \
    -fsanitize=thread "$source_file" "${support[@]}" -o build/tsan-app -lm
"$compiler" "${flags[@]}" -Itests/reference/include -Itests/reference \
    "$reference_file" "${reference_support[@]}" -o build/reference-app -lm

if ! grep -Eq '^[[:space:]]*#[[:space:]]*pragma[[:space:]]+omp[[:space:]]+(parallel|for)([[:space:]]|$)' "$source_file"; then
    echo 'The OpenMP parallel work construct was removed.' >&2
    exit 1
fi

for workers in 1 2 4; do
    expected="build/reference-${workers}.vector"
    actual="build/test-${workers}.vector"
    OMP_NUM_THREADS="$workers" timeout 60s ./build/reference-app "$@" >"build/reference-${workers}.out" 2>"$expected"
    if ! TSAN_OPTIONS='halt_on_error=1 exitcode=66' OMP_NUM_THREADS="$workers" \
        timeout 60s ./build/tsan-app "$@" >"build/test-${workers}.out" 2>"$actual"; then
        echo "The ${workers}-worker run failed, timed out, or reported a data race." >&2
        tail -n 20 "$actual" >&2 || true
        exit 1
    fi
    if ! cmp -s "$expected" "$actual"; then
        echo "Final vector differs from the official OmpSCR pipeline solution with ${workers} workers." >&2
        exit 1
    fi
done

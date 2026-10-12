#!/usr/bin/env bash
set -euo pipefail

readonly test_dir="Tests/Particles/Redistribute"
readonly test_source="$test_dir/main.cpp"
readonly fixed_test="tests/main.cpp.fixed"

# The test revision below is exactly the one committed with AMReX PR #5404.
# It is restored for every evaluation so edits to the public test cannot mask
# a race in the library snapshot.
cp "$fixed_test" "$test_source"

make -C "$test_dir" clean
make -C "$test_dir" USE_MPI=FALSE USE_OMP=TRUE BL_NO_FORT=TRUE THREAD_SANITIZER=TRUE DEBUG=TRUE

app="$(find "$test_dir" -maxdepth 1 -type f -name '*.ex' -perm -u+x | head -n 1)"
if [[ -z "$app" ]]; then
    echo "AMReX Redistribute test executable was not produced." >&2
    exit 1
fi

set +e
TSAN_OPTIONS='halt_on_error=1 exitcode=66' OMP_NUM_THREADS=4 "$app" >build.upstream.out 2>build.tsan.err
status=$?
set -e

if [[ $status -eq 66 ]] || grep -qi 'data race' build.tsan.err; then
    cat build.tsan.err >&2
    exit 1
fi

if [[ $status -ne 0 ]]; then
    cat build.tsan.err >&2
    exit "$status"
fi

grep -q 'Running redistribute test' build.upstream.out

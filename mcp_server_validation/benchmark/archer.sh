#!/usr/bin/env bash
# Sourced by hidden tests/archer.sh links. copytree dereferences these links in
# evaluator workspaces, so detached benchmark runs carry the exact helper.

repair_setup_error() {
    echo "[Archer setup] ERROR: $*" >&2
    exit 1
}

compiler=${CC:-${COMPILER:-clang}}
command -v "$compiler" >/dev/null 2>&1 || repair_setup_error "Clang not found: $compiler"
repair_version=$("$compiler" --version) || repair_setup_error "Cannot execute $compiler"
[[ "$repair_version" == *clang* ]] || repair_setup_error "Use Clang, not $compiler. Set CC=clang-19 (COMPILER=clang-19 for OmpSCR)."
[[ $(uname -s) == Linux ]] || repair_setup_error "The race oracle requires Linux Clang/libomp/Archer/TSan."

repair_resource=$("$compiler" -print-resource-dir)
repair_llvm_lib=$(dirname "$(dirname "$repair_resource")")
repair_archer=${ARCHER_LIBRARY:-}
if [[ -z "$repair_archer" ]]; then
    for repair_path in "$("$compiler" -print-file-name=libarcher.so)" "$repair_llvm_lib/libarcher.so"; do
        if [[ -f "$repair_path" ]]; then
            repair_archer=$repair_path
            break
        fi
    done
fi
[[ -f "$repair_archer" ]] || repair_setup_error "libarcher.so not found for $compiler. Install matching libomp development package or set ARCHER_LIBRARY to its absolute path."
repair_archer=$(realpath "$repair_archer")
repair_openmp_flags=(-fopenmp=libomp "-L$(dirname "$repair_archer")" "-Wl,-rpath,$(dirname "$repair_archer")")

# Fixed oracle settings: no inherited suppressions or disabled analysis. Archer
# documents ignore_noninstrumented_modules for uninstrumented runtime code.
export REPAIR_TSAN_OPTIONS='ignore_noninstrumented_modules=1:halt_on_error=1:exitcode=66'
export TSAN_OPTIONS="$REPAIR_TSAN_OPTIONS"
export OMP_TOOL=enabled
export OMP_TOOL_LIBRARIES="$repair_archer"
export OMP_TOOL_VERBOSE_INIT=disabled
export ARCHER_OPTIONS='enable=1 verbose=0 ignore_serial=0'
export OMP_DYNAMIC=FALSE
export OMP_THREAD_LIMIT=64

mkdir -p build
cat > build/archer-good.c <<'EOF'
#include <assert.h>
int main(void) {
    int value = 0;
#pragma omp parallel num_threads(2) shared(value)
#pragma omp single
    {
#pragma omp task depend(out:value) shared(value)
        value = 1;
#pragma omp task depend(inout:value) shared(value)
        value = 2;
#pragma omp taskwait
    }
    assert(value == 2);
    return 0;
}
EOF
cat > build/archer-race.c <<'EOF'
int main(void) {
    int value = 0;
#pragma omp parallel num_threads(2) shared(value)
    {
        for (int i = 0; i < 1000; ++i)
            value++;
    }
    return value == -1;
}
EOF
for repair_probe in good race; do
    if ! "$compiler" -std=c11 -O0 -g "${repair_openmp_flags[@]}" -fsanitize=thread \
        "build/archer-$repair_probe.c" -o "build/archer-$repair_probe" \
        >"build/archer-$repair_probe.compile.out" 2>"build/archer-$repair_probe.compile.err"; then
        cat "build/archer-$repair_probe.compile.err" >&2
        repair_setup_error "Cannot compile $repair_probe probe with Clang/libomp/TSan."
    fi
done
repair_libraries=$(ldd build/archer-good) || repair_setup_error "Cannot inspect runtime libraries."
[[ "$repair_libraries" == *libomp.so* && "$repair_libraries" != *libgomp.so* ]] || repair_setup_error "Probe must load libomp, not libgomp: $repair_libraries"

if ! ARCHER_OPTIONS='enable=1 verbose=1 ignore_serial=0' OMP_THREAD_LIMIT=2 \
    timeout 30s ./build/archer-good >build/archer-good.out 2>build/archer-good.err; then
    cat build/archer-good.out build/archer-good.err >&2
    repair_setup_error "Known-correct OpenMP task probe failed."
fi
grep -q 'Archer detected OpenMP application with TSan' build/archer-good.out || {
    cat build/archer-good.out build/archer-good.err >&2
    repair_setup_error "Archer did not activate; refusing to run the oracle."
}
repair_probe_status=0
OMP_THREAD_LIMIT=2 timeout 30s ./build/archer-race \
    >build/archer-race.out 2>build/archer-race.err || repair_probe_status=$?
if [[ "$repair_probe_status" != 66 ]] || ! grep -q 'WARNING: ThreadSanitizer: data race' build/archer-race.err; then
    cat build/archer-race.out build/archer-race.err >&2
    repair_setup_error "Race detector self-check failed (expected race exit 66, got $repair_probe_status)."
fi
echo "[Archer setup] PASS: ${repair_version%%$'\n'*}; libomp; $repair_archer; correct/racy probes verified"

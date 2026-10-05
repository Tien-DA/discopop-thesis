#include <cstdint>
#include <iostream>
#include <omp.h>
#include "config.h"
#include "context.h"
#include "pipeline.h"

namespace {
constexpr uint64_t kSeed = 20261004ULL;
constexpr uint64_t kGoldenProfiling = 2956884534226943421ULL;
constexpr uint64_t kGoldenStress = 7090033127137085518ULL;
uint64_t digest(const Config& config, int threads) {
    omp_set_dynamic(0); omp_set_num_threads(threads);
    Context ctx(config, kSeed); run_all(ctx); return checksum(ctx);
}
bool stencil_sequential_profile_matches_golden() { return digest(profiling_config(), 1) == kGoldenProfiling; }
bool stencil_sequential_stress_matches_golden() { return digest(stress_config(), 1) == kGoldenStress; }
bool stencil_parallel_halos_match_golden() { for (int i = 0; i < 16; ++i) if (digest(profiling_config(), 8) != kGoldenProfiling) return false; return true; }
bool stencil_parallel_stress_matches_golden() { for (int t : {4, 8, 12}) for (int i = 0; i < 4; ++i) if (digest(stress_config(), t) != kGoldenStress) return false; return true; }
}  // namespace

int main() {
    struct Test { const char* name; bool (*function)(); };
    const Test tests[] = {
        {"stencil_sequential_profile_matches_golden", stencil_sequential_profile_matches_golden}, {"stencil_sequential_stress_matches_golden", stencil_sequential_stress_matches_golden}, {"stencil_parallel_halos_match_golden", stencil_parallel_halos_match_golden}, {"stencil_parallel_stress_matches_golden", stencil_parallel_stress_matches_golden}
    };
    int failures = 0;
    for (const auto& test : tests) {
        if (test.function()) std::cout << "[PASS] " << test.name << std::endl;
        else { std::cerr << "[FAIL] " << test.name << std::endl; ++failures; }
    }
    if (failures) { std::cerr << failures << " test(s) failed." << std::endl; return 1; }
    std::cout << "All tests passed." << std::endl;
    return 0;
}

#include <cstdint>
#include <iostream>
#include <omp.h>
#include "config.h"
#include "context.h"
#include "pipeline.h"

namespace {
constexpr uint64_t kSeed = 20261004ULL;
constexpr uint64_t kGoldenProfiling = 6965038551762099044ULL;
constexpr uint64_t kGoldenStress = 14124349492425838302ULL;
uint64_t digest(const Config& config, int threads) {
    omp_set_dynamic(0); omp_set_num_threads(threads);
    Context ctx(config, kSeed); run_all(ctx); return checksum(ctx);
}
bool task_graph_sequential_profile_matches_golden() { return digest(profiling_config(), 1) == kGoldenProfiling; }
bool task_graph_sequential_stress_matches_golden() { return digest(stress_config(), 1) == kGoldenStress; }
bool task_graph_parallel_merge_counts_match_golden() { for (int i = 0; i < 16; ++i) if (digest(profiling_config(), 8) != kGoldenProfiling) return false; return true; }
bool task_graph_parallel_stress_matches_golden() { for (int t : {4, 8, 12}) for (int i = 0; i < 4; ++i) if (digest(stress_config(), t) != kGoldenStress) return false; return true; }
}  // namespace

int main() {
    struct Test { const char* name; bool (*function)(); };
    const Test tests[] = {
        {"task_graph_sequential_profile_matches_golden", task_graph_sequential_profile_matches_golden}, {"task_graph_sequential_stress_matches_golden", task_graph_sequential_stress_matches_golden}, {"task_graph_parallel_merge_counts_match_golden", task_graph_parallel_merge_counts_match_golden}, {"task_graph_parallel_stress_matches_golden", task_graph_parallel_stress_matches_golden}
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

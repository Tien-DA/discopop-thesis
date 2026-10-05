#include <cstdint>
#include <iostream>

#include "config.h"
#include "context.h"
#include "pipeline.h"

namespace {
constexpr uint64_t kSeed = 20261004ULL;
constexpr uint64_t kGoldenProfiling = 13775878792427347996ULL;
constexpr uint64_t kGoldenStress = 9890133355103629171ULL;

uint64_t run_pipeline_digest(const Config& config) {
    Context ctx(config, kSeed);
    run_all(ctx);
    return checksum(ctx);
}

bool test_profiling_workload_matches_reference() {
    return run_pipeline_digest(profiling_config()) == kGoldenProfiling;
}

bool test_stress_workload_matches_reference() {
    return run_pipeline_digest(stress_config()) == kGoldenStress;
}

bool test_repeated_profiling_workload_is_stable() {
    for (int trial = 0; trial < 5; ++trial) {
        if (run_pipeline_digest(profiling_config()) != kGoldenProfiling) return false;
    }
    return true;
}
}  // namespace

int main() {
    struct Test { const char* name; bool (*function)(); };
    const Test tests[] = {
        {"profiling_workload_matches_reference", test_profiling_workload_matches_reference},
        {"stress_workload_matches_reference", test_stress_workload_matches_reference},
        {"repeated_profiling_workload_is_stable", test_repeated_profiling_workload_is_stable},
    };
    int failures = 0;
    for (const Test& test : tests) {
        if (test.function()) std::cout << "[PASS] " << test.name << std::endl;
        else { std::cerr << "[FAIL] " << test.name << std::endl; ++failures; }
    }
    if (failures) { std::cerr << failures << " test(s) failed." << std::endl; return 1; }
    std::cout << "All tests passed." << std::endl;
    return 0;
}

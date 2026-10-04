#include <cstdint>
#include <iostream>

#include <omp.h>

#include "config.h"
#include "context.h"
#include "pipeline.h"

namespace {

constexpr uint64_t kSeed = 20261004ULL;
// Digests produced by the reference (sequential) execution of the pipeline.
constexpr uint64_t kGoldenProfiling = 676562504391227398ULL;
constexpr uint64_t kGoldenStress = 8366546716101169961ULL;

uint64_t run_pipeline_digest(const Config& config, int threads) {
    omp_set_dynamic(0);
    omp_set_num_threads(threads);
    Context ctx(config, kSeed);
    run_all(ctx);
    return checksum(ctx);
}

bool test_sequential_profiling_workload_matches_golden() {
    return run_pipeline_digest(profiling_config(), 1) == kGoldenProfiling;
}

bool test_sequential_stress_workload_matches_golden() {
    return run_pipeline_digest(stress_config(), 1) == kGoldenStress;
}

bool test_parallel_profiling_workload_matches_golden() {
    for (int trial = 0; trial < 20; ++trial) {
        if (run_pipeline_digest(profiling_config(), 8) != kGoldenProfiling) return false;
    }
    return true;
}

bool test_parallel_stress_workload_matches_golden() {
    const int thread_counts[] = {4, 8};
    for (int threads : thread_counts) {
        for (int trial = 0; trial < 6; ++trial) {
            if (run_pipeline_digest(stress_config(), threads) != kGoldenStress) return false;
        }
    }
    return true;
}

}  // namespace

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"sequential_profiling_workload_matches_golden", test_sequential_profiling_workload_matches_golden},
        {"sequential_stress_workload_matches_golden", test_sequential_stress_workload_matches_golden},
        {"parallel_profiling_workload_matches_golden", test_parallel_profiling_workload_matches_golden},
        {"parallel_stress_workload_matches_golden", test_parallel_stress_workload_matches_golden}
    };

    int failures = 0;
    for (const Test& test : tests) {
        bool passed = test.function();
        if (passed) {
            std::cout << "[PASS] " << test.name << std::endl;
        } else {
            std::cerr << "[FAIL] " << test.name << std::endl;
            ++failures;
        }
    }

    if (failures > 0) {
        std::cerr << failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}

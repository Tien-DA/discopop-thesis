#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <vector>

#include "data_gen.h"
#include "report.h"
#include "stats.h"

#include <omp.h>

namespace {

// Reference parallel implementation used as the performance yardstick: the
// same per-iteration updates of per-thread slots as the candidate, but each
// slot is padded to its own cache line, so there is no false sharing.
struct alignas(64) PaddedStats {
    Stats stats;
};

Stats reference_stats_parallel(const std::vector<long long>& values, long long threshold) {
    std::vector<PaddedStats> partial(static_cast<std::size_t>(omp_get_max_threads()));
    const long long n = static_cast<long long>(values.size());
    #pragma omp parallel
    {
        const std::size_t t = static_cast<std::size_t>(omp_get_thread_num());
        #pragma omp for schedule(static)
        for (long long i = 0; i < n; ++i) {
            const long long v = values[static_cast<std::size_t>(i)];
            partial[t].stats.sum += v;
            if (v > threshold) ++partial[t].stats.above;
            if (v % 2 == 0) ++partial[t].stats.even;
        }
    }
    Stats total;
    for (const PaddedStats& p : partial) {
        total.sum += p.stats.sum;
        total.above += p.stats.above;
        total.even += p.stats.even;
    }
    return total;
}

bool test_serial_known_result() {
    std::vector<long long> values = {1, 2, 3, 4, 10, 11};
    Stats stats = compute_stats_serial(values, 3);
    return stats.sum == 31 && stats.above == 3 && stats.even == 3;
}

bool test_parallel_matches_serial_for_many_sizes_and_threads() {
    const std::size_t sizes[] = {0, 1, 5, 64, 1000, 99991};
    const int thread_counts[] = {1, 2, 3, 8};
    for (int threads : thread_counts) {
        omp_set_num_threads(threads);
        for (std::size_t size : sizes) {
            std::vector<long long> values = make_random_values(size, /*seed=*/3, /*max_value=*/1000);
            if (!(compute_stats_parallel(values, 400) == compute_stats_serial(values, 400))) return false;
        }
    }
    return true;
}

bool test_parallel_matches_serial_large_repeated() {
    omp_set_num_threads(8);
    std::vector<long long> values = make_random_values(3000000, /*seed=*/12, /*max_value=*/1000000);
    Stats expected = compute_stats_serial(values, 500000);
    for (int trial = 0; trial < 5; ++trial) {
        if (!(compute_stats_parallel(values, 500000) == expected)) return false;
    }
    return true;
}

bool test_format_stats() {
    Stats stats;
    stats.sum = 10;
    stats.above = 2;
    stats.even = 1;
    return format_stats(stats, 4) == "count=4 sum=10 above=2 even=1 mean=2.5";
}

// Performance check: the candidate must be about as fast as the reference
// with cache-line padded slots. With false sharing it is typically 3x-20x
// slower than that; fixes that use private variables or a reduction are faster. Needs real parallel hardware: skipped on
// machines with fewer than 4 hardware threads unless FORCE_PERF_TEST is set.
bool test_parallel_has_no_false_sharing() {
    if (std::getenv("FORCE_PERF_TEST") == nullptr && omp_get_num_procs() < 4) {
        std::cout << "[SKIP] performance check needs >= 4 hardware threads" << std::endl;
        return true;
    }
    const int threads = std::min(8, omp_get_num_procs());
    omp_set_dynamic(0);
    omp_set_num_threads(threads);

    std::vector<long long> values = make_random_values(12000000, /*seed=*/21, /*max_value=*/1000000);
    const long long threshold = 500000;
    const Stats expected = compute_stats_serial(values, threshold);

    auto best_time = [&](auto&& function) {
        double best = 1e30;
        for (int run = 0; run < 7; ++run) {
            auto start = std::chrono::steady_clock::now();
            Stats result = function(values, threshold);
            auto stop = std::chrono::steady_clock::now();
            if (!(result == expected)) return -1.0;
            best = std::min(best, std::chrono::duration<double>(stop - start).count());
        }
        return best;
    };

    best_time(reference_stats_parallel);  // warm-up (thread pool, page faults)
    const double reference = best_time(reference_stats_parallel);
    const double candidate = best_time(compute_stats_parallel);
    if (reference < 0.0 || candidate < 0.0) return false;

    std::cout << "       candidate " << candidate * 1000.0 << " ms, reference " << reference * 1000.0
              << " ms (limit: 2.5x reference), threads=" << threads << std::endl;
    return candidate <= 2.5 * reference;
}

}  // namespace

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"serial_known_result", test_serial_known_result},
        {"parallel_matches_serial_for_many_sizes_and_threads", test_parallel_matches_serial_for_many_sizes_and_threads},
        {"parallel_matches_serial_large_repeated", test_parallel_matches_serial_large_repeated},
        {"format_stats", test_format_stats},
        {"parallel_has_no_false_sharing", test_parallel_has_no_false_sharing}
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

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <vector>

#include "iteration_map.h"
#include "mandelbrot.h"
#include "render.h"

#include <omp.h>

namespace {

const Viewport kView{-2.0, 0.8, -1.2, 1.2, 400};
const std::size_t kRows = 160;
const std::size_t kCols = 240;

bool test_mandelbrot_point_known_values() {
    return mandelbrot_point(0.0, 0.0, 100) == 100 &&   // inside the set
           mandelbrot_point(2.0, 2.0, 100) == 1 &&     // escapes immediately
           mandelbrot_point(-1.0, 0.0, 100) == 100;    // period-2 bulb
}

bool test_parallel_map_matches_serial() {
    omp_set_num_threads(8);
    IterationMap expected(kRows, kCols);
    compute_mandelbrot_serial(kView, expected);
    for (int trial = 0; trial < 5; ++trial) {
        IterationMap actual(kRows, kCols);
        compute_mandelbrot_parallel(kView, actual);
        if (!(actual == expected)) return false;
    }
    return true;
}

bool test_parallel_total_matches_serial_repeated() {
    omp_set_num_threads(8);
    IterationMap reference(kRows, kCols);
    const long long expected = compute_mandelbrot_serial(kView, reference);
    for (int trial = 0; trial < 20; ++trial) {
        IterationMap map(kRows, kCols);
        if (compute_mandelbrot_parallel(kView, map) != expected) return false;
    }
    return true;
}

bool test_row_owner_is_reported() {
    omp_set_num_threads(4);
    IterationMap map(64, 64);
    std::vector<int> owner;
    compute_mandelbrot_parallel(kView, map, &owner);
    if (owner.size() != map.rows()) return false;
    for (int id : owner) {
        if (id < 0 || id >= 4) return false;
    }
    return true;
}

// Work balance: the busiest thread must not carry much more than the average.
// Static block scheduling gives the central rows (which cost the most
// iterations) to one or two threads and fails this check. Dynamic or cyclic
// schedules pass. The check needs real parallel hardware; it is skipped on
// machines with fewer than 4 hardware threads unless FORCE_BALANCE_TEST is set.
bool test_work_is_balanced_across_threads() {
    if (std::getenv("FORCE_BALANCE_TEST") == nullptr && omp_get_num_procs() < 4) {
        std::cout << "[SKIP] work balance check needs >= 4 hardware threads" << std::endl;
        return true;
    }
    const int threads = 4;
    omp_set_dynamic(0);
    omp_set_num_threads(threads);

    double worst_ratio = 0.0;
    for (int trial = 0; trial < 3; ++trial) {
        IterationMap map(kRows, kCols);
        std::vector<int> owner;
        compute_mandelbrot_parallel(kView, map, &owner);

        std::vector<long long> work(threads, 0);
        long long all = 0;
        for (std::size_t r = 0; r < map.rows(); ++r) {
            long long w = map.row_work(r);
            work[static_cast<std::size_t>(owner[r])] += w;
            all += w;
        }
        const double mean = static_cast<double>(all) / threads;
        const double busiest = static_cast<double>(*std::max_element(work.begin(), work.end()));
        worst_ratio = std::max(worst_ratio, busiest / mean);
    }
    std::cout << "       busiest/mean work ratio: " << worst_ratio << std::endl;
    return worst_ratio < 1.25;
}

}  // namespace

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"mandelbrot_point_known_values", test_mandelbrot_point_known_values},
        {"parallel_map_matches_serial", test_parallel_map_matches_serial},
        {"parallel_total_matches_serial_repeated", test_parallel_total_matches_serial_repeated},
        {"row_owner_is_reported", test_row_owner_is_reported},
        {"work_is_balanced_across_threads", test_work_is_balanced_across_threads}
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

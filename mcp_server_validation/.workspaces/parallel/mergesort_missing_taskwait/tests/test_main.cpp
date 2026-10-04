#include <algorithm>
#include <functional>
#include <iostream>
#include <numeric>
#include <vector>

#include "data_gen.h"
#include "sort.h"

#include <omp.h>

namespace {

bool matches_std_sort(std::vector<int> values) {
    std::vector<int> expected = values;
    std::sort(expected.begin(), expected.end());
    merge_sort_parallel(values);
    return values == expected;
}

bool test_serial_sort_basic() {
    std::vector<int> values = {5, 2, 9, 1, 5, 6, 0, -3};
    merge_sort_serial(values);
    return values == std::vector<int>({-3, 0, 1, 2, 5, 5, 6, 9});
}

bool test_parallel_sort_tiny_inputs() {
    omp_set_num_threads(8);
    return matches_std_sort({}) && matches_std_sort({1}) && matches_std_sort({2, 1}) &&
           matches_std_sort({3, 1, 2}) && matches_std_sort({1, 1, 1, 1});
}

bool test_parallel_sort_random_inputs() {
    omp_set_num_threads(8);
    const std::size_t sizes[] = {100, kTaskCutoff, kTaskCutoff + 1, 10007, 250000};
    for (std::size_t size : sizes) {
        if (!matches_std_sort(make_random_ints(size, /*seed=*/static_cast<unsigned>(size), 1000000))) {
            return false;
        }
    }
    return true;
}

bool test_parallel_sort_special_patterns() {
    omp_set_num_threads(8);
    std::vector<int> ascending(100000);
    std::iota(ascending.begin(), ascending.end(), 0);
    std::vector<int> descending(ascending.rbegin(), ascending.rend());
    std::vector<int> few_distinct = make_random_ints(100000, /*seed=*/4, /*max_value=*/3);
    return matches_std_sort(ascending) && matches_std_sort(descending) && matches_std_sort(few_distinct);
}

bool test_parallel_sort_repeated_with_different_thread_counts() {
    const int thread_counts[] = {1, 2, 3, 8};
    std::vector<int> original = make_random_ints(400000, /*seed=*/123, /*max_value=*/5000000);
    for (int threads : thread_counts) {
        omp_set_num_threads(threads);
        for (int trial = 0; trial < 3; ++trial) {
            if (!matches_std_sort(original)) return false;
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
        {"serial_sort_basic", test_serial_sort_basic},
        {"parallel_sort_tiny_inputs", test_parallel_sort_tiny_inputs},
        {"parallel_sort_random_inputs", test_parallel_sort_random_inputs},
        {"parallel_sort_special_patterns", test_parallel_sort_special_patterns},
        {"parallel_sort_repeated_with_different_thread_counts", test_parallel_sort_repeated_with_different_thread_counts}
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

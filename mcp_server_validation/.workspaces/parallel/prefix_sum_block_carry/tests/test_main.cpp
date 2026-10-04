#include <iostream>
#include <utility>
#include <vector>

#include "data_gen.h"
#include "prefix_sum.h"
#include "range_query.h"

#include <omp.h>

namespace {

bool test_serial_scan_known_result() {
    std::vector<long long> input = {3, -1, 4, 1, -5, 9};
    std::vector<long long> expected = {3, 2, 6, 7, 2, 11};
    return inclusive_scan_serial(input) == expected;
}

bool test_parallel_scan_matches_serial_for_many_sizes() {
    const std::size_t sizes[] = {0, 1, 2, 3, 7, 8, 9, 100, 1001, 65537};
    const int thread_counts[] = {1, 2, 3, 4, 8};
    for (int threads : thread_counts) {
        omp_set_num_threads(threads);
        for (std::size_t size : sizes) {
            std::vector<long long> input = make_random_vector(size, /*seed=*/31, /*max_abs=*/1000);
            if (inclusive_scan_parallel(input) != inclusive_scan_serial(input)) return false;
        }
    }
    return true;
}

bool test_parallel_scan_large_input_repeated() {
    omp_set_num_threads(8);
    std::vector<long long> input = make_random_vector(2000000, /*seed=*/77, /*max_abs=*/50);
    std::vector<long long> expected = inclusive_scan_serial(input);
    for (int trial = 0; trial < 5; ++trial) {
        if (inclusive_scan_parallel(input) != expected) return false;
    }
    return true;
}

bool test_scan_of_all_ones_is_index_plus_one() {
    omp_set_num_threads(6);
    std::vector<long long> input(50000, 1);
    std::vector<long long> output = inclusive_scan_parallel(input);
    for (std::size_t i = 0; i < output.size(); ++i) {
        if (output[i] != static_cast<long long>(i) + 1) return false;
    }
    return true;
}

bool test_range_sum_queries() {
    omp_set_num_threads(8);
    std::vector<long long> data = make_random_vector(30000, /*seed=*/5, /*max_abs=*/500);
    std::vector<std::pair<std::size_t, std::size_t>> queries = {
        {0, 0}, {0, 29999}, {1, 1}, {100, 20000}, {29999, 29999}, {12345, 23456}};

    std::vector<long long> answers = answer_range_sums(data, queries);
    for (std::size_t q = 0; q < queries.size(); ++q) {
        long long expected = 0;
        for (std::size_t i = queries[q].first; i <= queries[q].second; ++i) expected += data[i];
        if (answers[q] != expected) return false;
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
        {"serial_scan_known_result", test_serial_scan_known_result},
        {"parallel_scan_matches_serial_for_many_sizes", test_parallel_scan_matches_serial_for_many_sizes},
        {"parallel_scan_large_input_repeated", test_parallel_scan_large_input_repeated},
        {"scan_of_all_ones_is_index_plus_one", test_scan_of_all_ones_is_index_plus_one},
        {"range_sum_queries", test_range_sum_queries}
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

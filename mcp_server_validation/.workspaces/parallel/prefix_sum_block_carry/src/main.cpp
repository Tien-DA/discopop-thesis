#include <iostream>
#include <utility>
#include <vector>

#include "data_gen.h"
#include "prefix_sum.h"
#include "range_query.h"

int main() {
    std::vector<long long> data = make_random_vector(2000, /*seed=*/17, /*max_abs=*/100);

    std::vector<long long> prefix = inclusive_scan_parallel(data);
    std::vector<std::pair<std::size_t, std::size_t>> queries = {{0, 1999}, {10, 20}, {500, 1500}};
    std::vector<long long> answers = answer_range_sums(data, queries);

    std::cout << "last prefix value: " << prefix.back() << std::endl;
    for (long long answer : answers) {
        std::cout << "range sum: " << answer << std::endl;
    }
    return 0;
}

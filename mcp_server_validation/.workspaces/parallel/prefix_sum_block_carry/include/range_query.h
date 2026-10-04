#pragma once

#include <cstddef>
#include <utility>
#include <vector>

// Answers "sum of data[l..r]" (inclusive) queries using a prefix-sum table
// built with inclusive_scan_parallel().
std::vector<long long> answer_range_sums(
    const std::vector<long long>& data,
    const std::vector<std::pair<std::size_t, std::size_t>>& queries);

#pragma once

#include <cstddef>
#include <vector>

// Deterministic vector of integers in [0, max_value].
std::vector<int> make_random_ints(std::size_t size, unsigned seed, int max_value);

bool is_sorted_ascending(const std::vector<int>& values);

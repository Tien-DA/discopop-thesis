#pragma once

#include <cstddef>
#include <vector>

// Deterministic vector of integers in [0, max_value].
std::vector<long long> make_random_values(std::size_t size, unsigned seed, long long max_value);

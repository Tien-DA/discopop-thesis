#pragma once

#include <cstddef>
#include <vector>

// Deterministic vector of integers in [-max_abs, max_abs].
std::vector<long long> make_random_vector(std::size_t size, unsigned seed, int max_abs);

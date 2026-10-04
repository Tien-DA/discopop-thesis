#pragma once

#include <cstddef>
#include <cstdint>

// Applies mix64() 'rounds' times.
uint64_t spread(uint64_t value, unsigned rounds);

// Combines data[center - radius .. center + radius] (indices clamped).
uint64_t fold_range(const uint64_t* data, std::size_t n, std::size_t center, unsigned radius);

std::size_t clamp_index(long index, std::size_t n);

// Order dependent digest of a whole array.
uint64_t digest_span(const uint64_t* data, std::size_t n);

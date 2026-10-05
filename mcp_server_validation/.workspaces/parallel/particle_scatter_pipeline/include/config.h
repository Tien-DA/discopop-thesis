#pragma once
#include <cstddef>
constexpr std::size_t kMaxScratch = 4096;
constexpr std::size_t kPoolSlots = 8;
struct Config { std::size_t items; std::size_t scratch_len; std::size_t blocks; };
inline Config profiling_config() { return Config{112, 28, 14}; }
inline Config discopop_profiling_config() { return Config{28, 7, 2}; }
inline Config stress_config() { return Config{1792, 896, 16}; }

#pragma once
#include <cstddef>
constexpr std::size_t kMaxScratch = 4096;
constexpr std::size_t kPoolSlots = 8;
struct Config { std::size_t items; std::size_t scratch_len; std::size_t blocks; };
inline Config profiling_config() { return Config{80, 20, 10}; }
inline Config discopop_profiling_config() { return Config{20, 6, 2}; }
inline Config stress_config() { return Config{1280, 640, 16}; }

#pragma once
#include <cstddef>
constexpr std::size_t kMaxScratch = 4096;
constexpr std::size_t kPoolSlots = 8;
struct Config { std::size_t items; std::size_t scratch_len; std::size_t blocks; };
inline Config profiling_config() { return Config{96, 24, 12}; }
inline Config discopop_profiling_config() { return Config{24, 8, 4}; }
inline Config stress_config() { return Config{1536, 768, 16}; }

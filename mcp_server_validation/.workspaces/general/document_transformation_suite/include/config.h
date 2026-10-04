#pragma once

#include <cstddef>

// Upper bound for every per-item scratch window used by the kernels.
constexpr std::size_t kMaxScratch = 4096;
// Number of pre-allocated slots of the WorkspacePool.
constexpr std::size_t kPoolSlots = 8;

struct Config {
    std::size_t items;        // elements per working buffer
    std::size_t scratch_len;  // length of the per-item scratch window
    std::size_t blocks;       // number of coarse blocks (<= kPoolSlots)
};

// Small workload used by the profiling entry point (src/main.cpp).
inline Config profiling_config() { return Config{64, 16, 8}; }
inline Config discopop_profiling_config() { return Config{16, 4, 2}; }
// Large workload used by the correctness harness.
inline Config stress_config() { return Config{1024, 1024, 8}; }

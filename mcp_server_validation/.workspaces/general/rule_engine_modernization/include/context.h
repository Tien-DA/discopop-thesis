#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "config.h"
#include "workspace.h"

// Shared state of the whole pipeline: six working buffers that the stages
// read and write, index tables and a few aggregate counters.
struct Context {
    static constexpr int kBuffers = 6;

    Context(const Config& config, uint64_t seed);

    Config cfg;
    std::vector<uint64_t> buf[kBuffers];
    std::vector<uint32_t> perm;      // permutation of [0, items)
    std::vector<uint32_t> table;     // gather table, values in [0, items)
    std::vector<uint64_t> partial;   // one slot per block
    std::vector<uint64_t> work;      // general purpose scratch area
    WorkspacePool pool;
    uint64_t hits = 0;
    uint64_t peak = 0;
};

// Order dependent digest of everything the stages produce.
uint64_t checksum(const Context& ctx);

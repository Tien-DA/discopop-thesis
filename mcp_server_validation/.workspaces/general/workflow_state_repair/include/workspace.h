#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "config.h"

// Pool of pre-allocated scratch windows. acquire(key) hands out the slot
// that belongs to 'key'.
class WorkspacePool {
public:
    WorkspacePool();
    uint64_t* acquire(std::size_t key);

private:
    std::vector<std::vector<uint64_t>> slots_;
};

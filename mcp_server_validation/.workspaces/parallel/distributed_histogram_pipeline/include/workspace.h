#pragma once

#include <cstddef>
#include <cstdint>

#include "config.h"

// Each OpenMP worker receives an independent reusable scratch window.
class WorkspacePool {
public:
    WorkspacePool() = default;
    uint64_t* acquire(std::size_t key);
};

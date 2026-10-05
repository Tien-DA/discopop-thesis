#include "workspace.h"

#include <vector>

uint64_t* WorkspacePool::acquire(std::size_t) {
    thread_local std::vector<uint64_t> scratch(kMaxScratch, 0);
    return scratch.data();
}

#include "workspace.h"

WorkspacePool::WorkspacePool() : slots_(kPoolSlots, std::vector<uint64_t>(kMaxScratch, 0)) {}

uint64_t* WorkspacePool::acquire(std::size_t key) {
    return slots_[key % kPoolSlots].data();
}

#pragma once

#include <vector>

// Ranges at or below this size are sorted sequentially instead of spawning
// more OpenMP tasks.
constexpr std::size_t kTaskCutoff = 2048;

void merge_sort_serial(std::vector<int>& values);

// Task-parallel merge sort; must produce exactly the sorted sequence.
void merge_sort_parallel(std::vector<int>& values);

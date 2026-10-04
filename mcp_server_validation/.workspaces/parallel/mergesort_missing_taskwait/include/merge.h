#pragma once

#include <cstddef>

// Merges the sorted ranges data[lo, mid) and data[mid, hi) into one sorted
// range data[lo, hi), using tmp[lo, hi) as scratch space.
void merge_ranges(int* data, int* tmp, std::size_t lo, std::size_t mid, std::size_t hi);

// Sequential top-down merge sort of data[lo, hi) (tmp is scratch space).
void merge_sort_range_serial(int* data, int* tmp, std::size_t lo, std::size_t hi);

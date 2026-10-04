#include "merge.h"

void merge_ranges(int* data, int* tmp, std::size_t lo, std::size_t mid, std::size_t hi) {
    std::size_t left = lo;
    std::size_t right = mid;
    std::size_t out = lo;
    while (left < mid && right < hi) {
        if (data[right] < data[left]) {
            tmp[out++] = data[right++];
        } else {
            tmp[out++] = data[left++];
        }
    }
    while (left < mid) tmp[out++] = data[left++];
    while (right < hi) tmp[out++] = data[right++];
    for (std::size_t i = lo; i < hi; ++i) {
        data[i] = tmp[i];
    }
}

void merge_sort_range_serial(int* data, int* tmp, std::size_t lo, std::size_t hi) {
    if (hi - lo < 2) {
        return;
    }
    const std::size_t mid = lo + (hi - lo) / 2;
    merge_sort_range_serial(data, tmp, lo, mid);
    merge_sort_range_serial(data, tmp, mid, hi);
    merge_ranges(data, tmp, lo, mid, hi);
}

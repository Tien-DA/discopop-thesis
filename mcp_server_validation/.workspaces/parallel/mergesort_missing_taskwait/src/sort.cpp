#include "sort.h"

#include "merge.h"

void merge_sort_serial(std::vector<int>& values) {
    std::vector<int> tmp(values.size());
    merge_sort_range_serial(values.data(), tmp.data(), 0, values.size());
}

namespace {

void sort_with_tasks(int* data, int* tmp, std::size_t lo, std::size_t hi) {
    if (hi - lo <= kTaskCutoff) {
        merge_sort_range_serial(data, tmp, lo, hi);
        return;
    }
    const std::size_t mid = lo + (hi - lo) / 2;

    #pragma omp task
    sort_with_tasks(data, tmp, lo, mid);

    #pragma omp task
    sort_with_tasks(data, tmp, mid, hi);

    // BUG: there is no '#pragma omp taskwait' here. Both child tasks are
    // only *queued*; the merge below runs immediately on halves that are
    // still unsorted (and keeps racing with the children afterwards), so the
    // result is not sorted.
    merge_ranges(data, tmp, lo, mid, hi);
}

}  // namespace

void merge_sort_parallel(std::vector<int>& values) {
    if (values.size() < 2) {
        return;
    }
    std::vector<int> tmp(values.size());
    int* data = values.data();
    int* scratch = tmp.data();
    const std::size_t n = values.size();

    #pragma omp parallel
    {
        #pragma omp single
        sort_with_tasks(data, scratch, 0, n);
    }
}

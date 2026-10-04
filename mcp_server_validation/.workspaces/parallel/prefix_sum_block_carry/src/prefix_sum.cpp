#include "prefix_sum.h"

#include <omp.h>

std::vector<long long> inclusive_scan_serial(const std::vector<long long>& input) {
    std::vector<long long> output(input.size());
    long long running = 0;
    for (std::size_t i = 0; i < input.size(); ++i) {
        running += input[i];
        output[i] = running;
    }
    return output;
}

// BUG: the array is split into one contiguous block per thread and every
// thread scans only its own block. A scan has a loop-carried dependency
// (element i needs the sum of everything before it), so each block must also
// be shifted by the total of all preceding blocks. That second pass is
// missing: every block starts counting from zero and the output is only
// correct for the first block.
std::vector<long long> inclusive_scan_parallel(const std::vector<long long>& input) {
    const std::size_t n = input.size();
    std::vector<long long> output(n);

    #pragma omp parallel
    {
        const std::size_t t = static_cast<std::size_t>(omp_get_thread_num());
        const std::size_t threads = static_cast<std::size_t>(omp_get_num_threads());
        const std::size_t lo = n * t / threads;
        const std::size_t hi = n * (t + 1) / threads;

        long long running = 0;
        for (std::size_t i = lo; i < hi; ++i) {
            running += input[i];
            output[i] = running;
        }
    }
    return output;
}

#include "stats.h"

#include <omp.h>

bool operator==(const Stats& a, const Stats& b) {
    return a.sum == b.sum && a.above == b.above && a.even == b.even;
}

Stats compute_stats_serial(const std::vector<long long>& values, long long threshold) {
    Stats stats;
    for (std::size_t i = 0; i < values.size(); ++i) {
        const long long v = values[i];
        stats.sum += v;
        if (v > threshold) ++stats.above;
        if (v % 2 == 0) ++stats.even;
    }
    return stats;
}

// PERFORMANCE BUG (false sharing): the per-thread partial results live in a
// tightly packed std::vector<Stats>. A Stats object is only 24 bytes, so the
// slots of several threads share the same 64-byte cache line. Every
// iteration writes to partial[t], so each write invalidates the cache line
// in the other cores' caches and the threads spend their time bouncing
// cache lines around instead of computing. The result is correct, but the
// parallel version is many times slower than it should be (often slower
// than the serial version).
Stats compute_stats_parallel(const std::vector<long long>& values, long long threshold) {
    const int max_threads = omp_get_max_threads();
    std::vector<Stats> partial(static_cast<std::size_t>(max_threads));
    const long long n = static_cast<long long>(values.size());

    #pragma omp parallel
    {
        const std::size_t t = static_cast<std::size_t>(omp_get_thread_num());

        #pragma omp for schedule(static)
        for (long long i = 0; i < n; ++i) {
            const long long v = values[static_cast<std::size_t>(i)];
            partial[t].sum += v;
            if (v > threshold) ++partial[t].above;
            if (v % 2 == 0) ++partial[t].even;
        }
    }

    Stats total;
    for (const Stats& p : partial) {
        total.sum += p.sum;
        total.above += p.above;
        total.even += p.even;
    }
    return total;
}

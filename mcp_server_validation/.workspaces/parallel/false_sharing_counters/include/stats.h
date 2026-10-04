#pragma once

#include <vector>

struct Stats {
    long long sum = 0;          // sum of all values
    long long above = 0;        // how many values are > threshold
    long long even = 0;         // how many values are even
};

bool operator==(const Stats& a, const Stats& b);

// Sequential reference implementation.
Stats compute_stats_serial(const std::vector<long long>& values, long long threshold);

// OpenMP implementation. Must return exactly the same statistics as the
// serial version and must scale with the number of threads.
Stats compute_stats_parallel(const std::vector<long long>& values, long long threshold);

#pragma once

#include <vector>

// Inclusive prefix sum: output[i] = input[0] + ... + input[i].
std::vector<long long> inclusive_scan_serial(const std::vector<long long>& input);

// OpenMP version; must return exactly the same vector as the serial one for
// every input size and every number of threads.
std::vector<long long> inclusive_scan_parallel(const std::vector<long long>& input);

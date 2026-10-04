#pragma once

#include <cstddef>
#include <vector>

// Three-stage threaded pipeline:
//   producer thread  --queue A-->  'workers' transform threads  --queue B-->  collector thread
// Each input x is transformed to x * x + 1 and the collector sums the
// results. Both queues have the given capacity. Returns that sum.
// The result must not depend on thread timing, and the call must terminate.
long long run_pipeline(const std::vector<int>& input, std::size_t queue_capacity, int workers);

// Sequential reference: sum of (x * x + 1) over the input.
long long pipeline_reference(const std::vector<int>& input);

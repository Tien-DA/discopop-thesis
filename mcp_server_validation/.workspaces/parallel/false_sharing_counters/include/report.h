#pragma once

#include <cstddef>
#include <string>

#include "stats.h"

// One-line human readable summary of the statistics of 'count' values.
std::string format_stats(const Stats& stats, std::size_t count);

#pragma once

#include <string>
#include <vector>

#include "iteration_map.h"

// Converts an iteration map into ASCII art, one string per row.
std::vector<std::string> render_ascii(const IterationMap& map, int max_iterations);

// Fraction of pixels that never escaped (an estimate of the set's area share).
double inside_fraction(const IterationMap& map, int max_iterations);

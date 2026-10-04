#pragma once

#include <array>

#include "matrix.h"

constexpr int kHistogramBins = 256;

std::array<int, kHistogramBins> compute_histogram_serial(const Matrix& image);
std::array<int, kHistogramBins> compute_histogram_parallel(const Matrix& image);
#include "histogram.h"

#include <omp.h>

std::array<int, kHistogramBins> compute_histogram_serial(const Matrix& image) {
    std::array<int, kHistogramBins> histogram{};
    for (std::size_t r = 0; r < image.rows(); ++r) {
        for (std::size_t c = 0; c < image.cols(); ++c) {
            int value = image.at(r, c);
            ++histogram[static_cast<std::size_t>(value)];
        }
    }
    return histogram;
}

// BUG: every thread increments the same shared 'histogram' array with no
// synchronization or reduction. Concurrent read-modify-write on the same
// bin loses updates under contention, so bin counts (and their sum) do
// not match the serial reference.
std::array<int, kHistogramBins> compute_histogram_parallel(const Matrix& image) {
    std::array<int, kHistogramBins> histogram{};
    const std::size_t rows = image.rows();
    const std::size_t cols = image.cols();

    #pragma omp parallel for
    for (std::size_t r = 0; r < rows; ++r) {
        for (std::size_t c = 0; c < cols; ++c) {
            int value = image.at(r, c);
            ++histogram[static_cast<std::size_t>(value)];
        }
    }
    return histogram;
}
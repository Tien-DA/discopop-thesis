#include "pipeline.h"

#include <array>

#include "histogram.h"

Matrix equalize_histogram(const Matrix& image, int max_value) {
    auto histogram = compute_histogram_parallel(image);

    std::array<int, kHistogramBins> cdf{};
    int running = 0;
    for (int i = 0; i < kHistogramBins; ++i) {
        running += histogram[i];
        cdf[i] = running;
    }

    int total = running;
    Matrix output(image.rows(), image.cols());
    if (total == 0) {
        return output;
    }

    for (std::size_t r = 0; r < image.rows(); ++r) {
        for (std::size_t c = 0; c < image.cols(); ++c) {
            int value = image.at(r, c);
            double normalized = static_cast<double>(cdf[static_cast<std::size_t>(value)]) / total;
            output.at(r, c) = static_cast<int>(normalized * max_value);
        }
    }
    return output;
}
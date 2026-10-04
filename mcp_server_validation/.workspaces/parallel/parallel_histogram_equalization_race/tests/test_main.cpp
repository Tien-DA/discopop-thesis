#include <array>
#include <iostream>

#include "histogram.h"
#include "matrix.h"
#include "pipeline.h"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

bool test_serial_histogram_basic() {
    Matrix image(4, 4, 0);
    image.at(0, 0) = 10;
    image.at(1, 1) = 10;
    image.at(2, 2) = 200;
    auto histogram = compute_histogram_serial(image);
    return histogram[0] == 13 && histogram[10] == 2 && histogram[200] == 1;
}

bool test_parallel_histogram_matches_serial_repeated() {
#ifdef _OPENMP
    omp_set_num_threads(8);
#endif
    Matrix image = make_random_matrix(256, 256, /*seed=*/7, /*max_value=*/255);
    auto serial = compute_histogram_serial(image);

    const int total_pixels = static_cast<int>(image.rows() * image.cols());

    for (int trial = 0; trial < 20; ++trial) {
        auto parallel = compute_histogram_parallel(image);

        int parallel_total = 0;
        for (int bin : parallel) {
            parallel_total += bin;
        }
        if (parallel_total != total_pixels) {
            return false;
        }

        if (parallel != serial) {
            return false;
        }
    }
    return true;
}

bool test_equalize_histogram_preserves_pixel_count() {
    Matrix image = make_random_matrix(64, 64, /*seed=*/3, /*max_value=*/255);
    Matrix equalized = equalize_histogram(image, 255);
    return equalized.rows() == image.rows() && equalized.cols() == image.cols();
}

bool test_equalize_histogram_output_range() {
    Matrix image = make_random_matrix(64, 64, /*seed=*/9, /*max_value=*/255);
    Matrix equalized = equalize_histogram(image, 255);
    for (std::size_t r = 0; r < equalized.rows(); ++r) {
        for (std::size_t c = 0; c < equalized.cols(); ++c) {
            int value = equalized.at(r, c);
            if (value < 0 || value > 255) {
                return false;
            }
        }
    }
    return true;
}

bool test_equalize_histogram_matches_serial_reference() {
    // A reference implementation built directly on the serial histogram
    // must match equalize_histogram()'s output once the parallel race is
    // fixed, since both should compute the same cumulative distribution.
    Matrix image = make_random_matrix(64, 64, /*seed=*/11, /*max_value=*/255);

    auto serial_hist = compute_histogram_serial(image);
    std::array<int, kHistogramBins> cdf{};
    int running = 0;
    for (int i = 0; i < kHistogramBins; ++i) {
        running += serial_hist[i];
        cdf[i] = running;
    }
    int total = running;

    Matrix reference(image.rows(), image.cols());
    for (std::size_t r = 0; r < image.rows(); ++r) {
        for (std::size_t c = 0; c < image.cols(); ++c) {
            int value = image.at(r, c);
            double normalized = static_cast<double>(cdf[static_cast<std::size_t>(value)]) / total;
            reference.at(r, c) = static_cast<int>(normalized * 255);
        }
    }

    Matrix actual = equalize_histogram(image, 255);
    for (std::size_t r = 0; r < image.rows(); ++r) {
        for (std::size_t c = 0; c < image.cols(); ++c) {
            if (actual.at(r, c) != reference.at(r, c)) {
                return false;
            }
        }
    }
    return true;
}

}  // namespace

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"serial_histogram_basic", test_serial_histogram_basic},
        {"parallel_histogram_matches_serial_repeated", test_parallel_histogram_matches_serial_repeated},
        {"equalize_histogram_preserves_pixel_count", test_equalize_histogram_preserves_pixel_count},
        {"equalize_histogram_output_range", test_equalize_histogram_output_range},
        {"equalize_histogram_matches_serial_reference", test_equalize_histogram_matches_serial_reference}
    };

    int failures = 0;
    for (const Test& test : tests) {
        bool passed = test.function();
        if (passed) {
            std::cout << "[PASS] " << test.name << std::endl;
        } else {
            std::cerr << "[FAIL] " << test.name << std::endl;
            ++failures;
        }
    }

    if (failures > 0) {
        std::cerr << failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}
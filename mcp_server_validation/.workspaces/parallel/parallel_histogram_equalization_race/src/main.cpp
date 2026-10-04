#include <iostream>

#include "matrix.h"
#include "pipeline.h"

int main() {
    Matrix image = make_random_matrix(128, 128, /*seed=*/42, /*max_value=*/255);
    Matrix equalized = equalize_histogram(image, 255);

    long sum = 0;
    for (std::size_t r = 0; r < equalized.rows(); ++r) {
        for (std::size_t c = 0; c < equalized.cols(); ++c) {
            sum += equalized.at(r, c);
        }
    }

    std::cout << "equalized pixel sum: " << sum << std::endl;
    std::cout << "rows: " << equalized.rows() << ", cols: " << equalized.cols() << std::endl;
    return 0;
}
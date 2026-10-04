#include "matmul.h"

#include <vector>

Matrix multiply_serial(const Matrix& a, const Matrix& b) {
    const std::size_t n = a.rows();
    const std::size_t m = a.cols();
    const std::size_t p = b.cols();
    Matrix c(n, p, 0);
    for (std::size_t i = 0; i < n; ++i) {
        for (std::size_t j = 0; j < p; ++j) {
            long long sum = 0;
            for (std::size_t k = 0; k < m; ++k) {
                sum += a.at(i, k) * b.at(k, j);
            }
            c.at(i, j) = sum;
        }
    }
    return c;
}

// BUG: row i of A is first copied into 'row_buffer' (intended as a
// cache-friendly staging area), but the buffer is declared outside the
// parallel loop and is therefore shared by all threads. While one thread is
// still multiplying with its copy of row i, another thread overwrites the
// buffer with a different row, so the products mix entries of different rows
// of A and the result differs from multiply_serial().
Matrix multiply_parallel(const Matrix& a, const Matrix& b) {
    const std::size_t n = a.rows();
    const std::size_t m = a.cols();
    const std::size_t p = b.cols();
    Matrix c(n, p, 0);

    std::vector<long long> row_buffer(m);

    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        for (std::size_t k = 0; k < m; ++k) {
            row_buffer[k] = a.at(i, k);
        }
        for (std::size_t j = 0; j < p; ++j) {
            long long sum = 0;
            for (std::size_t k = 0; k < m; ++k) {
                sum += row_buffer[k] * b.at(k, j);
            }
            c.at(i, j) = sum;
        }
    }
    return c;
}

Matrix transpose_parallel(const Matrix& a) {
    Matrix t(a.cols(), a.rows(), 0);

    #pragma omp parallel for
    for (std::size_t i = 0; i < a.rows(); ++i) {
        for (std::size_t j = 0; j < a.cols(); ++j) {
            t.at(j, i) = a.at(i, j);
        }
    }
    return t;
}

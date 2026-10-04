#include "pipeline.h"

#include "matmul.h"

Matrix compute_gram_matrix(const Matrix& a) {
    Matrix at = transpose_parallel(a);
    return multiply_parallel(a, at);
}

long long trace(const Matrix& m) {
    long long sum = 0;
    const std::size_t n = m.rows() < m.cols() ? m.rows() : m.cols();
    for (std::size_t i = 0; i < n; ++i) {
        sum += m.at(i, i);
    }
    return sum;
}

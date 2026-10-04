#pragma once

#include <cstddef>
#include <vector>

// Simple row-major matrix of 64-bit integers. Integer arithmetic keeps
// every result exactly reproducible, independent of summation order.
class Matrix {
public:
    Matrix(std::size_t rows, std::size_t cols, long long value = 0);

    std::size_t rows() const;
    std::size_t cols() const;
    long long& at(std::size_t row, std::size_t col);
    long long at(std::size_t row, std::size_t col) const;

    bool operator==(const Matrix& other) const;

private:
    std::size_t rows_;
    std::size_t cols_;
    std::vector<long long> data_;
};

// Deterministic matrix with entries in [-max_abs, max_abs].
Matrix make_random_matrix(std::size_t rows, std::size_t cols, unsigned seed, int max_abs);

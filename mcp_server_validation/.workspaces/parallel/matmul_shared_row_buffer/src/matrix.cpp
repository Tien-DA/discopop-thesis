#include "matrix.h"

#include <random>

Matrix::Matrix(std::size_t rows, std::size_t cols, long long value)
    : rows_(rows), cols_(cols), data_(rows * cols, value) {}

std::size_t Matrix::rows() const {
    return rows_;
}

std::size_t Matrix::cols() const {
    return cols_;
}

long long& Matrix::at(std::size_t row, std::size_t col) {
    return data_.at(row * cols_ + col);
}

long long Matrix::at(std::size_t row, std::size_t col) const {
    return data_.at(row * cols_ + col);
}

bool Matrix::operator==(const Matrix& other) const {
    return rows_ == other.rows_ && cols_ == other.cols_ && data_ == other.data_;
}

Matrix make_random_matrix(std::size_t rows, std::size_t cols, unsigned seed, int max_abs) {
    Matrix matrix(rows, cols);
    std::mt19937 generator(seed);
    std::uniform_int_distribution<int> distribution(-max_abs, max_abs);
    for (std::size_t r = 0; r < rows; ++r) {
        for (std::size_t c = 0; c < cols; ++c) {
            matrix.at(r, c) = distribution(generator);
        }
    }
    return matrix;
}

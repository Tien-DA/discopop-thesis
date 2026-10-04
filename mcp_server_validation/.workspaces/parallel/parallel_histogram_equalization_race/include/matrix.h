#pragma once

#include <cstddef>
#include <vector>

class Matrix {
public:
    Matrix() = default;
    Matrix(std::size_t rows, std::size_t cols, int value = 0);

    std::size_t rows() const;
    std::size_t cols() const;

    int& at(std::size_t row, std::size_t col);
    int at(std::size_t row, std::size_t col) const;

private:
    std::size_t rows_ = 0;
    std::size_t cols_ = 0;
    std::vector<int> data_;
};

Matrix make_random_matrix(std::size_t rows, std::size_t cols, unsigned seed, int max_value);
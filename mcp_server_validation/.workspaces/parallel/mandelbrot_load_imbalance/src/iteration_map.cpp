#include "iteration_map.h"

IterationMap::IterationMap(std::size_t rows, std::size_t cols, int value)
    : rows_(rows), cols_(cols), data_(rows * cols, value) {}

std::size_t IterationMap::rows() const {
    return rows_;
}

std::size_t IterationMap::cols() const {
    return cols_;
}

int& IterationMap::at(std::size_t row, std::size_t col) {
    return data_.at(row * cols_ + col);
}

int IterationMap::at(std::size_t row, std::size_t col) const {
    return data_.at(row * cols_ + col);
}

long long IterationMap::row_work(std::size_t row) const {
    long long work = 0;
    for (std::size_t c = 0; c < cols_; ++c) {
        work += data_.at(row * cols_ + c);
    }
    return work;
}

bool IterationMap::operator==(const IterationMap& other) const {
    return rows_ == other.rows_ && cols_ == other.cols_ && data_ == other.data_;
}

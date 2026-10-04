#include "grid.h"

Grid::Grid(std::size_t rows, std::size_t cols, double value)
    : rows_(rows), cols_(cols), data_(rows * cols, value) {}

std::size_t Grid::rows() const {
    return rows_;
}

std::size_t Grid::cols() const {
    return cols_;
}

double& Grid::at(std::size_t row, std::size_t col) {
    return data_.at(row * cols_ + col);
}

double Grid::at(std::size_t row, std::size_t col) const {
    return data_.at(row * cols_ + col);
}

bool Grid::operator==(const Grid& other) const {
    return rows_ == other.rows_ && cols_ == other.cols_ && data_ == other.data_;
}

Grid make_hot_plate(std::size_t rows, std::size_t cols) {
    Grid grid(rows, cols, 0.0);
    for (std::size_t c = 0; c < cols; ++c) {
        grid.at(0, c) = 100.0;
    }
    for (std::size_t r = rows / 3; r < rows / 3 + rows / 6 + 1 && r + 1 < rows; ++r) {
        for (std::size_t c = cols / 3; c < cols / 3 + cols / 6 + 1 && c + 1 < cols; ++c) {
            grid.at(r, c) = 50.0;
        }
    }
    return grid;
}

double total_heat(const Grid& grid) {
    double sum = 0.0;
    for (std::size_t r = 0; r < grid.rows(); ++r) {
        for (std::size_t c = 0; c < grid.cols(); ++c) {
            sum += grid.at(r, c);
        }
    }
    return sum;
}

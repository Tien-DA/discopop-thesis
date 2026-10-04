#pragma once

#include <cstddef>
#include <vector>

// Row-major 2D grid of temperatures.
class Grid {
public:
    Grid(std::size_t rows, std::size_t cols, double value = 0.0);

    std::size_t rows() const;
    std::size_t cols() const;
    double& at(std::size_t row, std::size_t col);
    double at(std::size_t row, std::size_t col) const;

    bool operator==(const Grid& other) const;

private:
    std::size_t rows_;
    std::size_t cols_;
    std::vector<double> data_;
};

// Hot plate: the top edge is held at 100 degrees, a small hot square sits in
// the interior, everything else starts at 0.
Grid make_hot_plate(std::size_t rows, std::size_t cols);

// Sum of all cells.
double total_heat(const Grid& grid);

#pragma once

#include <cstddef>
#include <vector>

// Row-major grid holding the escape-iteration count of every pixel.
class IterationMap {
public:
    IterationMap(std::size_t rows, std::size_t cols, int value = 0);

    std::size_t rows() const;
    std::size_t cols() const;
    int& at(std::size_t row, std::size_t col);
    int at(std::size_t row, std::size_t col) const;

    // Sum of the iteration counts of one row (= the work spent on that row).
    long long row_work(std::size_t row) const;

    bool operator==(const IterationMap& other) const;

private:
    std::size_t rows_;
    std::size_t cols_;
    std::vector<int> data_;
};

#include "heat.h"

#include <algorithm>
#include <cmath>
#include <utility>

double solve_heat_serial(Grid& grid, int iterations) {
    const std::size_t rows = grid.rows();
    const std::size_t cols = grid.cols();
    Grid next = grid;
    double residual = 0.0;

    for (int it = 0; it < iterations; ++it) {
        residual = 0.0;
        for (std::size_t r = 1; r + 1 < rows; ++r) {
            for (std::size_t c = 1; c + 1 < cols; ++c) {
                double updated = 0.25 * (grid.at(r - 1, c) + grid.at(r + 1, c) +
                                         grid.at(r, c - 1) + grid.at(r, c + 1));
                residual = std::max(residual, std::fabs(updated - grid.at(r, c)));
                next.at(r, c) = updated;
            }
        }
        std::swap(grid, next);
    }
    return residual;
}

// BUG: the stencil reads and writes the same grid. Within one sweep a cell
// is updated from neighbours that may already hold *new* values (the row
// above / the cell to the left have been overwritten, while the row below
// and the cell to the right have not, and across thread boundaries which
// value is seen depends on timing). That is Gauss-Seidel, not Jacobi, and
// it is also a data race, so the result differs from solve_heat_serial().
double solve_heat_parallel(Grid& grid, int iterations) {
    const std::size_t rows = grid.rows();
    const std::size_t cols = grid.cols();
    double residual = 0.0;

    for (int it = 0; it < iterations; ++it) {
        residual = 0.0;
        #pragma omp parallel for reduction(max : residual)
        for (std::size_t r = 1; r < rows - 1; ++r) {
            for (std::size_t c = 1; c + 1 < cols; ++c) {
                double updated = 0.25 * (grid.at(r - 1, c) + grid.at(r + 1, c) +
                                         grid.at(r, c - 1) + grid.at(r, c + 1));
                residual = std::max(residual, std::fabs(updated - grid.at(r, c)));
                grid.at(r, c) = updated;
            }
        }
    }
    return residual;
}

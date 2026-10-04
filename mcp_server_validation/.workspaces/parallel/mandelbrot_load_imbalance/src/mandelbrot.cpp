#include "mandelbrot.h"

#include <omp.h>

int mandelbrot_point(double cr, double ci, int max_iterations) {
    double zr = 0.0;
    double zi = 0.0;
    int n = 0;
    while (n < max_iterations && zr * zr + zi * zi <= 4.0) {
        double next_zr = zr * zr - zi * zi + cr;
        zi = 2.0 * zr * zi + ci;
        zr = next_zr;
        ++n;
    }
    return n;
}

long long compute_mandelbrot_serial(const Viewport& view, IterationMap& map) {
    const std::size_t rows = map.rows();
    const std::size_t cols = map.cols();
    const double dx = (view.x_max - view.x_min) / static_cast<double>(cols);
    const double dy = (view.y_max - view.y_min) / static_cast<double>(rows);

    long long total = 0;
    for (std::size_t r = 0; r < rows; ++r) {
        for (std::size_t c = 0; c < cols; ++c) {
            int n = mandelbrot_point(view.x_min + dx * static_cast<double>(c),
                                     view.y_min + dy * static_cast<double>(r),
                                     view.max_iterations);
            map.at(r, c) = n;
            total += n;
        }
    }
    return total;
}

// BUG (two problems):
//  1. 'total' is updated by every thread without a reduction clause or an
//     atomic, so concurrent updates are lost and the returned total does not
//     match the serial version.
//  2. The rows are distributed with schedule(static). Rows crossing the
//     middle of the set cost far more iterations than rows near the top and
//     bottom edges, so the thread owning the central block of rows does most
//     of the work while the others finish early (severe load imbalance).
long long compute_mandelbrot_parallel(const Viewport& view, IterationMap& map,
                                      std::vector<int>* row_owner) {
    const std::size_t rows = map.rows();
    const std::size_t cols = map.cols();
    const double dx = (view.x_max - view.x_min) / static_cast<double>(cols);
    const double dy = (view.y_max - view.y_min) / static_cast<double>(rows);

    if (row_owner != nullptr) {
        row_owner->assign(rows, -1);
    }

    long long total = 0;
    #pragma omp parallel for schedule(static)
    for (std::size_t r = 0; r < rows; ++r) {
        if (row_owner != nullptr) {
            (*row_owner)[r] = omp_get_thread_num();
        }
        for (std::size_t c = 0; c < cols; ++c) {
            int n = mandelbrot_point(view.x_min + dx * static_cast<double>(c),
                                     view.y_min + dy * static_cast<double>(r),
                                     view.max_iterations);
            map.at(r, c) = n;
            total += n;
        }
    }
    return total;
}

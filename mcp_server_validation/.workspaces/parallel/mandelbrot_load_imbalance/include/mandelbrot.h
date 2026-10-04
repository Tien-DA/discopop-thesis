#pragma once

#include <vector>

#include "iteration_map.h"

struct Viewport {
    double x_min;
    double x_max;
    double y_min;
    double y_max;
    int max_iterations;
};

// Number of iterations z = z^2 + c needs to escape |z| > 2 (capped at
// max_iterations for points inside the set).
int mandelbrot_point(double cr, double ci, int max_iterations);

// Fills 'map' (already sized rows x cols) and returns the total number of
// iterations executed over all pixels.
long long compute_mandelbrot_serial(const Viewport& view, IterationMap& map);

// OpenMP version. Returns the same total as the serial version. If
// 'row_owner' is not null it is resized to map.rows() and row_owner[r]
// receives the id (omp_get_thread_num()) of the thread that computed row r.
long long compute_mandelbrot_parallel(const Viewport& view, IterationMap& map,
                                      std::vector<int>* row_owner = nullptr);

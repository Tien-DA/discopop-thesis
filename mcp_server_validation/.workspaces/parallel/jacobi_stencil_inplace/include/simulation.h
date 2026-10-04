#pragma once

#include "grid.h"

struct SimulationResult {
    Grid grid;
    double residual;
    double heat;
};

// Builds a hot plate, relaxes it with solve_heat_parallel() and reports the
// final grid, the last residual and the total heat.
SimulationResult run_simulation(std::size_t rows, std::size_t cols, int iterations);

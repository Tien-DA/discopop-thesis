#include "simulation.h"

#include "heat.h"

SimulationResult run_simulation(std::size_t rows, std::size_t cols, int iterations) {
    Grid grid = make_hot_plate(rows, cols);
    double residual = solve_heat_parallel(grid, iterations);
    double heat = total_heat(grid);
    return SimulationResult{grid, residual, heat};
}

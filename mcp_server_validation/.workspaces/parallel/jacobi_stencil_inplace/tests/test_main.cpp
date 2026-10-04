#include <iostream>

#include "grid.h"
#include "heat.h"
#include "simulation.h"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

bool test_serial_single_sweep_is_jacobi() {
    // 3x3 grid: only the centre cell is interior.
    Grid grid(3, 3, 0.0);
    grid.at(0, 1) = 8.0;
    grid.at(1, 0) = 4.0;
    grid.at(1, 2) = 12.0;
    grid.at(2, 1) = 16.0;
    double residual = solve_heat_serial(grid, 1);
    return grid.at(1, 1) == 10.0 && residual == 10.0;
}

bool test_parallel_matches_serial_for_various_iteration_counts() {
#ifdef _OPENMP
    omp_set_num_threads(8);
#endif
    const int iteration_counts[] = {1, 2, 10, 60};
    for (int iterations : iteration_counts) {
        Grid expected = make_hot_plate(96, 80);
        Grid actual = expected;
        double expected_residual = solve_heat_serial(expected, iterations);
        double actual_residual = solve_heat_parallel(actual, iterations);
        if (!(actual == expected)) return false;
        if (actual_residual != expected_residual) return false;
    }
    return true;
}

bool test_parallel_is_repeatable() {
#ifdef _OPENMP
    omp_set_num_threads(8);
#endif
    Grid expected = make_hot_plate(128, 128);
    solve_heat_serial(expected, 40);
    for (int trial = 0; trial < 10; ++trial) {
        Grid actual = make_hot_plate(128, 128);
        solve_heat_parallel(actual, 40);
        if (!(actual == expected)) return false;
    }
    return true;
}

bool test_boundary_cells_are_unchanged() {
#ifdef _OPENMP
    omp_set_num_threads(8);
#endif
    Grid initial = make_hot_plate(50, 70);
    Grid grid = initial;
    solve_heat_parallel(grid, 30);
    for (std::size_t c = 0; c < grid.cols(); ++c) {
        if (grid.at(0, c) != initial.at(0, c)) return false;
        if (grid.at(grid.rows() - 1, c) != initial.at(grid.rows() - 1, c)) return false;
    }
    for (std::size_t r = 0; r < grid.rows(); ++r) {
        if (grid.at(r, 0) != initial.at(r, 0)) return false;
        if (grid.at(r, grid.cols() - 1) != initial.at(r, grid.cols() - 1)) return false;
    }
    return true;
}

bool test_simulation_pipeline_matches_serial() {
#ifdef _OPENMP
    omp_set_num_threads(8);
#endif
    Grid expected = make_hot_plate(64, 64);
    double expected_residual = solve_heat_serial(expected, 25);
    SimulationResult result = run_simulation(64, 64, 25);
    return result.grid == expected && result.residual == expected_residual &&
           result.heat == total_heat(expected);
}

}  // namespace

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"serial_single_sweep_is_jacobi", test_serial_single_sweep_is_jacobi},
        {"parallel_matches_serial_for_various_iteration_counts", test_parallel_matches_serial_for_various_iteration_counts},
        {"parallel_is_repeatable", test_parallel_is_repeatable},
        {"boundary_cells_are_unchanged", test_boundary_cells_are_unchanged},
        {"simulation_pipeline_matches_serial", test_simulation_pipeline_matches_serial}
    };

    int failures = 0;
    for (const Test& test : tests) {
        bool passed = test.function();
        if (passed) {
            std::cout << "[PASS] " << test.name << std::endl;
        } else {
            std::cerr << "[FAIL] " << test.name << std::endl;
            ++failures;
        }
    }

    if (failures > 0) {
        std::cerr << failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}

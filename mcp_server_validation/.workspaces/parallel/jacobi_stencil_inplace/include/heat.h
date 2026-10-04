#pragma once

#include "grid.h"

// Jacobi relaxation of the heat equation. Every interior cell becomes the
// average of its four neighbours *from the previous iteration*; boundary
// cells (first/last row and column) stay fixed.
//
// Both functions run 'iterations' sweeps in place on 'grid' and return the
// largest absolute change of any cell in the final sweep.
double solve_heat_serial(Grid& grid, int iterations);
double solve_heat_parallel(Grid& grid, int iterations);

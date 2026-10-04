#pragma once

#include "matrix.h"

// Reference implementation: C = A * B (A is n x m, B is m x p).
Matrix multiply_serial(const Matrix& a, const Matrix& b);

// OpenMP implementation of the same product.
Matrix multiply_parallel(const Matrix& a, const Matrix& b);

// Parallel transpose.
Matrix transpose_parallel(const Matrix& a);

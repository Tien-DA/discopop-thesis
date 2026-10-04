#pragma once

#include "matrix.h"

// Gram matrix G = A * A^T, built from transpose_parallel() and
// multiply_parallel().
Matrix compute_gram_matrix(const Matrix& a);

// Sum of all diagonal entries of a square matrix.
long long trace(const Matrix& m);

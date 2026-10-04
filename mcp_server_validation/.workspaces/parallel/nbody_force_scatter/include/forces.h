#pragma once

#include <vector>

#include "body.h"

constexpr double kGravity = 1.0;
constexpr double kSoftening = 1e-3;

// Computes the gravitational force on every body ('forces' is resized and
// overwritten) and returns the total potential energy of the system.
// Each unordered pair of bodies contributes to both bodies (Newton's third
// law), so the forces always sum to (numerically) zero.
double compute_forces_serial(const std::vector<Body>& bodies, std::vector<Vec3>& forces);

// OpenMP version with identical results (up to floating point summation order).
double compute_forces_parallel(const std::vector<Body>& bodies, std::vector<Vec3>& forces);

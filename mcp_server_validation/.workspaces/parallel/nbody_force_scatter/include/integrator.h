#pragma once

#include <vector>

#include "body.h"

// Advances the system by 'steps' explicit Euler steps of size dt, using
// compute_forces_parallel() (parallel = true) or compute_forces_serial()
// (parallel = false). Returns the potential energy computed in the last step.
double simulate(std::vector<Body>& bodies, int steps, double dt, bool parallel);

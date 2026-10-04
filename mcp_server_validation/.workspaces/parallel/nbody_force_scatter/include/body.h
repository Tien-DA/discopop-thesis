#pragma once

#include <cstddef>
#include <vector>

#include "vec3.h"

struct Body {
    Vec3 position;
    Vec3 velocity;
    double mass = 1.0;
};

// Deterministic cloud of bodies with positions in [-10, 10]^3 and masses in [0.5, 2].
std::vector<Body> make_random_bodies(std::size_t count, unsigned seed);

#include "forces.h"

#include <cmath>

double compute_forces_serial(const std::vector<Body>& bodies, std::vector<Vec3>& forces) {
    const std::size_t n = bodies.size();
    forces.assign(n, Vec3{});
    double energy = 0.0;

    for (std::size_t i = 0; i < n; ++i) {
        for (std::size_t j = i + 1; j < n; ++j) {
            const Vec3 d = bodies[j].position - bodies[i].position;
            const double r2 = dot(d, d) + kSoftening;
            const double inv_r = 1.0 / std::sqrt(r2);
            const double inv_r3 = inv_r * inv_r * inv_r;
            const double strength = kGravity * bodies[i].mass * bodies[j].mass;

            const Vec3 f = d * (strength * inv_r3);
            forces[i] += f;
            forces[j] -= f;
            energy -= strength * inv_r;
        }
    }
    return energy;
}

// BUG: the parallel loop over i is not independent. Iteration i also writes
// forces[j] for every j > i, i.e. into entries that belong to other
// iterations (and other threads), and every iteration adds to the shared
// scalar 'energy'. Neither update is protected (no atomic, no per-thread
// buffers, no reduction clause), so concurrent read-modify-write cycles lose
// updates: forces no longer cancel out and the energy is wrong.
double compute_forces_parallel(const std::vector<Body>& bodies, std::vector<Vec3>& forces) {
    const std::size_t n = bodies.size();
    forces.assign(n, Vec3{});
    double energy = 0.0;

    #pragma omp parallel for schedule(dynamic, 4)
    for (std::size_t i = 0; i < n; ++i) {
        for (std::size_t j = i + 1; j < n; ++j) {
            const Vec3 d = bodies[j].position - bodies[i].position;
            const double r2 = dot(d, d) + kSoftening;
            const double inv_r = 1.0 / std::sqrt(r2);
            const double inv_r3 = inv_r * inv_r * inv_r;
            const double strength = kGravity * bodies[i].mass * bodies[j].mass;

            const Vec3 f = d * (strength * inv_r3);
            forces[i] += f;
            forces[j] -= f;
            energy -= strength * inv_r;
        }
    }
    return energy;
}

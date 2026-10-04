#include "integrator.h"

#include "forces.h"

double simulate(std::vector<Body>& bodies, int steps, double dt, bool parallel) {
    std::vector<Vec3> forces;
    double energy = 0.0;

    for (int step = 0; step < steps; ++step) {
        energy = parallel ? compute_forces_parallel(bodies, forces)
                          : compute_forces_serial(bodies, forces);

        #pragma omp parallel for
        for (std::size_t i = 0; i < bodies.size(); ++i) {
            const Vec3 acceleration = forces[i] * (1.0 / bodies[i].mass);
            bodies[i].velocity += acceleration * dt;
            bodies[i].position += bodies[i].velocity * dt;
        }
    }
    return energy;
}

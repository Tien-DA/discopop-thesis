#include <algorithm>
#include <cmath>
#include <iostream>
#include <vector>

#include "body.h"
#include "forces.h"
#include "integrator.h"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

double max_abs_component(const std::vector<Vec3>& forces) {
    double m = 0.0;
    for (const Vec3& f : forces) {
        m = std::max({m, std::fabs(f.x), std::fabs(f.y), std::fabs(f.z)});
    }
    return m;
}

bool forces_close(const std::vector<Vec3>& a, const std::vector<Vec3>& b, double relative_tolerance) {
    if (a.size() != b.size()) return false;
    const double scale = std::max(max_abs_component(a), 1e-12);
    for (std::size_t i = 0; i < a.size(); ++i) {
        if (std::fabs(a[i].x - b[i].x) > relative_tolerance * scale) return false;
        if (std::fabs(a[i].y - b[i].y) > relative_tolerance * scale) return false;
        if (std::fabs(a[i].z - b[i].z) > relative_tolerance * scale) return false;
    }
    return true;
}

bool close(double a, double b, double relative_tolerance) {
    return std::fabs(a - b) <= relative_tolerance * std::max(std::fabs(a), std::fabs(b));
}

bool test_serial_two_body_forces_are_opposite() {
    std::vector<Body> bodies(2);
    bodies[0].position = {0.0, 0.0, 0.0};
    bodies[1].position = {2.0, 0.0, 0.0};
    std::vector<Vec3> forces;
    double energy = compute_forces_serial(bodies, forces);
    return forces[0].x > 0.0 && std::fabs(forces[0].x + forces[1].x) < 1e-12 && energy < 0.0;
}

bool test_parallel_forces_match_serial_repeated() {
#ifdef _OPENMP
    omp_set_num_threads(32);
#endif
    std::vector<Body> bodies = make_random_bodies(1200, /*seed=*/5);
    std::vector<Vec3> expected;
    compute_forces_serial(bodies, expected);
    for (int trial = 0; trial < 10; ++trial) {
        std::vector<Vec3> actual;
        compute_forces_parallel(bodies, actual);
        if (!forces_close(actual, expected, 1e-9)) return false;
    }
    return true;
}

bool test_parallel_energy_matches_serial_repeated() {
#ifdef _OPENMP
    omp_set_num_threads(32);
#endif
    std::vector<Body> bodies = make_random_bodies(1200, /*seed=*/6);
    std::vector<Vec3> forces;
    const double expected = compute_forces_serial(bodies, forces);
    for (int trial = 0; trial < 10; ++trial) {
        std::vector<Vec3> actual_forces;
        if (!close(compute_forces_parallel(bodies, actual_forces), expected, 1e-9)) return false;
    }
    return true;
}

bool test_total_force_is_zero() {
#ifdef _OPENMP
    omp_set_num_threads(32);
#endif
    std::vector<Body> bodies = make_random_bodies(1200, /*seed=*/7);
    for (int trial = 0; trial < 5; ++trial) {
        std::vector<Vec3> forces;
        compute_forces_parallel(bodies, forces);
        Vec3 total;
        for (const Vec3& f : forces) total += f;
        const double scale = std::max(max_abs_component(forces), 1e-12);
        if (std::fabs(total.x) > 1e-9 * scale * bodies.size()) return false;
        if (std::fabs(total.y) > 1e-9 * scale * bodies.size()) return false;
        if (std::fabs(total.z) > 1e-9 * scale * bodies.size()) return false;
    }
    return true;
}

bool test_small_systems() {
#ifdef _OPENMP
    omp_set_num_threads(32);
#endif
    for (std::size_t n : {0u, 1u, 2u, 3u, 9u}) {
        std::vector<Body> bodies = make_random_bodies(n, /*seed=*/1);
        std::vector<Vec3> expected, actual;
        double e1 = compute_forces_serial(bodies, expected);
        double e2 = compute_forces_parallel(bodies, actual);
        if (actual.size() != n || !forces_close(actual, expected, 1e-9)) return false;
        if (n > 1 && !close(e1, e2, 1e-9)) return false;
    }
    return true;
}

bool test_simulation_matches_serial() {
#ifdef _OPENMP
    omp_set_num_threads(32);
#endif
    std::vector<Body> reference = make_random_bodies(200, /*seed=*/8);
    std::vector<Body> candidate = reference;
    double e_ref = simulate(reference, 5, 0.01, /*parallel=*/false);
    double e_par = simulate(candidate, 5, 0.01, /*parallel=*/true);
    if (!close(e_ref, e_par, 1e-8)) return false;
    for (std::size_t i = 0; i < reference.size(); ++i) {
        if (std::fabs(reference[i].position.x - candidate[i].position.x) > 1e-8) return false;
        if (std::fabs(reference[i].position.y - candidate[i].position.y) > 1e-8) return false;
        if (std::fabs(reference[i].position.z - candidate[i].position.z) > 1e-8) return false;
    }
    return true;
}

}  // namespace

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"serial_two_body_forces_are_opposite", test_serial_two_body_forces_are_opposite},
        {"parallel_forces_match_serial_repeated", test_parallel_forces_match_serial_repeated},
        {"parallel_energy_matches_serial_repeated", test_parallel_energy_matches_serial_repeated},
        {"total_force_is_zero", test_total_force_is_zero},
        {"small_systems", test_small_systems},
        {"simulation_matches_serial", test_simulation_matches_serial}
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

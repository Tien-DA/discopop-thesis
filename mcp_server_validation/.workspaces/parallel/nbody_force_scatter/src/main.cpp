#include <iostream>
#include <vector>

#include "body.h"
#include "integrator.h"

int main() {
    std::vector<Body> bodies = make_random_bodies(200, /*seed=*/4);
    double energy = simulate(bodies, /*steps=*/3, /*dt=*/0.01, /*parallel=*/true);

    std::cout << "potential energy: " << energy << std::endl;
    std::cout << "first body x: " << bodies.front().position.x << std::endl;
    return 0;
}

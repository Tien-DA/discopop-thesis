#include "body.h"

#include <random>

std::vector<Body> make_random_bodies(std::size_t count, unsigned seed) {
    std::mt19937 generator(seed);
    std::uniform_real_distribution<double> position(-10.0, 10.0);
    std::uniform_real_distribution<double> mass(0.5, 2.0);

    std::vector<Body> bodies(count);
    for (Body& body : bodies) {
        body.position = {position(generator), position(generator), position(generator)};
        body.mass = mass(generator);
    }
    return bodies;
}

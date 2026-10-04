#include "data_gen.h"

#include <random>

std::vector<long long> make_random_vector(std::size_t size, unsigned seed, int max_abs) {
    std::vector<long long> values(size);
    std::mt19937 generator(seed);
    std::uniform_int_distribution<int> distribution(-max_abs, max_abs);
    for (std::size_t i = 0; i < size; ++i) {
        values[i] = distribution(generator);
    }
    return values;
}

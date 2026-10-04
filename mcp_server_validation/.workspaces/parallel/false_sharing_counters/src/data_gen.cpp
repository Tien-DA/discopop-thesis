#include "data_gen.h"

#include <random>

std::vector<long long> make_random_values(std::size_t size, unsigned seed, long long max_value) {
    std::vector<long long> values(size);
    std::mt19937_64 generator(seed);
    std::uniform_int_distribution<long long> distribution(0, max_value);
    for (std::size_t i = 0; i < size; ++i) {
        values[i] = distribution(generator);
    }
    return values;
}

#include "data_gen.h"

#include <random>

std::vector<int> make_random_ints(std::size_t size, unsigned seed, int max_value) {
    std::vector<int> values(size);
    std::mt19937 generator(seed);
    std::uniform_int_distribution<int> distribution(0, max_value);
    for (std::size_t i = 0; i < size; ++i) {
        values[i] = distribution(generator);
    }
    return values;
}

bool is_sorted_ascending(const std::vector<int>& values) {
    for (std::size_t i = 1; i < values.size(); ++i) {
        if (values[i - 1] > values[i]) {
            return false;
        }
    }
    return true;
}

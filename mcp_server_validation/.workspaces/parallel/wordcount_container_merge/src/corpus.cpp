#include "corpus.h"

#include <cmath>
#include <random>

std::vector<std::string> make_corpus(std::size_t line_count, std::size_t words_per_line,
                                     std::size_t vocabulary_size, unsigned seed) {
    std::mt19937 generator(seed);
    std::uniform_real_distribution<double> uniform(0.0, 1.0);

    std::vector<std::string> lines;
    lines.reserve(line_count);
    for (std::size_t l = 0; l < line_count; ++l) {
        std::string line;
        for (std::size_t w = 0; w < words_per_line; ++w) {
            // Squaring the uniform sample skews the choice towards small ids.
            const double u = uniform(generator);
            const std::size_t id = static_cast<std::size_t>(u * u * static_cast<double>(vocabulary_size));
            if (w > 0) line.push_back(' ');
            line += "w" + std::to_string(id < vocabulary_size ? id : vocabulary_size - 1);
        }
        lines.push_back(line);
    }
    return lines;
}

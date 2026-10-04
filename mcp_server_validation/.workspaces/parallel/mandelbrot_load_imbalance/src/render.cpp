#include "render.h"

std::vector<std::string> render_ascii(const IterationMap& map, int max_iterations) {
    static const char kPalette[] = " .:-=+*#%@";
    const int levels = 9;
    std::vector<std::string> lines;
    for (std::size_t r = 0; r < map.rows(); ++r) {
        std::string line;
        for (std::size_t c = 0; c < map.cols(); ++c) {
            int n = map.at(r, c);
            int level = (n >= max_iterations) ? levels : (n * levels) / max_iterations;
            line.push_back(kPalette[level]);
        }
        lines.push_back(line);
    }
    return lines;
}

double inside_fraction(const IterationMap& map, int max_iterations) {
    std::size_t inside = 0;
    for (std::size_t r = 0; r < map.rows(); ++r) {
        for (std::size_t c = 0; c < map.cols(); ++c) {
            if (map.at(r, c) >= max_iterations) {
                ++inside;
            }
        }
    }
    return static_cast<double>(inside) / static_cast<double>(map.rows() * map.cols());
}

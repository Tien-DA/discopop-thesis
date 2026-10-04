#include <iostream>

#include "iteration_map.h"
#include "mandelbrot.h"
#include "render.h"

int main() {
    const Viewport view{-2.0, 0.8, -1.2, 1.2, 300};
    IterationMap map(48, 80);
    long long total = compute_mandelbrot_parallel(view, map);

    std::cout << "total iterations: " << total << std::endl;
    std::cout << "inside fraction: " << inside_fraction(map, view.max_iterations) << std::endl;
    return 0;
}

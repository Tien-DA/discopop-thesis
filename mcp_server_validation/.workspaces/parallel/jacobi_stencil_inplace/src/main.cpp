#include <iostream>

#include "simulation.h"

int main() {
    SimulationResult result = run_simulation(64, 64, 20);

    std::cout << "residual: " << result.residual << std::endl;
    std::cout << "total heat: " << result.heat << std::endl;
    return 0;
}

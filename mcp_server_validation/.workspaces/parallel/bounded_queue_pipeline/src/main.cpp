#include <iostream>
#include <vector>

#include "pipeline.h"

int main() {
    std::vector<int> input;
    for (int i = 1; i <= 200; ++i) {
        input.push_back(i);
    }

    long long result = run_pipeline(input, /*queue_capacity=*/8, /*workers=*/3);

    std::cout << "pipeline result: " << result << std::endl;
    std::cout << "reference result: " << pipeline_reference(input) << std::endl;
    return 0;
}

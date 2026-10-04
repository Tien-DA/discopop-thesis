#include <iostream>
#include <vector>

#include "data_gen.h"
#include "sort.h"

int main() {
    std::vector<int> values = make_random_ints(20000, /*seed=*/99, /*max_value=*/100000);
    merge_sort_parallel(values);

    std::cout << "sorted: " << (is_sorted_ascending(values) ? "yes" : "no") << std::endl;
    std::cout << "min: " << values.front() << ", max: " << values.back() << std::endl;
    return 0;
}

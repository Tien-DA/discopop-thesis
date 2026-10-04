#include <iostream>
#include <vector>

#include "data_gen.h"
#include "report.h"
#include "stats.h"

int main() {
    std::vector<long long> values = make_random_values(100000, /*seed=*/8, /*max_value=*/1000);
    Stats stats = compute_stats_parallel(values, /*threshold=*/500);

    std::cout << format_stats(stats, values.size()) << std::endl;
    return 0;
}

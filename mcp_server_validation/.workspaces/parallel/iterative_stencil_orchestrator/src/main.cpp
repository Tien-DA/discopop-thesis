#include <iostream>

#include "config.h"
#include "context.h"
#include "pipeline.h"

int main() {
    Context ctx(discopop_profiling_config(), /*seed=*/20261004ULL);
    run_all(ctx);

    std::cout << "pipeline checksum: " << checksum(ctx) << std::endl;
    std::cout << "hits: " << ctx.hits << ", peak: " << ctx.peak << std::endl;
    return 0;
}

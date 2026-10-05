#include "context.h"
#include "mix.h"
#include "util.h"
#include <vector>

void run_taskgraph(Context& ctx) {
    std::vector<uint64_t> frontier(ctx.cfg.blocks, 0);
    #pragma omp parallel for
    for (std::size_t task = 0; task < ctx.cfg.items; ++task) {
        const std::size_t parent = (ctx.perm[task] ^ ctx.table[task]) % ctx.cfg.blocks;
        frontier[parent] += mix64(ctx.buf[4][task] + task) & 0x3fULL;
    }
    #pragma omp parallel for
    for (std::size_t parent = 0; parent < ctx.cfg.blocks; ++parent) ctx.partial[parent] = combine(ctx.partial[parent], frontier[parent]);
    #pragma omp parallel for
    for (std::size_t task = 0; task < ctx.cfg.items; ++task) {
        ctx.buf[4][task] = combine(ctx.buf[4][task], frontier[ctx.perm[task] % ctx.cfg.blocks]);
    }
}

#include "context.h"
#include "mix.h"
#include "util.h"
#include <vector>

void run_histogram(Context& ctx) {
    const std::size_t bins_count = ctx.cfg.blocks;
    std::vector<uint64_t> bins(bins_count, 0);
    #pragma omp parallel for
    for (std::size_t i = 0; i < ctx.cfg.items; ++i) {
        const std::size_t bin = mix64(ctx.buf[0][i] ^ (i * 0x9e3779b9ULL)) % bins_count;
        ++bins[bin];
    }
    #pragma omp parallel for
    for (std::size_t b = 0; b < bins_count; ++b) ctx.partial[b] = combine(ctx.partial[b], bins[b]);
    #pragma omp parallel for
    for (std::size_t i = 0; i < ctx.cfg.items; ++i) {
        ctx.buf[0][i] = combine(ctx.buf[0][i], bins[i % bins_count]);
    }
}

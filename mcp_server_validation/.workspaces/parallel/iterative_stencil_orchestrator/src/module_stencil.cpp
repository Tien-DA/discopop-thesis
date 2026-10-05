#include "context.h"
#include "mix.h"
#include "util.h"

void run_stencil(Context& ctx) {
    static uint64_t halo[kMaxScratch];
    const std::size_t n = ctx.cfg.items;
    const std::size_t width = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        for (std::size_t d = 0; d < width; ++d) {
            halo[d] = mix64(ctx.buf[1][(i + d * 3) % n] + d);
        }
        uint64_t acc = 0x6a09e667f3bcc909ULL;
        for (std::size_t d = 0; d < width; ++d) acc = combine(acc, halo[d]);
        ctx.buf[1][i] = combine(ctx.buf[1][i], acc);
    }
}

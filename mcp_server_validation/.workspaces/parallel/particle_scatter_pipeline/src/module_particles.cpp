#include "context.h"
#include "mix.h"
#include "util.h"
#include <vector>

void run_particles(Context& ctx) {
    std::vector<uint64_t> mass(ctx.cfg.blocks, 0);
    #pragma omp parallel for
    for (std::size_t particle = 0; particle < ctx.cfg.items; ++particle) {
        const std::size_t cell = (ctx.table[particle] + particle * 5) % ctx.cfg.blocks;
        mass[cell] += (mix64(ctx.buf[3][particle]) & 0xffULL) + 1ULL;
    }
    #pragma omp parallel for
    for (std::size_t cell = 0; cell < ctx.cfg.blocks; ++cell) ctx.partial[cell] = combine(ctx.partial[cell], mass[cell]);
    #pragma omp parallel for
    for (std::size_t particle = 0; particle < ctx.cfg.items; ++particle) {
        ctx.buf[3][particle] = combine(ctx.buf[3][particle], mass[particle % ctx.cfg.blocks]);
    }
}

#include "context.h"

#include <algorithm>
#include <numeric>
#include <random>

#include "mix.h"
#include "util.h"

Context::Context(const Config& config, uint64_t seed)
    : cfg(config), partial(config.blocks, 0), work(kMaxScratch, 0) {
    for (int b = 0; b < kBuffers; ++b) {
        buf[b].resize(cfg.items);
        for (std::size_t i = 0; i < cfg.items; ++i) {
            buf[b][i] = mix64(seed + static_cast<uint64_t>(b) * 1000003ULL + i);
        }
    }
    perm.resize(cfg.items);
    std::iota(perm.begin(), perm.end(), 0u);
    std::mt19937 generator(static_cast<unsigned>(seed));
    std::shuffle(perm.begin(), perm.end(), generator);

    table.resize(cfg.items);
    for (std::size_t i = 0; i < cfg.items; ++i) {
        table[i] = static_cast<uint32_t>(mix64(seed ^ (i * 77ULL)) % cfg.items);
    }
}

uint64_t checksum(const Context& ctx) {
    uint64_t acc = 0x517cc1b727220a95ULL;
    for (int b = 0; b < Context::kBuffers; ++b) {
        acc = combine(acc, digest_span(ctx.buf[b].data(), ctx.buf[b].size()));
    }
    acc = combine(acc, digest_span(ctx.partial.data(), ctx.partial.size()));
    acc = combine(acc, ctx.hits);
    acc = combine(acc, ctx.peak);
    return acc;
}

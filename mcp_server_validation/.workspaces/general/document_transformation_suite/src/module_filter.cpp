// Smoothing filters stages.
#include <cstddef>
#include <cstdint>
#include <vector>

#include "context.h"
#include "kernels.h"
#include "lookup.h"
#include "mix.h"
#include "smoother.h"
#include "util.h"

namespace {

// Stage 00
void stage_filter_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 889083553903848227ULL;
        for (int d = -4; d <= 4; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 4));
        }
        out[i] = acc;
    }
}

// Stage 01
void stage_filter_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 33) % n]) ^ 273149904025753ULL;
        out[i] = v;
        if ((v & 15) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 02
void stage_filter_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 114269774309411ULL;
        const uint64_t u = spread(in[i] ^ 264775916755141ULL, 3);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 03
void stage_filter_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 1813298319865979ULL);
    }
}

// Stage 04
void stage_filter_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 657694572085671719ULL);
    }
}

// Stage 05
void stage_filter_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 934353130037308563ULL);
    }
}

// Stage 06
void stage_filter_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = in[i] * 51890422753829ULL + rotl64(in[(i + 2) % n], 54);
        out[i] = v;
        if ((v & 15) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 07
void stage_filter_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 728545440626334409ULL;
        for (int d = -1; d <= 1; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 1));
        }
        out[i] = acc;
    }
}

// Stage 08
void stage_filter_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 29) % n]) ^ 59274390028197ULL;
        out[i] = v;
        if ((v & 15) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 09
void stage_filter_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const Smoother smoother(ctx.cfg.scratch_len, 551608407990636103ULL);
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = smoother.apply(in.data(), n, i);
    }
}

// Stage 10
void stage_filter_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 830121800156895383ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 11
void stage_filter_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 601269074501155393ULL;
        for (int d = -1; d <= 1; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 1));
        }
        out[i] = acc;
    }
}

// Stage 12
void stage_filter_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 1012103192973834619ULL;
        for (std::size_t i = lo; i < hi; ++i) {
            acc += mix64(in[i] + i);
        }
        ctx.partial[blk] = acc;
    }
    uint64_t total = 0;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        total = combine(total, ctx.partial[blk]);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], total);
    }
}

// Stage 13
void stage_filter_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 960754058156475043ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 14
void stage_filter_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 3);
        const uint64_t u = spread(in[i] ^ 208038255049105ULL, 5);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 15
void stage_filter_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 3);
        const uint64_t u = rotl64(in[i] ^ 163617484145883ULL, 21) - mix64(in[i]);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 16
void stage_filter_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 1110919984528832035ULL;
        for (int d = -1; d <= 1; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 1));
        }
        out[i] = acc;
    }
}

// Stage 17
void stage_filter_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 3);
        const uint64_t u = rotl64(in[i] ^ 5582848608677ULL, 49) - mix64(in[i]);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 18
void stage_filter_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 660530413989695885ULL);
    }
}

// Stage 19
void stage_filter_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 135335743810253ULL;
        const uint64_t u = spread(in[i] ^ 262791943540001ULL, 2);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 20
void stage_filter_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 1);
        const uint64_t u = spread(in[i] ^ 187053535937825ULL, 5);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 21
void stage_filter_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = tapered_span_digest(in.data(), n, i, len, 772253180419858543ULL);
    }
}

// Stage 22
void stage_filter_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 266534537468247095ULL;
        for (std::size_t i = lo; i < hi; ++i) {
            acc += mix64(in[i] + i);
        }
        ctx.partial[blk] = acc;
    }
    uint64_t total = 0;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        total = combine(total, ctx.partial[blk]);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], total);
    }
}

// Stage 23
void stage_filter_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 262968266042391ULL + rotl64(in[(i + 30) % n], 19);
        const uint64_t u = combine(in[i], 227078350071127ULL);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

}  // namespace

void run_filter(Context& ctx) {
    stage_filter_00(ctx);
    stage_filter_01(ctx);
    stage_filter_02(ctx);
    stage_filter_03(ctx);
    stage_filter_04(ctx);
    stage_filter_05(ctx);
    stage_filter_06(ctx);
    stage_filter_07(ctx);
    stage_filter_08(ctx);
    stage_filter_09(ctx);
    stage_filter_10(ctx);
    stage_filter_11(ctx);
    stage_filter_12(ctx);
    stage_filter_13(ctx);
    stage_filter_14(ctx);
    stage_filter_15(ctx);
    stage_filter_16(ctx);
    stage_filter_17(ctx);
    stage_filter_18(ctx);
    stage_filter_19(ctx);
    stage_filter_20(ctx);
    stage_filter_21(ctx);
    stage_filter_22(ctx);
    stage_filter_23(ctx);
}

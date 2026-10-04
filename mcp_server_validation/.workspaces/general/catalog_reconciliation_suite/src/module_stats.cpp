// Statistics collection stages.
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

uint64_t g_tmp[kMaxScratch];

// Stage 00
void stage_stats_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 612382379868215755ULL;
        for (int d = -2; d <= 2; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 2));
        }
        out[i] = acc;
    }
}

// Stage 01
void stage_stats_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 1077379920687889459ULL);
    }
}

// Stage 02
void stage_stats_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    #pragma omp parallel for reduction(max : peak)
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 15) % n]) ^ 10376595675285ULL;
        out[i] = v;
        if (v > peak) {
            peak = v;
        }
    }
    if (peak > ctx.peak) {
        ctx.peak = peak;
    }
}

// Stage 03
void stage_stats_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t* tmp = g_tmp;
        for (std::size_t k = 0; k < len; ++k) {
            tmp[k] = mix64(in[(i * 7 + k * 3) % n] ^ (800007067912075061ULL + k));
        }
        uint64_t acc = 0xa4093822299f31d0ULL;
        for (std::size_t k = 0; k < len; ++k) {
            acc = acc * 33 + (tmp[k] ^ (tmp[(k + 1) % len] >> 8));
        }
        out[i] = acc;
    }
}

// Stage 04
void stage_stats_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = mix64(in[i] + 139034605437451ULL) ^ rotl64(in[i], 61);
    }
}

// Stage 05
void stage_stats_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = coarse_slice_digest(in.data(), n, i, len, 1089306846113282847ULL);
    }
}

// Stage 06
void stage_stats_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 610309049660922381ULL;
        for (int d = -2; d <= 2; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 2));
        }
        out[i] = acc;
    }
}

// Stage 07
void stage_stats_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 3);
        const uint64_t u = combine(in[i], 226556281112795ULL);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 08
void stage_stats_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t* tmp = g_tmp;
        for (std::size_t k = 0; k < len; ++k) {
            tmp[k] = mix64(in[(i * 7 + k * 3) % n] ^ (724464675131806513ULL + k));
        }
        uint64_t acc = 0xa4093822299f31d0ULL;
        for (std::size_t k = 0; k < len; ++k) {
            acc = acc * 33 + (tmp[k] ^ (tmp[(k + 1) % len] >> 8));
        }
        out[i] = acc;
    }
}

// Stage 09
void stage_stats_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 549541359161718363ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 10
void stage_stats_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 3);
        const uint64_t u = combine(in[i], 222909172506675ULL);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 11
void stage_stats_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 160274146092065023ULL);
    }
}

// Stage 12
void stage_stats_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 102531910033654169ULL;
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
void stage_stats_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 4) % n]) ^ 209229997988815ULL;
        const uint64_t u = spread(in[i] ^ 187866650781331ULL, 5);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 14
void stage_stats_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 1133531198012912025ULL;
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

// Stage 15
void stage_stats_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 411067308428752953ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 16
void stage_stats_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 725333872219448973ULL;
        for (int d = -2; d <= 2; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 2));
        }
        out[i] = acc;
    }
}

// Stage 17
void stage_stats_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = fold_range(in.data(), n, i, 3);
        out[i] = v;
        if ((v & 31) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 18
void stage_stats_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 256171635225264975ULL;
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

// Stage 19
void stage_stats_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 876286201621229887ULL);
    }
}

// Stage 20
void stage_stats_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 1133415387045238319ULL);
    }
}

// Stage 21
void stage_stats_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 140499458356436601ULL);
    }
}

// Stage 22
void stage_stats_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        uint64_t* slot = ctx.pool.acquire(blk);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(blk * 7 + k * 7) % n] ^ (331189600063867575ULL + k));
        }
        uint64_t acc = 0x9ddfea08eb382d69ULL;
        for (std::size_t k = 0; k < len; ++k) {
            acc = acc * 31 + (slot[k] ^ (slot[(k + 1) % len] >> 12));
        }
        ctx.partial[blk] = acc;
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], ctx.partial[i % blocks]);
    }
}

// Stage 23
void stage_stats_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 692112377624578395ULL);
    }
}

}  // namespace

void run_stats(Context& ctx) {
    stage_stats_00(ctx);
    stage_stats_01(ctx);
    stage_stats_02(ctx);
    stage_stats_03(ctx);
    stage_stats_04(ctx);
    stage_stats_05(ctx);
    stage_stats_06(ctx);
    stage_stats_07(ctx);
    stage_stats_08(ctx);
    stage_stats_09(ctx);
    stage_stats_10(ctx);
    stage_stats_11(ctx);
    stage_stats_12(ctx);
    stage_stats_13(ctx);
    stage_stats_14(ctx);
    stage_stats_15(ctx);
    stage_stats_16(ctx);
    stage_stats_17(ctx);
    stage_stats_18(ctx);
    stage_stats_19(ctx);
    stage_stats_20(ctx);
    stage_stats_21(ctx);
    stage_stats_22(ctx);
    stage_stats_23(ctx);
}

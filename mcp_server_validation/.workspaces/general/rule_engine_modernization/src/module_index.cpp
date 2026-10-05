// Index maintenance stages.
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
void stage_index_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 2) % n]) ^ 110509015896029ULL;
        out[i] = v;
        if (v > peak) {
            peak = v;
        }
    }
    if (peak > ctx.peak) {
        ctx.peak = peak;
    }
}

// Stage 01
void stage_index_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        uint64_t* slot = ctx.pool.acquire(blk);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(blk * 7 + k * 5) % n] ^ (142193689721779927ULL + k));
        }
        uint64_t acc = 0x9ddfea08eb382d69ULL;
        for (std::size_t k = 0; k < len; ++k) {
            acc = acc * 31 + (slot[k] ^ (slot[(k + 1) % len] >> 7));
        }
        ctx.partial[blk] = acc;
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], ctx.partial[i % blocks]);
    }
}

// Stage 02
void stage_index_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = blended_shard_digest(in.data(), n, i, len, 831493114033032263ULL);
    }
}

// Stage 03
void stage_index_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 341060370114945595ULL);
    }
}

// Stage 04
void stage_index_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = fold_range(in.data(), n, i, 1);
        out[i] = v;
        if (v > peak) {
            peak = v;
        }
    }
    if (peak > ctx.peak) {
        ctx.peak = peak;
    }
}

// Stage 05
void stage_index_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 138465868834134703ULL);
    }
}

// Stage 06
void stage_index_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 269359918064277ULL;
        const uint64_t u = spread(in[i] ^ 33001898748907ULL, 4);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 07
void stage_index_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 101867045894091ULL + rotl64(in[(i + 40) % n], 15);
        const uint64_t u = rotl64(in[i] ^ 200866898041271ULL, 50) - mix64(in[i]);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 08
void stage_index_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 22993137982695493ULL;
        for (int d = -2; d <= 2; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 2));
        }
        out[i] = acc;
    }
}

// Stage 09
void stage_index_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 200398272394651ULL;
        const uint64_t u = in[i] * 27803869257075ULL + 3475483657134ULL;
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 10
void stage_index_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 1028772557992349483ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 11
void stage_index_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 517519076677164059ULL;
        for (int d = -4; d <= 4; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 4));
        }
        out[i] = acc;
    }
}

// Stage 12
void stage_index_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 1);
        const uint64_t u = rotl64(in[i] ^ 268412352959223ULL, 44) - mix64(in[i]);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 13
void stage_index_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 880256818119284451ULL);
    }
}

// Stage 14
void stage_index_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = in[i] * 274041860050123ULL + rotl64(in[(i + 15) % n], 24);
        out[i] = v;
        if (v > peak) {
            peak = v;
        }
    }
    if (peak > ctx.peak) {
        ctx.peak = peak;
    }
}

// Stage 15
void stage_index_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], 133858223036397ULL);
    }
}

// Stage 16
void stage_index_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 554035854494156889ULL);
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 17
void stage_index_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 286374252008337443ULL;
        for (std::size_t i = lo; i < hi; ++i) {
            acc += mix64(in[i] + i);
        }
        ctx.partial[blk] = acc;
    }
    uint64_t total = 0;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        total = combine(total, ctx.partial[blk]);
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], total);
    }
}

// Stage 18
void stage_index_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 34783314532820093ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 19
void stage_index_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = mix64(in[i]) - mix64(in[n - 1 - i]) + 121133555221447ULL;
        out[i] = v;
        if ((v & 15) == 0) {
            ctx.hits += 1;
        }
    }
}

// Stage 20
void stage_index_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = in[i] * 128172650460481ULL + rotl64(in[(i + 15) % n], 45);
        out[i] = v;
        {
            if (v > ctx.peak) {
                ctx.peak = v;
            }
        }
    }
}

// Stage 21
void stage_index_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        uint64_t* slot = ctx.pool.acquire(blk);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(blk * 7 + k * 5) % n] ^ (546735090563443867ULL + k));
        }
        uint64_t acc = 0x9ddfea08eb382d69ULL;
        for (std::size_t k = 0; k < len; ++k) {
            acc = acc * 31 + (slot[k] ^ (slot[(k + 1) % len] >> 4));
        }
        ctx.partial[blk] = acc;
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], ctx.partial[i % blocks]);
    }
}

// Stage 22
void stage_index_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 30) % n]) ^ 133172906704299ULL;
        out[i] = v;
        if (v > peak) {
            peak = v;
        }
    }
    if (peak > ctx.peak) {
        ctx.peak = peak;
    }
}

// Stage 23
void stage_index_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 702285161511285515ULL;
        for (int d = -1; d <= 1; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 1));
        }
        out[i] = acc;
    }
}

}  // namespace

void run_index(Context& ctx) {
    stage_index_00(ctx);
    stage_index_01(ctx);
    stage_index_02(ctx);
    stage_index_03(ctx);
    stage_index_04(ctx);
    stage_index_05(ctx);
    stage_index_06(ctx);
    stage_index_07(ctx);
    stage_index_08(ctx);
    stage_index_09(ctx);
    stage_index_10(ctx);
    stage_index_11(ctx);
    stage_index_12(ctx);
    stage_index_13(ctx);
    stage_index_14(ctx);
    stage_index_15(ctx);
    stage_index_16(ctx);
    stage_index_17(ctx);
    stage_index_18(ctx);
    stage_index_19(ctx);
    stage_index_20(ctx);
    stage_index_21(ctx);
    stage_index_22(ctx);
    stage_index_23(ctx);
}

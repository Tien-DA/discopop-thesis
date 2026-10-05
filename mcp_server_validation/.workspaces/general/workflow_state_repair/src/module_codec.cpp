// Block encoding stages.
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

uint64_t encode_item(Context& ctx, const std::vector<uint64_t>& in, std::size_t i, uint64_t salt) {
    const std::size_t len = ctx.cfg.scratch_len;
    std::vector<uint64_t>& tmp = ctx.work;
    for (std::size_t k = 0; k < len; ++k) {
        tmp[k] = mix64(in[(i * 3 + k) % in.size()] ^ (salt + k));
    }
    uint64_t acc = 0x13198a2e03707344ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 35 + (tmp[k] ^ (tmp[(k + 1) % len] >> 4));
    }
    return acc;
}

// Stage 00
void stage_codec_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 1071132059540969499ULL;
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

// Stage 01
void stage_codec_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        uint64_t* slot = ctx.pool.acquire(blk);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(blk * 7 + k * 5) % n] ^ (1121932593252756539ULL + k));
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
void stage_codec_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 438132340242651567ULL;
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

// Stage 03
void stage_codec_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 52070896708609ULL;
        const uint64_t u = rotl64(in[i] ^ 156804865730677ULL, 14) - mix64(in[i]);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 04
void stage_codec_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = encode_item(ctx, in, i, 1056457945209165317ULL);
    }
}

// Stage 05
void stage_codec_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 10989342135377383ULL);
    }
}

// Stage 06
void stage_codec_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = masked_patch_digest(in.data(), n, i, len, 977674908866701949ULL);
    }
}

// Stage 07
void stage_codec_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 110231489364845491ULL);
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 08
void stage_codec_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = blended_shard_digest(in.data(), n, i, len, 455646177245858329ULL);
    }
}

// Stage 09
void stage_codec_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 134409639329607ULL;
        const uint64_t u = mix64(in[i] + 189927286613569ULL) ^ rotl64(in[i], 56);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 10
void stage_codec_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
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

// Stage 11
void stage_codec_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 265740831030221155ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 12
void stage_codec_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 108225678857661ULL + rotl64(in[(i + 31) % n], 30);
        const uint64_t u = in[i] * 139058189137297ULL + 17382273642162ULL;
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 13
void stage_codec_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 535154225175175529ULL);
    }
}

// Stage 14
void stage_codec_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 1024639947589826435ULL);
    }
}

// Stage 15
void stage_codec_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = in[i] * 277230030600763ULL + rotl64(in[(i + 10) % n], 24);
        out[i] = v;
        if (v > peak) {
            peak = v;
        }
    }
    if (peak > ctx.peak) {
        ctx.peak = peak;
    }
}

// Stage 16
void stage_codec_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 713593593469022671ULL);
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 17
void stage_codec_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 25) % n]) ^ 43135828024619ULL;
        const uint64_t u = combine(in[i], 30102675919441ULL);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 18
void stage_codec_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 139550531422349ULL + rotl64(in[(i + 4) % n], 5);
        const uint64_t u = combine(in[i], 162807212626703ULL);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 19
void stage_codec_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 582352985545020635ULL);
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 20
void stage_codec_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 492827265879057087ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 21
void stage_codec_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 35) % n]) ^ 118056837514691ULL;
        const uint64_t u = combine(in[i], 248509972727195ULL);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 22
void stage_codec_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = folded_strip_digest(in.data(), n, i, len, 216820777367946183ULL);
    }
}

// Stage 23
void stage_codec_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 555327596698415613ULL);
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

}  // namespace

void run_codec(Context& ctx) {
    stage_codec_00(ctx);
    stage_codec_01(ctx);
    stage_codec_02(ctx);
    stage_codec_03(ctx);
    stage_codec_04(ctx);
    stage_codec_05(ctx);
    stage_codec_06(ctx);
    stage_codec_07(ctx);
    stage_codec_08(ctx);
    stage_codec_09(ctx);
    stage_codec_10(ctx);
    stage_codec_11(ctx);
    stage_codec_12(ctx);
    stage_codec_13(ctx);
    stage_codec_14(ctx);
    stage_codec_15(ctx);
    stage_codec_16(ctx);
    stage_codec_17(ctx);
    stage_codec_18(ctx);
    stage_codec_19(ctx);
    stage_codec_20(ctx);
    stage_codec_21(ctx);
    stage_codec_22(ctx);
    stage_codec_23(ctx);
}

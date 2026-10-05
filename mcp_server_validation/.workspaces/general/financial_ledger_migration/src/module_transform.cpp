// Domain transforms stages.
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
void stage_transform_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 151576136156604679ULL;
        for (int d = -2; d <= 2; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 2));
        }
        out[i] = acc;
    }
}

// Stage 01
void stage_transform_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 470547326206050233ULL);
    }
}

// Stage 02
void stage_transform_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 5) % n]) ^ 212371227408493ULL;
        const uint64_t u = mix64(in[i] + 242444702523013ULL) ^ rotl64(in[i], 23);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 03
void stage_transform_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = masked_patch_digest(in.data(), n, i, len, 974296752359912273ULL);
    }
}

// Stage 04
void stage_transform_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 358717161304250131ULL);
    }
}

// Stage 05
void stage_transform_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 345744949069637229ULL;
        for (int d = -1; d <= 1; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 1));
        }
        out[i] = acc;
    }
}

// Stage 06
void stage_transform_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 4);
        const uint64_t u = rotl64(in[i] ^ 147889248838173ULL, 25) - mix64(in[i]);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 07
void stage_transform_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = in[i] * 159190945095947ULL + rotl64(in[(i + 9) % n], 4);
        out[i] = v;
        if (v > peak) {
            peak = v;
        }
    }
    if (peak > ctx.peak) {
        ctx.peak = peak;
    }
}

// Stage 08
void stage_transform_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 149049513613575ULL;
        const uint64_t u = in[i] * 85633329031109ULL + 10704166128888ULL;
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 09
void stage_transform_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 2);
        const uint64_t u = mix64(in[i] + 214154361257075ULL) ^ rotl64(in[i], 30);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 10
void stage_transform_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 3);
        const uint64_t u = in[i] * 128564080215285ULL + 16070510026910ULL;
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 11
void stage_transform_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 373696300261102183ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 12
void stage_transform_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 287958816899635235ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 13
void stage_transform_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], 231717938314731ULL);
    }
}

// Stage 14
void stage_transform_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 205497172331920953ULL);
    }
}

// Stage 15
void stage_transform_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 293408124352394065ULL);
    }
}

// Stage 16
void stage_transform_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = in[i] * 84048602688237ULL + rotl64(in[(i + 22) % n], 23);
        out[i] = v;
        if ((v & 31) == 0) {
            ctx.hits += 1;
        }
    }
}

// Stage 17
void stage_transform_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = coarse_slice_digest(in.data(), n, i, len, 1063071713464083267ULL);
    }
}

// Stage 18
void stage_transform_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 10424871652481923ULL;
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

// Stage 19
void stage_transform_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 63271575458934999ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 20
void stage_transform_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 579342300068655309ULL);
    }
}

// Stage 21
void stage_transform_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], 6439806037561ULL);
    }
}

// Stage 22
void stage_transform_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 395669957669113319ULL);
    }
}

// Stage 23
void stage_transform_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = mix64(in[i] + 235886099802555ULL) ^ rotl64(in[i], 7);
    }
}

}  // namespace

void run_transform(Context& ctx) {
    stage_transform_00(ctx);
    stage_transform_01(ctx);
    stage_transform_02(ctx);
    stage_transform_03(ctx);
    stage_transform_04(ctx);
    stage_transform_05(ctx);
    stage_transform_06(ctx);
    stage_transform_07(ctx);
    stage_transform_08(ctx);
    stage_transform_09(ctx);
    stage_transform_10(ctx);
    stage_transform_11(ctx);
    stage_transform_12(ctx);
    stage_transform_13(ctx);
    stage_transform_14(ctx);
    stage_transform_15(ctx);
    stage_transform_16(ctx);
    stage_transform_17(ctx);
    stage_transform_18(ctx);
    stage_transform_19(ctx);
    stage_transform_20(ctx);
    stage_transform_21(ctx);
    stage_transform_22(ctx);
    stage_transform_23(ctx);
}

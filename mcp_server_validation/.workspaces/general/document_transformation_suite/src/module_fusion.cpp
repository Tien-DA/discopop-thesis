// Sensor fusion stages.
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
void stage_fusion_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 601780913578933989ULL;
        for (int d = -4; d <= 4; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 4));
        }
        out[i] = acc;
    }
}

// Stage 01
void stage_fusion_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = masked_patch_digest(in.data(), n, i, len, 838757131205985971ULL);
    }
}

// Stage 02
void stage_fusion_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = blended_shard_digest(in.data(), n, i, len, 251237914196670959ULL);
    }
}

// Stage 03
void stage_fusion_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 576259059587243787ULL);
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 04
void stage_fusion_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 772775693489011343ULL;
        for (int d = -4; d <= 4; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 4));
        }
        out[i] = acc;
    }
}

// Stage 05
void stage_fusion_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 39614347949362571ULL;
        for (int d = -4; d <= 4; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 4));
        }
        out[i] = acc;
    }
}

// Stage 06
void stage_fusion_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 692969591938273115ULL;
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

// Stage 07
void stage_fusion_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t* slot = ctx.pool.acquire(i);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(i + k * 5) % n] ^ (1085493217093052759ULL + k));
        }
        uint64_t acc = 0x243f6a8885a308d3ULL;
        for (std::size_t k = 0; k < len; ++k) {
            acc = acc * 29 + (slot[k] ^ (slot[(k + 1) % len] >> 6));
        }
        out[i] = acc;
    }
}

// Stage 08
void stage_fusion_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = banded_lane_digest(in.data(), n, i, len, 879974213503352041ULL);
    }
}

// Stage 09
void stage_fusion_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = tapered_span_digest(in.data(), n, i, len, 181587474913051855ULL);
    }
}

// Stage 10
void stage_fusion_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 526946157693811533ULL;
        for (int d = -2; d <= 2; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 2));
        }
        out[i] = acc;
    }
}

// Stage 11
void stage_fusion_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 17645673977421ULL + rotl64(in[(i + 38) % n], 51);
        const uint64_t u = in[i] * 190869942826733ULL + 23858742853341ULL;
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 12
void stage_fusion_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 2);
        const uint64_t u = mix64(in[i] + 143841946585959ULL) ^ rotl64(in[i], 44);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 13
void stage_fusion_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 21) % n]) ^ 130063356498667ULL;
        const uint64_t u = spread(in[i] ^ 73041428591223ULL, 5);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 14
void stage_fusion_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 591118026811398971ULL);
    }
}

// Stage 15
void stage_fusion_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 920167196204398507ULL;
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

// Stage 16
void stage_fusion_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 709992014184365935ULL;
        for (int d = -1; d <= 1; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 1));
        }
        out[i] = acc;
    }
}

// Stage 17
void stage_fusion_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = fold_range(in.data(), n, i, 4);
        out[i] = v;
        if ((v & 31) == 0) {
            ctx.hits += 1;
        }
    }
}

// Stage 18
void stage_fusion_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 36) % n]) ^ 146197873013401ULL;
        out[i] = v;
        if (v > peak) {
            peak = v;
        }
    }
    if (peak > ctx.peak) {
        ctx.peak = peak;
    }
}

// Stage 19
void stage_fusion_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = strided_panel_digest(in.data(), n, i, len, 480498892841602649ULL);
    }
}

// Stage 20
void stage_fusion_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 805373621066632507ULL);
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 21
void stage_fusion_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 1);
        const uint64_t u = combine(in[i], 87257779224239ULL);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 22
void stage_fusion_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = in[i] * 210528895050041ULL + rotl64(in[(i + 20) % n], 32);
        out[i] = v;
        if ((v & 31) == 0) {
            ctx.hits += 1;
        }
    }
}

// Stage 23
void stage_fusion_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 56609492012192251ULL;
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

}  // namespace

void run_fusion(Context& ctx) {
    stage_fusion_00(ctx);
    stage_fusion_01(ctx);
    stage_fusion_02(ctx);
    stage_fusion_03(ctx);
    stage_fusion_04(ctx);
    stage_fusion_05(ctx);
    stage_fusion_06(ctx);
    stage_fusion_07(ctx);
    stage_fusion_08(ctx);
    stage_fusion_09(ctx);
    stage_fusion_10(ctx);
    stage_fusion_11(ctx);
    stage_fusion_12(ctx);
    stage_fusion_13(ctx);
    stage_fusion_14(ctx);
    stage_fusion_15(ctx);
    stage_fusion_16(ctx);
    stage_fusion_17(ctx);
    stage_fusion_18(ctx);
    stage_fusion_19(ctx);
    stage_fusion_20(ctx);
    stage_fusion_21(ctx);
    stage_fusion_22(ctx);
    stage_fusion_23(ctx);
}

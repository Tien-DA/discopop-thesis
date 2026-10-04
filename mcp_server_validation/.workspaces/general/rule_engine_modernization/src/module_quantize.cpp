// Quantization stages.
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
void stage_quantize_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 14) % n]) ^ 94718310068117ULL;
        out[i] = v;
        if ((v & 15) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 01
void stage_quantize_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 875628628015545307ULL);
    }
}

// Stage 02
void stage_quantize_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 125470269868185ULL;
        const uint64_t u = in[i] * 253062713816467ULL + 31632839227058ULL;
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 03
void stage_quantize_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 223426146524113ULL;
        const uint64_t u = rotl64(in[i] ^ 120071963146665ULL, 6) - mix64(in[i]);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 04
void stage_quantize_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        uint64_t* slot = ctx.pool.acquire(blk);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(blk * 7 + k * 5) % n] ^ (315190271586620089ULL + k));
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

// Stage 05
void stage_quantize_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 913779224609972069ULL);
    }
}

// Stage 06
void stage_quantize_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 144250904420483ULL;
        const uint64_t u = rotl64(in[i] ^ 136620812063873ULL, 20) - mix64(in[i]);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 07
void stage_quantize_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 907734864605409193ULL;
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

// Stage 08
void stage_quantize_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 6) % n]) ^ 109620816663641ULL;
        const uint64_t u = in[i] * 56546601234087ULL + 7068325154260ULL;
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 09
void stage_quantize_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 2);
        const uint64_t u = combine(in[i], 152356290792197ULL);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 10
void stage_quantize_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 711407948838633437ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 11
void stage_quantize_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 718574307626247529ULL;
        for (int d = -2; d <= 2; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 2));
        }
        out[i] = acc;
    }
}

// Stage 12
void stage_quantize_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 896759731197184547ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 13
void stage_quantize_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 12706491611937ULL;
        const uint64_t u = mix64(in[i] + 23112254845291ULL) ^ rotl64(in[i], 1);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 14
void stage_quantize_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    #pragma omp parallel for reduction(max : peak)
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = fold_range(in.data(), n, i, 3);
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
void stage_quantize_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = blended_shard_digest(in.data(), n, i, len, 99312112588693673ULL);
    }
}

// Stage 16
void stage_quantize_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 49809442976823ULL + rotl64(in[(i + 31) % n], 19);
        const uint64_t u = combine(in[i], 56166760627653ULL);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 17
void stage_quantize_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 224143507787815ULL + rotl64(in[(i + 2) % n], 38);
        const uint64_t u = spread(in[i] ^ 251920481205689ULL, 3);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 18
void stage_quantize_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 969003951311678559ULL);
    (void)lookup.get(0);  // build the table before the parallel region
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 19
void stage_quantize_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = masked_patch_digest(in.data(), n, i, len, 392552201547565093ULL);
    }
}

// Stage 20
void stage_quantize_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = mix64(in[i]) - mix64(in[n - 1 - i]) + 74743032508231ULL;
        out[i] = v;
        if ((v & 31) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 21
void stage_quantize_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 389899465870076747ULL);
    }
}

// Stage 22
void stage_quantize_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 3) % n]) ^ 109710020117839ULL;
        const uint64_t u = combine(in[i], 176267987589681ULL);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 23
void stage_quantize_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 4);
        const uint64_t u = rotl64(in[i] ^ 31134527574469ULL, 57) - mix64(in[i]);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

}  // namespace

void run_quantize(Context& ctx) {
    stage_quantize_00(ctx);
    stage_quantize_01(ctx);
    stage_quantize_02(ctx);
    stage_quantize_03(ctx);
    stage_quantize_04(ctx);
    stage_quantize_05(ctx);
    stage_quantize_06(ctx);
    stage_quantize_07(ctx);
    stage_quantize_08(ctx);
    stage_quantize_09(ctx);
    stage_quantize_10(ctx);
    stage_quantize_11(ctx);
    stage_quantize_12(ctx);
    stage_quantize_13(ctx);
    stage_quantize_14(ctx);
    stage_quantize_15(ctx);
    stage_quantize_16(ctx);
    stage_quantize_17(ctx);
    stage_quantize_18(ctx);
    stage_quantize_19(ctx);
    stage_quantize_20(ctx);
    stage_quantize_21(ctx);
    stage_quantize_22(ctx);
    stage_quantize_23(ctx);
}

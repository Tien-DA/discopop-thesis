// Geometry preparation stages.
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
void stage_geo_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 81384762590011ULL;
        const uint64_t u = in[i] * 253520174449771ULL + 31690021806221ULL;
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 01
void stage_geo_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 646441761507836737ULL;
        for (int d = -4; d <= 4; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 4));
        }
        out[i] = acc;
    }
}

// Stage 02
void stage_geo_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    #pragma omp parallel for reduction(max : peak)
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = mix64(in[i]) - mix64(in[n - 1 - i]) + 121036092845595ULL;
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
void stage_geo_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const ItemKernel kernel = kGeoKernels[0];
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = kernel(in.data(), n, i, len, 270679210665266311ULL);
    }
}

// Stage 04
void stage_geo_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 1143401990427679687ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 05
void stage_geo_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = folded_strip_digest(in.data(), n, i, len, 633561398677920343ULL);
    }
}

// Stage 06
void stage_geo_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 25474601623215217ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 07
void stage_geo_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 64846212184467147ULL);
    }
}

// Stage 08
void stage_geo_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 826808345145041835ULL;
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

// Stage 09
void stage_geo_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 470235904974577491ULL;
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

// Stage 10
void stage_geo_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const ItemKernel kernel = kGeoKernels[1];
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = kernel(in.data(), n, i, len, 405461799076759719ULL);
    }
}

// Stage 11
void stage_geo_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = blended_shard_digest(in.data(), n, i, len, 273114276481397465ULL);
    }
}

// Stage 12
void stage_geo_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 5) % n]) ^ 126568305947269ULL;
        out[i] = v;
        if ((v & 31) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 13
void stage_geo_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 626730475331966577ULL);
    }
}

// Stage 14
void stage_geo_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const ItemKernel kernel = kGeoKernels[0];
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = kernel(in.data(), n, i, len, 33440276393744485ULL);
    }
}

// Stage 15
void stage_geo_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 820571950318579809ULL);
    (void)lookup.get(0);  // build the table before the parallel region
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 16
void stage_geo_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 18) % n]) ^ 240657629807585ULL;
        const uint64_t u = in[i] * 79583530882167ULL + 9947941360270ULL;
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 17
void stage_geo_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 153542491041873659ULL);
    }
}

// Stage 18
void stage_geo_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 13) % n]) ^ 171028814510229ULL;
        const uint64_t u = mix64(in[i] + 203382668804393ULL) ^ rotl64(in[i], 40);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 19
void stage_geo_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 7) % n]) ^ 121550608900029ULL;
        out[i] = v;
        if ((v & 7) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 20
void stage_geo_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 316455043962731165ULL);
    }
}

// Stage 21
void stage_geo_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 3) % n]) ^ 164210650607377ULL;
        out[i] = v;
        if ((v & 31) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 22
void stage_geo_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 16588892797273ULL + rotl64(in[(i + 26) % n], 51);
        const uint64_t u = spread(in[i] ^ 190627829892295ULL, 1);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 23
void stage_geo_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = mix64(in[i]) - mix64(in[n - 1 - i]) + 249794662958033ULL;
        out[i] = v;
        #pragma omp critical(peak_update)
        {
            if (v > ctx.peak) {
                ctx.peak = v;
            }
        }
    }
}

}  // namespace

void run_geo(Context& ctx) {
    stage_geo_00(ctx);
    stage_geo_01(ctx);
    stage_geo_02(ctx);
    stage_geo_03(ctx);
    stage_geo_04(ctx);
    stage_geo_05(ctx);
    stage_geo_06(ctx);
    stage_geo_07(ctx);
    stage_geo_08(ctx);
    stage_geo_09(ctx);
    stage_geo_10(ctx);
    stage_geo_11(ctx);
    stage_geo_12(ctx);
    stage_geo_13(ctx);
    stage_geo_14(ctx);
    stage_geo_15(ctx);
    stage_geo_16(ctx);
    stage_geo_17(ctx);
    stage_geo_18(ctx);
    stage_geo_19(ctx);
    stage_geo_20(ctx);
    stage_geo_21(ctx);
    stage_geo_22(ctx);
    stage_geo_23(ctx);
}

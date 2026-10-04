// Matrix style kernels stages.
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
void stage_matrix_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 43896529851485ULL + rotl64(in[(i + 20) % n], 32);
        const uint64_t u = mix64(in[i] + 74938484987333ULL) ^ rotl64(in[i], 9);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 01
void stage_matrix_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 97402337876565ULL;
        const uint64_t u = in[i] * 128344675529867ULL + 16043084441233ULL;
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 02
void stage_matrix_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 226403411029889ULL + rotl64(in[(i + 17) % n], 43);
        const uint64_t u = spread(in[i] ^ 275919493381221ULL, 3);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 03
void stage_matrix_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 195029460447941ULL + rotl64(in[(i + 26) % n], 54);
        const uint64_t u = combine(in[i], 38655314101195ULL);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 04
void stage_matrix_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 257297719859647185ULL);
    (void)lookup.get(0);  // build the table before the parallel region
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 05
void stage_matrix_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 3);
        const uint64_t u = in[i] * 135611328066333ULL + 16951416008291ULL;
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 06
void stage_matrix_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 15) % n]) ^ 67003078682243ULL;
        out[i] = v;
        #pragma omp critical(peak_update)
        {
            if (v > ctx.peak) {
                ctx.peak = v;
            }
        }
    }
}

// Stage 07
void stage_matrix_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 116942093062459ULL;
        const uint64_t u = mix64(in[i] + 175706542887051ULL) ^ rotl64(in[i], 28);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 08
void stage_matrix_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 472085103099686239ULL;
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
void stage_matrix_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    uint64_t peak = 0;
    #pragma omp parallel for reduction(max : peak)
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 8) % n]) ^ 273070513214211ULL;
        out[i] = v;
        if (v > peak) {
            peak = v;
        }
    }
    if (peak > ctx.peak) {
        ctx.peak = peak;
    }
}

// Stage 10
void stage_matrix_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = rotl64(in[i] ^ 232781407607975ULL, 19) - mix64(in[i]);
    }
}

// Stage 11
void stage_matrix_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = folded_strip_digest(in.data(), n, i, len, 738786580476773105ULL);
    }
}

// Stage 12
void stage_matrix_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 1081035844780976501ULL;
        for (int d = -4; d <= 4; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 4));
        }
        out[i] = acc;
    }
}

// Stage 13
void stage_matrix_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 952190858253326291ULL;
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

// Stage 14
void stage_matrix_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 223392708832003ULL;
        const uint64_t u = in[i] * 222281349147163ULL + 27785168643395ULL;
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 15
void stage_matrix_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 622092076464107739ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 16
void stage_matrix_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 10) % n]) ^ 48058444471711ULL;
        const uint64_t u = combine(in[i], 53201714950419ULL);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 17
void stage_matrix_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 4);
        const uint64_t u = in[i] * 153995476109095ULL + 19249434513636ULL;
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 18
void stage_matrix_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = row_signature(in.data(), n, i, len, 650138469185928771ULL);
    }
}

// Stage 19
void stage_matrix_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 14) % n]) ^ 101445657759601ULL;
        const uint64_t u = in[i] * 73636103246135ULL + 9204512905766ULL;
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 20
void stage_matrix_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 279604487001302835ULL;
        for (int d = -4; d <= 4; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 4));
        }
        out[i] = acc;
    }
}

// Stage 21
void stage_matrix_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 535193141880954729ULL);
    }
}

// Stage 22
void stage_matrix_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 755910506656492361ULL);
    }
}

// Stage 23
void stage_matrix_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 509112586675901061ULL;
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

}  // namespace

void run_matrix(Context& ctx) {
    prepare_row_buffers(ctx.cfg.scratch_len);
    stage_matrix_00(ctx);
    stage_matrix_01(ctx);
    stage_matrix_02(ctx);
    stage_matrix_03(ctx);
    stage_matrix_04(ctx);
    stage_matrix_05(ctx);
    stage_matrix_06(ctx);
    stage_matrix_07(ctx);
    stage_matrix_08(ctx);
    stage_matrix_09(ctx);
    stage_matrix_10(ctx);
    stage_matrix_11(ctx);
    stage_matrix_12(ctx);
    stage_matrix_13(ctx);
    stage_matrix_14(ctx);
    stage_matrix_15(ctx);
    stage_matrix_16(ctx);
    stage_matrix_17(ctx);
    stage_matrix_18(ctx);
    stage_matrix_19(ctx);
    stage_matrix_20(ctx);
    stage_matrix_21(ctx);
    stage_matrix_22(ctx);
    stage_matrix_23(ctx);
}

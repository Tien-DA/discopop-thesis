// Resampling stages.
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
void stage_resample_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 288088877210641127ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 01
void stage_resample_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        uint64_t* slot = ctx.pool.acquire(blk);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(blk * 7 + k * 7) % n] ^ (679784535764615999ULL + k));
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

// Stage 02
void stage_resample_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 338323747593100731ULL);
    }
}

// Stage 03
void stage_resample_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 40) % n]) ^ 241142627297569ULL;
        const uint64_t u = combine(in[i], 182141117994829ULL);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 04
void stage_resample_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = combine(in[i], in[(i + 32) % n]) ^ 144388595672079ULL;
        out[i] = v;
        if ((v & 7) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 05
void stage_resample_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 685253686344109525ULL;
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

// Stage 06
void stage_resample_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 680254386915432243ULL);
    }
}

// Stage 07
void stage_resample_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 4);
        const uint64_t u = mix64(in[i] + 254552174577695ULL) ^ rotl64(in[i], 32);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 08
void stage_resample_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 422788982191158589ULL;
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
void stage_resample_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 1054900136671420243ULL);
    }
}

// Stage 10
void stage_resample_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 3148754001497ULL + rotl64(in[(i + 33) % n], 30);
        const uint64_t u = spread(in[i] ^ 142299471558249ULL, 3);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 11
void stage_resample_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 411578671031498697ULL);
    (void)lookup.get(0);  // build the table before the parallel region
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 12
void stage_resample_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 225866792036977ULL;
        const uint64_t u = rotl64(in[i] ^ 135286400430101ULL, 29) - mix64(in[i]);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 13
void stage_resample_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = mix64(in[i]) - mix64(in[n - 1 - i]) + 88592925904461ULL;
        out[i] = v;
        #pragma omp critical(peak_update)
        {
            if (v > ctx.peak) {
                ctx.peak = v;
            }
        }
    }
}

// Stage 14
void stage_resample_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 898903791843074393ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 15
void stage_resample_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 227575234729601ULL + rotl64(in[(i + 23) % n], 43);
        const uint64_t u = mix64(in[i] + 103688146988409ULL) ^ rotl64(in[i], 52);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 16
void stage_resample_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 14) % n]) ^ 108823513480085ULL;
        const uint64_t u = rotl64(in[i] ^ 257519808772065ULL, 18) - mix64(in[i]);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 17
void stage_resample_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        uint64_t* slot = ctx.pool.acquire(blk);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(blk * 7 + k * 3) % n] ^ (582276840282036379ULL + k));
        }
        uint64_t acc = 0x9ddfea08eb382d69ULL;
        for (std::size_t k = 0; k < len; ++k) {
            acc = acc * 31 + (slot[k] ^ (slot[(k + 1) % len] >> 6));
        }
        ctx.partial[blk] = acc;
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], ctx.partial[i % blocks]);
    }
}

// Stage 18
void stage_resample_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 209813722744831ULL + rotl64(in[(i + 14) % n], 53);
        const uint64_t u = mix64(in[i] + 100580615020673ULL) ^ rotl64(in[i], 48);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 19
void stage_resample_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 391393424359403725ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 20
void stage_resample_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 1130710166147427979ULL;
        for (int d = -2; d <= 2; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 2));
        }
        out[i] = acc;
    }
}

// Stage 21
void stage_resample_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 98701823944467ULL;
        const uint64_t u = combine(in[i], 154087690068257ULL);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 22
void stage_resample_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 357637405684862153ULL);
    }
}

// Stage 23
void stage_resample_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 100509350719113ULL;
        const uint64_t u = combine(in[i], 218570196889389ULL);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

}  // namespace

void run_resample(Context& ctx) {
    stage_resample_00(ctx);
    stage_resample_01(ctx);
    stage_resample_02(ctx);
    stage_resample_03(ctx);
    stage_resample_04(ctx);
    stage_resample_05(ctx);
    stage_resample_06(ctx);
    stage_resample_07(ctx);
    stage_resample_08(ctx);
    stage_resample_09(ctx);
    stage_resample_10(ctx);
    stage_resample_11(ctx);
    stage_resample_12(ctx);
    stage_resample_13(ctx);
    stage_resample_14(ctx);
    stage_resample_15(ctx);
    stage_resample_16(ctx);
    stage_resample_17(ctx);
    stage_resample_18(ctx);
    stage_resample_19(ctx);
    stage_resample_20(ctx);
    stage_resample_21(ctx);
    stage_resample_22(ctx);
    stage_resample_23(ctx);
}

// Graph relaxation stages.
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
void stage_graph_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 8691381167673ULL + rotl64(in[(i + 35) % n], 49);
        const uint64_t u = mix64(in[i] + 21227772631785ULL) ^ rotl64(in[i], 24);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 01
void stage_graph_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 847324741146720921ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 02
void stage_graph_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 512701986358910365ULL);
    }
}

// Stage 03
void stage_graph_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 191131521530245887ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 04
void stage_graph_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 1);
        const uint64_t u = combine(in[i], 183407627588567ULL);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 05
void stage_graph_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 229448752377617ULL + rotl64(in[(i + 38) % n], 14);
        const uint64_t u = rotl64(in[i] ^ 126612604780213ULL, 40) - mix64(in[i]);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 06
void stage_graph_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 18064724265581ULL;
        const uint64_t u = spread(in[i] ^ 21844101377477ULL, 4);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 07
void stage_graph_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    #pragma omp parallel for reduction(+ : total)
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 941747275516598185ULL);
    }
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 08
void stage_graph_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 37823741870032065ULL;
        for (int d = -4; d <= 4; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 4));
        }
        out[i] = acc;
    }
}

// Stage 09
void stage_graph_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 1103152060677625307ULL);
    (void)lookup.get(0);  // build the table before the parallel region
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 10
void stage_graph_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], 154981217438219ULL);
    }
}

// Stage 11
void stage_graph_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 269872958530545ULL;
        const uint64_t u = in[i] * 115938517138341ULL + 14492314642292ULL;
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 12
void stage_graph_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 887827754226766733ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 13
void stage_graph_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        uint64_t* slot = ctx.pool.acquire(blk);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(blk * 7 + k * 5) % n] ^ (131242855738591157ULL + k));
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

// Stage 14
void stage_graph_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = blended_shard_digest(in.data(), n, i, len, 321056661169871733ULL);
    }
}

// Stage 15
void stage_graph_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const std::size_t blocks = ctx.cfg.blocks;
    const std::size_t per_block = (n + blocks - 1) / blocks;
    #pragma omp parallel for
    for (std::size_t blk = 0; blk < blocks; ++blk) {
        const std::size_t lo = blk * per_block;
        const std::size_t hi = lo + per_block < n ? lo + per_block : n;
        uint64_t acc = 364809336633884743ULL;
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

// Stage 16
void stage_graph_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = in[i] * 119590815708375ULL + rotl64(in[(i + 6) % n], 19);
        const uint64_t u = combine(in[i], 265229712197461ULL);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 17
void stage_graph_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t* slot = ctx.pool.acquire(i);
        for (std::size_t k = 0; k < len; ++k) {
            slot[k] = mix64(in[(i + k * 5) % n] ^ (164506890553555319ULL + k));
        }
        uint64_t acc = 0x243f6a8885a308d3ULL;
        for (std::size_t k = 0; k < len; ++k) {
            acc = acc * 29 + (slot[k] ^ (slot[(k + 1) % len] >> 6));
        }
        out[i] = acc;
    }
}

// Stage 18
void stage_graph_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 275441540796385623ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 19
void stage_graph_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 577272576718368047ULL);
    }
}

// Stage 20
void stage_graph_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = in[i] * 126960591177179ULL + rotl64(in[(i + 3) % n], 20);
        out[i] = v;
        if ((v & 31) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 21
void stage_graph_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] * 64311441480331ULL + 8038930185041ULL;
    }
}

// Stage 22
void stage_graph_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t v = mix64(in[i]) - mix64(in[n - 1 - i]) + 115921771801577ULL;
        out[i] = v;
        if ((v & 15) == 0) {
            #pragma omp atomic
            ctx.hits += 1;
        }
    }
}

// Stage 23
void stage_graph_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    #pragma omp parallel for
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 232881931535275ULL;
        const uint64_t u = mix64(in[i] + 249240236406877ULL) ^ rotl64(in[i], 26);
        out[i] = (combine(t, in[i])) ^ u;
    }
}

}  // namespace

void run_graph(Context& ctx) {
    stage_graph_00(ctx);
    stage_graph_01(ctx);
    stage_graph_02(ctx);
    stage_graph_03(ctx);
    stage_graph_04(ctx);
    stage_graph_05(ctx);
    stage_graph_06(ctx);
    stage_graph_07(ctx);
    stage_graph_08(ctx);
    stage_graph_09(ctx);
    stage_graph_10(ctx);
    stage_graph_11(ctx);
    stage_graph_12(ctx);
    stage_graph_13(ctx);
    stage_graph_14(ctx);
    stage_graph_15(ctx);
    stage_graph_16(ctx);
    stage_graph_17(ctx);
    stage_graph_18(ctx);
    stage_graph_19(ctx);
    stage_graph_20(ctx);
    stage_graph_21(ctx);
    stage_graph_22(ctx);
    stage_graph_23(ctx);
}

// Consistency auditing stages.
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
void stage_audit_00(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    uint64_t total = 0;
    for (std::size_t i = 0; i < n; ++i) {
        total += mix64(in[i] ^ 363935980887118637ULL);
    }
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = in[i] + total;
    }
}

// Stage 01
void stage_audit_01(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 517304554941431721ULL;
        for (int d = -2; d <= 2; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 2));
        }
        out[i] = acc;
    }
}

// Stage 02
void stage_audit_02(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 175198117418497ULL;
        const uint64_t u = in[i] * 174477345207159ULL + 21809668150894ULL;
        out[i] = (combine(t, in[i])) ^ u;
    }
}

// Stage 03
void stage_audit_03(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 642744326240606711ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 04
void stage_audit_04(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = strided_panel_digest(in.data(), n, i, len, 34097493382799369ULL);
    }
}

// Stage 05
void stage_audit_05(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 88864486018639ULL;
        const uint64_t u = rotl64(in[i] ^ 100097303801909ULL, 53) - mix64(in[i]);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 06
void stage_audit_06(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 159679165936707ULL;
        const uint64_t u = spread(in[i] ^ 142060135805211ULL, 4);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 07
void stage_audit_07(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = tapered_span_digest(in.data(), n, i, len, 667461371104078615ULL);
    }
}

// Stage 08
void stage_audit_08(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 1078870662156520267ULL);
    }
}

// Stage 09
void stage_audit_09(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 650728210802689645ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 10
void stage_audit_10(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 914505009137234833ULL);
    }
}

// Stage 11
void stage_audit_11(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 4);
        const uint64_t u = rotl64(in[i] ^ 28441974820677ULL, 47) - mix64(in[i]);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 12
void stage_audit_12(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 1074753868739539307ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 13
void stage_audit_13(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 910439174477607193ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 14
void stage_audit_14(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 298655252458210301ULL);
    }
}

// Stage 15
void stage_audit_15(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    const Lookup lookup(ctx.cfg.scratch_len, 58465296080006777ULL);
    (void)lookup.get(0);  // build the table before use
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[i], lookup.get(i));
    }
}

// Stage 16
void stage_audit_16(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = fold_range(in.data(), n, i, 4);
        const uint64_t u = mix64(in[i] + 199961487937425ULL) ^ rotl64(in[i], 37);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 17
void stage_audit_17(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[ctx.perm[i]] = combine(in[i], 1096020184277162923ULL);
    }
}

// Stage 18
void stage_audit_18(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[2];
    std::vector<uint64_t>& out = ctx.buf[3];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = mix64(in[i]) - mix64(in[n - 1 - i]) + 122837873368253ULL;
        const uint64_t u = rotl64(in[i] ^ 263758305580319ULL, 27) - mix64(in[i]);
        out[i] = (t + in[i]) ^ u;
    }
}

// Stage 19
void stage_audit_19(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[3];
    std::vector<uint64_t>& out = ctx.buf[4];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        const uint64_t t = combine(in[i], in[(i + 40) % n]) ^ 263495911798791ULL;
        const uint64_t u = mix64(in[i] + 233682808899037ULL) ^ rotl64(in[i], 5);
        out[i] = (t ^ rotl64(in[i], 9)) ^ u;
    }
}

// Stage 20
void stage_audit_20(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[4];
    std::vector<uint64_t>& out = ctx.buf[5];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        uint64_t acc = 363229233170205021ULL;
        for (int d = -3; d <= 3; ++d) {
            acc = combine(acc, in[clamp_index(static_cast<long>(i) + d, n)] + static_cast<uint64_t>(d + 3));
        }
        out[i] = acc;
    }
}

// Stage 21
void stage_audit_21(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[5];
    std::vector<uint64_t>& out = ctx.buf[0];
    const std::size_t n = ctx.cfg.items;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = combine(in[ctx.table[i]], in[i] ^ 207265134835512839ULL);
    }
}

// Stage 22
void stage_audit_22(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[0];
    std::vector<uint64_t>& out = ctx.buf[1];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = tapered_span_digest(in.data(), n, i, len, 1110652199357614137ULL);
    }
}

// Stage 23
void stage_audit_23(Context& ctx) {
    const std::vector<uint64_t>& in = ctx.buf[1];
    std::vector<uint64_t>& out = ctx.buf[2];
    const std::size_t n = ctx.cfg.items;
    const std::size_t len = ctx.cfg.scratch_len;
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = banded_lane_digest(in.data(), n, i, len, 144192342823268459ULL);
    }
}

}  // namespace

void run_audit(Context& ctx) {
    stage_audit_00(ctx);
    stage_audit_01(ctx);
    stage_audit_02(ctx);
    stage_audit_03(ctx);
    stage_audit_04(ctx);
    stage_audit_05(ctx);
    stage_audit_06(ctx);
    stage_audit_07(ctx);
    stage_audit_08(ctx);
    stage_audit_09(ctx);
    stage_audit_10(ctx);
    stage_audit_11(ctx);
    stage_audit_12(ctx);
    stage_audit_13(ctx);
    stage_audit_14(ctx);
    stage_audit_15(ctx);
    stage_audit_16(ctx);
    stage_audit_17(ctx);
    stage_audit_18(ctx);
    stage_audit_19(ctx);
    stage_audit_20(ctx);
    stage_audit_21(ctx);
    stage_audit_22(ctx);
    stage_audit_23(ctx);
}

#include "kernels.h"

#include <vector>

#include "mix.h"

uint64_t rolling_tile_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    std::vector<uint64_t> w(len);
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 7) % n] ^ (salt + k));
    }
    uint64_t acc = 4228414519ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 33 + (w[k] ^ (w[(k + 1) % len] >> 7));
    }
    return acc;
}

uint64_t banded_lane_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    uint64_t w[kMaxScratch];
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 3) % n] ^ (salt + k));
    }
    uint64_t acc = 225749088899ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 31 + (w[k] ^ (w[(k + 1) % len] >> 7));
    }
    return acc;
}

uint64_t folded_strip_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    std::vector<uint64_t> w(len);
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 11) % n] ^ (salt + k));
    }
    uint64_t acc = 125687898617ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 31 + (w[k] ^ (w[(k + 1) % len] >> 9));
    }
    return acc;
}

uint64_t tapered_span_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    uint64_t w[kMaxScratch];
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 5) % n] ^ (salt + k));
    }
    uint64_t acc = 978419704265ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 37 + (w[k] ^ (w[(k + 1) % len] >> 4));
    }
    return acc;
}

uint64_t strided_panel_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    std::vector<uint64_t> w(len);
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 7) % n] ^ (salt + k));
    }
    uint64_t acc = 554097656137ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 29 + (w[k] ^ (w[(k + 1) % len] >> 11));
    }
    return acc;
}

uint64_t blended_shard_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    uint64_t w[kMaxScratch];
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 13) % n] ^ (salt + k));
    }
    uint64_t acc = 497937956371ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 37 + (w[k] ^ (w[(k + 1) % len] >> 12));
    }
    return acc;
}

uint64_t coarse_slice_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    std::vector<uint64_t> w(len);
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 7) % n] ^ (salt + k));
    }
    uint64_t acc = 549541179375ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 31 + (w[k] ^ (w[(k + 1) % len] >> 8));
    }
    return acc;
}

uint64_t masked_patch_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    uint64_t w[kMaxScratch];
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 3) % n] ^ (salt + k));
    }
    uint64_t acc = 552918954919ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 31 + (w[k] ^ (w[(k + 1) % len] >> 11));
    }
    return acc;
}


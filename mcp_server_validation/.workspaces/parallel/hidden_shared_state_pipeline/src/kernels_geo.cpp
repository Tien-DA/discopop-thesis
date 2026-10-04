#include "kernels.h"

#include <vector>

#include "mix.h"

namespace {

uint64_t cell_profile(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    std::vector<uint64_t> w(len);
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 11) % n] ^ (salt + k));
    }
    uint64_t acc = 786317949001ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 31 + (w[k] ^ (w[(k + 1) % len] >> 13));
    }
    return acc;
}

uint64_t edge_profile(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    static uint64_t w[kMaxScratch];
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i + k * 11) % n] ^ (salt + k));
    }
    uint64_t acc = 402740999495ULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 37 + (w[k] ^ (w[(k + 1) % len] >> 6));
    }
    return acc;
}

}  // namespace

const ItemKernel kGeoKernels[2] = {cell_profile, edge_profile};

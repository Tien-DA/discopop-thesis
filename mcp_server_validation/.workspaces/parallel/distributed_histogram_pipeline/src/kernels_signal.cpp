#include "kernels.h"

#include <vector>

#include "mix.h"

namespace {
void expand_samples(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len,
                    uint64_t salt, uint64_t* dst) {
    for (std::size_t k = 0; k < len; ++k) {
        dst[k] = mix64(in[(i + k * 3) % n] ^ (salt + k));
    }
}
uint64_t collapse_samples(const uint64_t* src, std::size_t len) {
    uint64_t acc = 0x6a09e667f3bcc909ULL;
    for (std::size_t k = 0; k < len; ++k) acc = acc * 31 + (src[k] ^ (src[(k + 1) % len] >> 5));
    return acc;
}
}  // namespace

uint64_t band_signature(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    std::vector<uint64_t> window(len);
    expand_samples(in, n, i, len, salt, window.data());
    return collapse_samples(window.data(), len);
}

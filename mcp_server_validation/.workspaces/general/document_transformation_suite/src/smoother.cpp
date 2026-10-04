#include "smoother.h"

#include "mix.h"

Smoother::Smoother(std::size_t len, uint64_t salt) : len_(len), salt_(salt), tmp_(len) {}

uint64_t Smoother::apply(const uint64_t* in, std::size_t n, std::size_t i) const {
    std::vector<uint64_t>& tmp = tmp_;
    for (std::size_t k = 0; k < len_; ++k) {
        tmp[k] = mix64(in[(i * 3 + k * 5) % n] ^ (salt_ + k));
    }
    uint64_t acc = 0x2545f4914f6cdd1dULL;
    for (std::size_t k = 0; k < len_; ++k) {
        acc = acc * 33 + (tmp[k] ^ (tmp[(k + 2) % len_] >> 9));
    }
    return acc;
}

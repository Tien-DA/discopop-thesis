#include "kernels.h"

#include <vector>

#include "mix.h"

namespace {

std::vector<uint64_t>& shared_buffer(std::size_t n) {
    static std::vector<uint64_t> buffer;
    if (buffer.size() < n) {
        buffer.resize(n);
    }
    return buffer;
}

}  // namespace

void prepare_row_buffers(std::size_t len) {
    shared_buffer(len);
}

uint64_t row_signature(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt) {
    std::vector<uint64_t>& w = shared_buffer(len);
    for (std::size_t k = 0; k < len; ++k) {
        w[k] = mix64(in[(i * 5 + k * 7) % n] ^ (salt + k));
    }
    uint64_t acc = 0x3c6ef372fe94f82bULL;
    for (std::size_t k = 0; k < len; ++k) {
        acc = acc * 37 + (w[k] ^ (w[(k + 3) % len] >> 11));
    }
    return acc;
}

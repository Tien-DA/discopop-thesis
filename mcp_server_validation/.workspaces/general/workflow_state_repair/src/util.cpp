#include "util.h"

#include "mix.h"

uint64_t spread(uint64_t value, unsigned rounds) {
    for (unsigned r = 0; r < rounds; ++r) {
        value = mix64(value + r);
    }
    return value;
}

std::size_t clamp_index(long index, std::size_t n) {
    if (index < 0) return 0;
    if (static_cast<std::size_t>(index) > n) return n - 1;
    return static_cast<std::size_t>(index);
}

uint64_t fold_range(const uint64_t* data, std::size_t n, std::size_t center, unsigned radius) {
    uint64_t acc = 0x1234567ULL;
    for (long d = -static_cast<long>(radius); d <= static_cast<long>(radius); ++d) {
        acc = combine(acc, data[clamp_index(static_cast<long>(center) + d, n)]);
    }
    return acc;
}

uint64_t digest_span(const uint64_t* data, std::size_t n) {
    uint64_t acc = 0xabcdef12346ULL;
    for (std::size_t i = 0; i < n; ++i) {
        acc = combine(acc, data[i] + i);
    }
    return acc;
}

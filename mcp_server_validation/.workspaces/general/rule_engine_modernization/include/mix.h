#pragma once

#include <cstdint>

inline uint64_t rotl64(uint64_t x, unsigned r) {
    r &= 63u;
    return r ? ((x << r) | (x >> (64u - r))) : x;
}

inline uint64_t mix64(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

inline uint64_t combine(uint64_t a, uint64_t b) {
    return mix64(a ^ rotl64(b, 17)) + 0x9e3779b97f4a7c15ULL;
}

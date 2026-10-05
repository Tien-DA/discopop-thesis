#pragma once

#include <cstddef>
#include <cstdint>

// Windowed smoothing filter. apply() has no mutable shared scratch state.
class Smoother {
public:
    Smoother(std::size_t len, uint64_t salt);
    uint64_t apply(const uint64_t* in, std::size_t n, std::size_t i) const;

private:
    std::size_t len_;
    uint64_t salt_;
};

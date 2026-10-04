#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

// Windowed smoothing filter. apply() does not change the observable state
// of the filter.
class Smoother {
public:
    Smoother(std::size_t len, uint64_t salt);
    uint64_t apply(const uint64_t* in, std::size_t n, std::size_t i) const;

private:
    std::size_t len_;
    uint64_t salt_;
    mutable std::vector<uint64_t> tmp_;
};

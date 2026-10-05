#pragma once

#include <cstddef>
#include <cstdint>
#include <mutex>
#include <vector>

// Table of derived constants that is built once on first use.
class Lookup {
public:
    Lookup(std::size_t len, uint64_t salt);
    uint64_t get(std::size_t k) const;

private:
    void build() const;

    std::size_t len_;
    uint64_t salt_;
    mutable std::vector<uint64_t> memo_;
    mutable std::once_flag build_once_;
};

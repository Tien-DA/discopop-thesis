#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

// Table of derived constants that is built lazily on first use.
class Lookup {
public:
    Lookup(std::size_t len, uint64_t salt);
    uint64_t get(std::size_t k) const;

private:
    void build() const;

    std::size_t len_;
    uint64_t salt_;
    mutable std::vector<uint64_t> memo_;
    mutable bool ready_ = false;
};

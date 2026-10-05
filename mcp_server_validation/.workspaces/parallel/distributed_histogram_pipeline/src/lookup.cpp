#include "lookup.h"

#include "mix.h"

Lookup::Lookup(std::size_t len, uint64_t salt) : len_(len), salt_(salt) {}

void Lookup::build() const {
    memo_.resize(len_);
    for (std::size_t k = 0; k < len_; ++k) {
        memo_[k] = mix64(salt_ + k * 0x9e3779b9ULL);
    }
}

uint64_t Lookup::get(std::size_t k) const {
    std::call_once(build_once_, [this] { build(); });
    return memo_[k % len_];
}

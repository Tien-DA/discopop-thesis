#pragma once

#include <cstddef>
#include <cstdint>

#include "config.h"

using ItemKernel = uint64_t (*)(const uint64_t*, std::size_t, std::size_t, std::size_t, uint64_t);

// Item kernels: digest of a scratch window derived from the input around item i.
uint64_t rolling_tile_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);
uint64_t banded_lane_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);
uint64_t folded_strip_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);
uint64_t tapered_span_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);
uint64_t strided_panel_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);
uint64_t blended_shard_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);
uint64_t coarse_slice_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);
uint64_t masked_patch_digest(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);

uint64_t band_signature(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);
extern const ItemKernel kGeoKernels[2];
void prepare_row_buffers(std::size_t len);
uint64_t row_signature(const uint64_t* in, std::size_t n, std::size_t i, std::size_t len, uint64_t salt);

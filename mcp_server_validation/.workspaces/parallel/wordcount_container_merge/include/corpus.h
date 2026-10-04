#pragma once

#include <cstddef>
#include <string>
#include <vector>

// Deterministic synthetic text: 'line_count' lines of 'words_per_line'
// space-separated words drawn from a vocabulary of 'vocabulary_size' distinct
// words ("w0", "w1", ...) with a skewed (frequent-words-first) distribution.
std::vector<std::string> make_corpus(std::size_t line_count, std::size_t words_per_line,
                                     std::size_t vocabulary_size, unsigned seed);

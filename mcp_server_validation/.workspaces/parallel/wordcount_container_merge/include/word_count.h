#pragma once

#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using WordCounts = std::unordered_map<std::string, long long>;

// Number of occurrences of every distinct word in all lines.
WordCounts count_words_serial(const std::vector<std::string>& lines);
WordCounts count_words_parallel(const std::vector<std::string>& lines);

// The k most frequent words, ordered by count (descending) and then by word
// (ascending), so the result is fully deterministic.
std::vector<std::pair<std::string, long long>> top_k(const WordCounts& counts, std::size_t k);

// Sum of all counts.
long long total_words(const WordCounts& counts);

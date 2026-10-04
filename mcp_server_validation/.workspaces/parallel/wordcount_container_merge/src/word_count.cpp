#include "word_count.h"

#include <algorithm>

#include "tokenizer.h"

WordCounts count_words_serial(const std::vector<std::string>& lines) {
    WordCounts counts;
    for (const std::string& line : lines) {
        for (const std::string& word : split_words(line)) {
            ++counts[word];
        }
    }
    return counts;
}

// BUG: all threads insert into and increment the same std::unordered_map.
// The standard containers are not thread-safe: concurrent operator[] calls
// race on the bucket array, on node allocation and on rehashing, so
// increments are lost, entries can disappear or be duplicated, and the
// program can crash or hang inside the hash table.
WordCounts count_words_parallel(const std::vector<std::string>& lines) {
    WordCounts counts;

    #pragma omp parallel for
    for (std::size_t i = 0; i < lines.size(); ++i) {
        for (const std::string& word : split_words(lines[i])) {
            ++counts[word];
        }
    }
    return counts;
}

std::vector<std::pair<std::string, long long>> top_k(const WordCounts& counts, std::size_t k) {
    std::vector<std::pair<std::string, long long>> entries(counts.begin(), counts.end());
    std::sort(entries.begin(), entries.end(), [](const auto& a, const auto& b) {
        if (a.second != b.second) return a.second > b.second;
        return a.first < b.first;
    });
    if (entries.size() > k) entries.resize(k);
    return entries;
}

long long total_words(const WordCounts& counts) {
    long long total = 0;
    for (const auto& entry : counts) total += entry.second;
    return total;
}

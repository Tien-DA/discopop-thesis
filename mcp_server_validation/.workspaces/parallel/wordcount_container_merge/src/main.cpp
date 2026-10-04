#include <iostream>

#include "corpus.h"
#include "word_count.h"

int main() {
    std::vector<std::string> lines = make_corpus(400, 20, /*vocabulary_size=*/500, /*seed=*/6);
    WordCounts counts = count_words_parallel(lines);

    std::cout << "distinct words: " << counts.size() << std::endl;
    std::cout << "total words: " << total_words(counts) << std::endl;
    for (const auto& entry : top_k(counts, 3)) {
        std::cout << entry.first << ": " << entry.second << std::endl;
    }
    return 0;
}

#include <iostream>
#include <string>
#include <vector>

#include "corpus.h"
#include "tokenizer.h"
#include "word_count.h"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

bool test_split_words() {
    std::vector<std::string> expected = {"a", "bb", "c"};
    return split_words("  a bb   c ") == expected && split_words("").empty() && split_words("   ").empty();
}

bool test_serial_count_known_result() {
    std::vector<std::string> lines = {"a b a", "b c", "a"};
    WordCounts counts = count_words_serial(lines);
    return counts.size() == 3 && counts["a"] == 3 && counts["b"] == 2 && counts["c"] == 1 &&
           total_words(counts) == 6;
}

bool test_parallel_matches_serial_repeated() {
#ifdef _OPENMP
    omp_set_num_threads(32);
#endif
    std::vector<std::string> lines = make_corpus(6000, 30, /*vocabulary_size=*/20000, /*seed=*/11);
    WordCounts expected = count_words_serial(lines);
    for (int trial = 0; trial < 8; ++trial) {
        WordCounts actual = count_words_parallel(lines);
        if (actual != expected) return false;
    }
    return true;
}

bool test_parallel_total_and_top_k() {
#ifdef _OPENMP
    omp_set_num_threads(32);
#endif
    std::vector<std::string> lines = make_corpus(5000, 25, /*vocabulary_size=*/3000, /*seed=*/12);
    WordCounts expected = count_words_serial(lines);
    for (int trial = 0; trial < 5; ++trial) {
        WordCounts actual = count_words_parallel(lines);
        if (total_words(actual) != 5000LL * 25) return false;
        if (top_k(actual, 10) != top_k(expected, 10)) return false;
    }
    return true;
}

bool test_parallel_edge_cases() {
#ifdef _OPENMP
    omp_set_num_threads(16);
#endif
    std::vector<std::string> empty;
    if (!count_words_parallel(empty).empty()) return false;

    std::vector<std::string> blanks = {"", "   ", ""};
    if (!count_words_parallel(blanks).empty()) return false;

    std::vector<std::string> one_word(1000, "same");
    WordCounts counts = count_words_parallel(one_word);
    return counts.size() == 1 && counts["same"] == 1000;
}

}  // namespace

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"split_words", test_split_words},
        {"serial_count_known_result", test_serial_count_known_result},
        {"parallel_matches_serial_repeated", test_parallel_matches_serial_repeated},
        {"parallel_total_and_top_k", test_parallel_total_and_top_k},
        {"parallel_edge_cases", test_parallel_edge_cases}
    };

    int failures = 0;
    for (const Test& test : tests) {
        bool passed = test.function();
        if (passed) {
            std::cout << "[PASS] " << test.name << std::endl;
        } else {
            std::cerr << "[FAIL] " << test.name << std::endl;
            ++failures;
        }
    }

    if (failures > 0) {
        std::cerr << failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}

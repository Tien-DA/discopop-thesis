#include "tokenizer.h"

std::vector<std::string> split_words(const std::string& line) {
    std::vector<std::string> words;
    std::size_t start = 0;
    while (start < line.size()) {
        while (start < line.size() && line[start] == ' ') ++start;
        std::size_t end = start;
        while (end < line.size() && line[end] != ' ') ++end;
        if (end > start) words.push_back(line.substr(start, end - start));
        start = end;
    }
    return words;
}

#pragma once

#include <string>
#include <vector>

// Splits a line on spaces; consecutive spaces produce no empty tokens.
std::vector<std::string> split_words(const std::string& line);

#include <cmath>
#include <iostream>
#include <sstream>
#include <stack>
#include <stdexcept>
#include <string>
#include <vector>

// BUG: splits on a single literal space character. Any run of consecutive
// whitespace (extra spaces, tabs) produces empty-string tokens instead of
// being treated as one delimiter.
std::vector<std::string> tokenize(const std::string& expression) {
    std::vector<std::string> tokens;
    std::string current;
    for (char c : expression) {
        if (c == ' ') {
            tokens.push_back(current);
            current.clear();
        } else {
            current.push_back(c);
        }
    }
    tokens.push_back(current);
    return tokens;
}

bool is_operator(const std::string& token) {
    return token == "+" || token == "-" || token == "*" || token == "/";
}

double apply_operator(const std::string& op, double a, double b) {
    if (op == "+") return a + b;
    if (op == "-") return a - b;
    if (op == "*") return a * b;
    if (op == "/") {
        if (b == 0.0) {
            throw std::domain_error("division by zero");
        }
        return a / b;
    }
    throw std::invalid_argument("unknown operator: " + op);
}

double evaluate_rpn(const std::vector<std::string>& tokens) {
    std::stack<double> operands;
    for (const std::string& token : tokens) {
        if (is_operator(token)) {
            if (operands.size() < 2) {
                throw std::invalid_argument("insufficient operands");
            }
            double b = operands.top();
            operands.pop();
            double a = operands.top();
            operands.pop();
            operands.push(apply_operator(token, a, b));
        } else {
            operands.push(std::stod(token));
        }
    }
    if (operands.size() != 1) {
        throw std::invalid_argument("malformed expression");
    }
    return operands.top();
}

double evaluate(const std::string& expression) {
    return evaluate_rpn(tokenize(expression));
}

bool nearly_equal(double a, double b) {
    return std::abs(a - b) < 1e-9;
}

bool test_single_space_still_works() {
    return nearly_equal(evaluate("3 4 +"), 7.0);
}

bool test_extra_spaces_between_tokens() {
    return nearly_equal(evaluate("3    4   +"), 7.0);
}

bool test_leading_and_trailing_spaces() {
    return nearly_equal(evaluate("  6 2 -  "), 4.0);
}

bool test_tabs_as_delimiters() {
    return nearly_equal(evaluate("20\t5\t/"), 4.0);
}

bool test_mixed_whitespace_compound_expression() {
    return nearly_equal(evaluate("5  3 -\t10   2 /  *"), 10.0);
}

bool test_malformed_still_throws() {
    bool threw = false;
    try {
        evaluate("3   4");
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    return threw;
}

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"single_space_still_works", test_single_space_still_works},
        {"extra_spaces_between_tokens", test_extra_spaces_between_tokens},
        {"leading_and_trailing_spaces", test_leading_and_trailing_spaces},
        {"tabs_as_delimiters", test_tabs_as_delimiters},
        {"mixed_whitespace_compound_expression", test_mixed_whitespace_compound_expression},
        {"malformed_still_throws", test_malformed_still_throws}
    };

    int failures = 0;
    for (const Test& test : tests) {
        bool passed = test.function();
        if (passed) {
            std::cout << "[PASS] " << test.name << '\n';
        } else {
            std::cerr << "[FAIL] " << test.name << '\n';
            ++failures;
        }
    }

    if (failures > 0) {
        std::cerr << failures << " test(s) failed.\n";
        return 1;
    }

    std::cout << "All tests passed.\n";
    return 0;
}
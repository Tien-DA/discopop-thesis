#include <cmath>
#include <iostream>
#include <sstream>
#include <stack>
#include <stdexcept>
#include <string>
#include <vector>

std::vector<std::string> tokenize(const std::string& expression) {
    std::vector<std::string> tokens;
    std::istringstream stream(expression);
    std::string token;
    while (stream >> token) {
        tokens.push_back(token);
    }
    return tokens;
}

// NOTE: "^" is not yet recognized as an operator. See benchmark.json.
bool is_operator(const std::string& token) {
    return token == "+" || token == "-" || token == "*" || token == "/";
}

// NOTE: no case for "^" yet. See benchmark.json.
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

bool test_addition() {
    return nearly_equal(evaluate("3 4 +"), 7.0);
}

bool test_subtraction() {
    return nearly_equal(evaluate("6 2 -"), 4.0);
}

bool test_division() {
    return nearly_equal(evaluate("20 5 /"), 4.0);
}

bool test_power_basic() {
    return nearly_equal(evaluate("2 10 ^"), 1024.0);
}

bool test_power_fractional_exponent() {
    return nearly_equal(evaluate("9 0.5 ^"), 3.0);
}

bool test_power_in_compound_expression() {
    // 2^3 + 4^2 = 8 + 16 = 24
    return nearly_equal(evaluate("2 3 ^ 4 2 ^ +"), 24.0);
}

bool test_unknown_operator_throws() {
    bool threw = false;
    try {
        evaluate("3 4 %");
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
        {"addition", test_addition},
        {"subtraction", test_subtraction},
        {"division", test_division},
        {"power_basic", test_power_basic},
        {"power_fractional_exponent", test_power_fractional_exponent},
        {"power_in_compound_expression", test_power_in_compound_expression},
        {"unknown_operator_throws", test_unknown_operator_throws}
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
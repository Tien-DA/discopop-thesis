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

// DUPLICATION: sum_all and product_all repeat the same "loop over values,
// accumulate into a running total" structure, differing only in the
// operator (+ vs *) and the starting identity value (0.0 vs 1.0).
double sum_all(const std::vector<double>& values) {
    double total = 0.0;
    for (double value : values) {
        total += value;
    }
    return total;
}

double product_all(const std::vector<double>& values) {
    double total = 1.0;
    for (double value : values) {
        total *= value;
    }
    return total;
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

bool test_sum_all_basic() {
    return nearly_equal(sum_all({1.0, 2.0, 3.0, 4.0}), 10.0);
}

bool test_sum_all_empty() {
    return nearly_equal(sum_all({}), 0.0);
}

bool test_product_all_basic() {
    return nearly_equal(product_all({1.0, 2.0, 3.0, 4.0}), 24.0);
}

bool test_product_all_empty() {
    return nearly_equal(product_all({}), 1.0);
}

bool test_product_all_with_zero() {
    return nearly_equal(product_all({5.0, 0.0, 3.0}), 0.0);
}

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"addition", test_addition},
        {"subtraction", test_subtraction},
        {"sum_all_basic", test_sum_all_basic},
        {"sum_all_empty", test_sum_all_empty},
        {"product_all_basic", test_product_all_basic},
        {"product_all_empty", test_product_all_empty},
        {"product_all_with_zero", test_product_all_with_zero}
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
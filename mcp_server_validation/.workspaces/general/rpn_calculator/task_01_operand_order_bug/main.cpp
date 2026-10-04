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

// BUG: operands are popped in the wrong order relative to apply_operator's
// (a, b) = (left, right) convention. The first pop is the right operand,
// the second pop is the left operand, but they are named/passed as if the
// reverse were true.
double evaluate_rpn(const std::vector<std::string>& tokens) {
    std::stack<double> operands;
    for (const std::string& token : tokens) {
        if (is_operator(token)) {
            if (operands.size() < 2) {
                throw std::invalid_argument("insufficient operands");
            }
            double a = operands.top();
            operands.pop();
            double b = operands.top();
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

bool test_multiplication() {
    return nearly_equal(evaluate("3 4 *"), 12.0);
}

bool test_subtraction_order() {
    return nearly_equal(evaluate("6 2 -"), 4.0);
}

bool test_division_order() {
    return nearly_equal(evaluate("20 5 /"), 4.0);
}

bool test_compound_expression() {
    // (5 - 3) * (10 / 2) = 2 * 5 = 10
    return nearly_equal(evaluate("5 3 - 10 2 / *"), 10.0);
}

bool test_division_by_zero_throws() {
    bool threw = false;
    try {
        evaluate("1 0 /");
    } catch (const std::domain_error&) {
        threw = true;
    }
    return threw;
}

bool test_malformed_throws() {
    bool threw = false;
    try {
        evaluate("3 4");
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
        {"multiplication", test_multiplication},
        {"subtraction_order", test_subtraction_order},
        {"division_order", test_division_order},
        {"compound_expression", test_compound_expression},
        {"division_by_zero_throws", test_division_by_zero_throws},
        {"malformed_throws", test_malformed_throws}
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
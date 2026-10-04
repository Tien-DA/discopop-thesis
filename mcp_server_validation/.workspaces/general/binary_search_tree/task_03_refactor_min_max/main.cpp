#include <algorithm>
#include <cstddef>
#include <iostream>
#include <stdexcept>
#include <vector>

struct Node {
    int value;
    Node* left;
    Node* right;
};

class BinarySearchTree {
public:
    BinarySearchTree() : root_(nullptr), size_(0) {}

    ~BinarySearchTree() {
        destroy(root_);
    }

    void insert(int value) {
        root_ = insert_node(root_, value);
    }

    bool contains(int value) const {
        return contains_node(root_, value);
    }

    std::vector<int> in_order() const {
        std::vector<int> result;
        in_order_node(root_, result);
        return result;
    }

    std::size_t size() const {
        return size_;
    }

    // DUPLICATION: min_value and max_value repeat the same "walk down one
    // side until nullptr" loop, differing only in which child is followed.
    int min_value() const {
        if (root_ == nullptr) {
            throw std::out_of_range("min_value called on empty tree");
        }
        Node* current = root_;
        while (current->left != nullptr) {
            current = current->left;
        }
        return current->value;
    }

    int max_value() const {
        if (root_ == nullptr) {
            throw std::out_of_range("max_value called on empty tree");
        }
        Node* current = root_;
        while (current->right != nullptr) {
            current = current->right;
        }
        return current->value;
    }

private:
    Node* root_;
    std::size_t size_;

    Node* insert_node(Node* node, int value) {
        if (node == nullptr) {
            ++size_;
            return new Node{value, nullptr, nullptr};
        }
        if (value < node->value) {
            node->left = insert_node(node->left, value);
        } else if (value > node->value) {
            node->right = insert_node(node->right, value);
        }
        return node;
    }

    bool contains_node(Node* node, int value) const {
        if (node == nullptr) {
            return false;
        }
        if (value == node->value) {
            return true;
        }
        return value < node->value
            ? contains_node(node->left, value)
            : contains_node(node->right, value);
    }

    void in_order_node(Node* node, std::vector<int>& result) const {
        if (node == nullptr) {
            return;
        }
        in_order_node(node->left, result);
        result.push_back(node->value);
        in_order_node(node->right, result);
    }

    void destroy(Node* node) {
        if (node == nullptr) {
            return;
        }
        destroy(node->left);
        destroy(node->right);
        delete node;
    }
};

bool test_insert_and_in_order() {
    BinarySearchTree tree;
    for (int v : {5, 3, 8, 2, 4, 7, 9}) {
        tree.insert(v);
    }
    return tree.in_order() == std::vector<int>{2, 3, 4, 5, 7, 8, 9};
}

bool test_contains() {
    BinarySearchTree tree;
    for (int v : {5, 3, 8}) {
        tree.insert(v);
    }
    return tree.contains(3) && !tree.contains(100);
}

bool test_min_max_basic() {
    BinarySearchTree tree;
    for (int v : {5, 3, 8, 2, 4, 7, 9}) {
        tree.insert(v);
    }
    return tree.min_value() == 2 && tree.max_value() == 9;
}

bool test_min_max_single_node() {
    BinarySearchTree tree;
    tree.insert(42);
    return tree.min_value() == 42 && tree.max_value() == 42;
}

bool test_min_max_empty_throws() {
    BinarySearchTree tree;
    bool min_threw = false;
    bool max_threw = false;
    try {
        tree.min_value();
    } catch (const std::out_of_range&) {
        min_threw = true;
    }
    try {
        tree.max_value();
    } catch (const std::out_of_range&) {
        max_threw = true;
    }
    return min_threw && max_threw;
}

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"insert_and_in_order", test_insert_and_in_order},
        {"contains", test_contains},
        {"min_max_basic", test_min_max_basic},
        {"min_max_single_node", test_min_max_single_node},
        {"min_max_empty_throws", test_min_max_empty_throws}
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
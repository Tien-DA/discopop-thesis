#include <algorithm>
#include <cstddef>
#include <iostream>
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

    // BUG: height of an empty subtree (nullptr) should be -1 by convention,
    // but this returns 0, shifting every height in the tree by +1.
    int height() const {
        return height_node(root_);
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

    int height_node(Node* node) const {
        if (node == nullptr) {
            return 0;
        }
        return 1 + std::max(height_node(node->left), height_node(node->right));
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

bool test_height_empty() {
    BinarySearchTree tree;
    return tree.height() == -1;
}

bool test_height_single_node() {
    BinarySearchTree tree;
    tree.insert(42);
    return tree.height() == 0;
}

bool test_height_two_levels() {
    BinarySearchTree tree;
    for (int v : {5, 3, 8}) {
        tree.insert(v);
    }
    return tree.height() == 1;
}

bool test_height_unbalanced() {
    BinarySearchTree tree;
    for (int v : {1, 2, 3, 4, 5}) {
        tree.insert(v);
    }
    return tree.height() == 4;
}

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"insert_and_in_order", test_insert_and_in_order},
        {"contains", test_contains},
        {"height_empty", test_height_empty},
        {"height_single_node", test_height_single_node},
        {"height_two_levels", test_height_two_levels},
        {"height_unbalanced", test_height_unbalanced}
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
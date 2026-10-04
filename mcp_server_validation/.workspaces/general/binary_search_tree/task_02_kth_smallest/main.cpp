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

    bool remove(int value) {
        bool removed = false;
        root_ = remove_node(root_, value, removed);
        return removed;
    }

    std::vector<int> in_order() const {
        std::vector<int> result;
        in_order_node(root_, result);
        return result;
    }

    int height() const {
        return height_node(root_);
    }

    std::size_t size() const {
        return size_;
    }

    // TODO: not implemented. See benchmark.json for the required behavior.
    int kth_smallest(int k) const {
        (void)k;
        throw std::out_of_range("kth_smallest not implemented");
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

    Node* remove_node(Node* node, int value, bool& removed) {
        if (node == nullptr) {
            return nullptr;
        }
        if (value < node->value) {
            node->left = remove_node(node->left, value, removed);
        } else if (value > node->value) {
            node->right = remove_node(node->right, value, removed);
        } else {
            removed = true;
            if (node->left == nullptr) {
                Node* right = node->right;
                delete node;
                --size_;
                return right;
            }
            if (node->right == nullptr) {
                Node* left = node->left;
                delete node;
                --size_;
                return left;
            }
            Node* successor = node->right;
            while (successor->left != nullptr) {
                successor = successor->left;
            }
            node->value = successor->value;
            node->right = remove_node(node->right, successor->value, removed);
        }
        return node;
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
            return -1;
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

bool test_remove() {
    BinarySearchTree tree;
    for (int v : {5, 3, 8, 2, 4, 7, 9}) {
        tree.insert(v);
    }
    bool removed = tree.remove(8);
    return removed && tree.in_order() == std::vector<int>{2, 3, 4, 5, 7, 9};
}

bool test_kth_smallest_basic() {
    BinarySearchTree tree;
    for (int v : {5, 3, 8, 2, 4, 7, 9}) {
        tree.insert(v);
    }
    return tree.kth_smallest(1) == 2 &&
           tree.kth_smallest(4) == 5 &&
           tree.kth_smallest(7) == 9;
}

bool test_kth_smallest_single_node() {
    BinarySearchTree tree;
    tree.insert(42);
    return tree.kth_smallest(1) == 42;
}

bool test_kth_smallest_out_of_range() {
    BinarySearchTree tree;
    for (int v : {5, 3, 8}) {
        tree.insert(v);
    }
    bool threw_low = false;
    bool threw_high = false;
    try {
        tree.kth_smallest(0);
    } catch (const std::out_of_range&) {
        threw_low = true;
    }
    try {
        tree.kth_smallest(4);
    } catch (const std::out_of_range&) {
        threw_high = true;
    }
    return threw_low && threw_high;
}

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"insert_and_in_order", test_insert_and_in_order},
        {"remove", test_remove},
        {"kth_smallest_basic", test_kth_smallest_basic},
        {"kth_smallest_single_node", test_kth_smallest_single_node},
        {"kth_smallest_out_of_range", test_kth_smallest_out_of_range}
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
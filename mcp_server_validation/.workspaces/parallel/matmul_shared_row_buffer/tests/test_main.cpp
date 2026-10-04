#include <iostream>

#include "matmul.h"
#include "matrix.h"
#include "pipeline.h"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

bool test_serial_multiply_known_result() {
    Matrix a(2, 3);
    Matrix b(3, 2);
    long long av[2][3] = {{1, 2, 3}, {4, 5, 6}};
    long long bv[3][2] = {{7, 8}, {9, 10}, {11, 12}};
    for (std::size_t i = 0; i < 2; ++i)
        for (std::size_t j = 0; j < 3; ++j) a.at(i, j) = av[i][j];
    for (std::size_t i = 0; i < 3; ++i)
        for (std::size_t j = 0; j < 2; ++j) b.at(i, j) = bv[i][j];
    Matrix c = multiply_serial(a, b);
    return c.at(0, 0) == 58 && c.at(0, 1) == 64 && c.at(1, 0) == 139 && c.at(1, 1) == 154;
}

bool test_transpose_parallel() {
#ifdef _OPENMP
    omp_set_num_threads(8);
#endif
    Matrix a = make_random_matrix(37, 53, /*seed=*/2, /*max_abs=*/100);
    Matrix t = transpose_parallel(a);
    if (t.rows() != a.cols() || t.cols() != a.rows()) return false;
    for (std::size_t i = 0; i < a.rows(); ++i)
        for (std::size_t j = 0; j < a.cols(); ++j)
            if (t.at(j, i) != a.at(i, j)) return false;
    return true;
}

bool test_parallel_multiply_matches_serial_repeated() {
#ifdef _OPENMP
    omp_set_num_threads(8);
#endif
    Matrix a = make_random_matrix(160, 120, /*seed=*/5, /*max_abs=*/50);
    Matrix b = make_random_matrix(120, 140, /*seed=*/6, /*max_abs=*/50);
    Matrix expected = multiply_serial(a, b);
    for (int trial = 0; trial < 10; ++trial) {
        if (!(multiply_parallel(a, b) == expected)) return false;
    }
    return true;
}

bool test_parallel_multiply_non_square_shapes() {
#ifdef _OPENMP
    omp_set_num_threads(8);
#endif
    const std::size_t shapes[][3] = {{1, 1, 1}, {1, 64, 7}, {9, 1, 33}, {70, 33, 2}};
    for (const auto& s : shapes) {
        Matrix a = make_random_matrix(s[0], s[1], /*seed=*/8, /*max_abs=*/20);
        Matrix b = make_random_matrix(s[1], s[2], /*seed=*/9, /*max_abs=*/20);
        if (!(multiply_parallel(a, b) == multiply_serial(a, b))) return false;
    }
    return true;
}

bool test_gram_matrix_matches_serial_and_is_symmetric() {
#ifdef _OPENMP
    omp_set_num_threads(8);
#endif
    Matrix a = make_random_matrix(150, 110, /*seed=*/13, /*max_abs=*/30);

    Matrix at(a.cols(), a.rows());
    for (std::size_t i = 0; i < a.rows(); ++i)
        for (std::size_t j = 0; j < a.cols(); ++j) at.at(j, i) = a.at(i, j);
    Matrix expected = multiply_serial(a, at);

    for (int trial = 0; trial < 5; ++trial) {
        Matrix gram = compute_gram_matrix(a);
        if (!(gram == expected)) return false;
        for (std::size_t i = 0; i < gram.rows(); ++i)
            for (std::size_t j = 0; j < i; ++j)
                if (gram.at(i, j) != gram.at(j, i)) return false;
        if (trace(gram) != trace(expected)) return false;
    }
    return true;
}

}  // namespace

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"serial_multiply_known_result", test_serial_multiply_known_result},
        {"transpose_parallel", test_transpose_parallel},
        {"parallel_multiply_matches_serial_repeated", test_parallel_multiply_matches_serial_repeated},
        {"parallel_multiply_non_square_shapes", test_parallel_multiply_non_square_shapes},
        {"gram_matrix_matches_serial_and_is_symmetric", test_gram_matrix_matches_serial_and_is_symmetric}
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

#include <iostream>

#include "matrix.h"
#include "pipeline.h"

int main() {
    Matrix a = make_random_matrix(48, 40, /*seed=*/21, /*max_abs=*/9);
    Matrix gram = compute_gram_matrix(a);

    std::cout << "gram size: " << gram.rows() << " x " << gram.cols() << std::endl;
    std::cout << "gram trace: " << trace(gram) << std::endl;
    return 0;
}

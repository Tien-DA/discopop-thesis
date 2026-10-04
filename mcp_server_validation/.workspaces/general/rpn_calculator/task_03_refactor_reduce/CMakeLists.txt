cmake_minimum_required(VERSION 3.16)
project(rpn_refactor_reduce LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(rpn_calculator main.cpp)

target_compile_options(rpn_calculator PRIVATE
    -Wall
    -Wextra
    -Wpedantic
    -O2
)

enable_testing()
add_test(NAME rpn_calculator_tests COMMAND rpn_calculator)
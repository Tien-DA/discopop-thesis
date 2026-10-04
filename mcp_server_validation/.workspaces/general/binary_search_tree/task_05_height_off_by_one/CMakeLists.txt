cmake_minimum_required(VERSION 3.16)
project(bst_height_off_by_one LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(bst main.cpp)

target_compile_options(bst PRIVATE
    -Wall
    -Wextra
    -Wpedantic
    -O2
)

enable_testing()
add_test(NAME bst_tests COMMAND bst)
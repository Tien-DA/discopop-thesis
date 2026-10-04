cmake_minimum_required(VERSION 3.16)
project(bst_remove_dead_code LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(bst main.cpp)

target_compile_options(bst PRIVATE
    -Wall
    -Wextra
    -Wpedantic
    -Werror
    -O2
)

enable_testing()
add_test(NAME bst_tests COMMAND bst)
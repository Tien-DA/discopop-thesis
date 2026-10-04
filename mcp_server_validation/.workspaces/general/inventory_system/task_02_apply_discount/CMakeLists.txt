cmake_minimum_required(VERSION 3.16)
project(inventory_apply_discount LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_executable(inventory main.c)

target_compile_options(inventory PRIVATE
    -Wall
    -Wextra
    -Wpedantic
    -O2
)

enable_testing()
add_test(NAME inventory_tests COMMAND inventory)
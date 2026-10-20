COMPILER ?= g++
FLAGS ?= -std=c++17 -O0 -g -fopenmp
LIBS ?=
SOURCES = src/cpp_qsomp5.cpp src/common/ompscrCommon.cpp src/common/wtime.cpp
RUN_ARGS = 10000 4 100

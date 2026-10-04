CXX ?= g++
CXXFLAGS := -std=c++17 -Wall -Wextra -Wpedantic -O2 -fopenmp -Iinclude
LDFLAGS := -fopenmp

SRC_DIR := src
TEST_DIR := tests
BUILD_DIR := build

LIB_SOURCES := $(SRC_DIR)/iteration_map.cpp $(SRC_DIR)/mandelbrot.cpp $(SRC_DIR)/render.cpp
LIB_OBJECTS := $(patsubst $(SRC_DIR)/%.cpp,$(BUILD_DIR)/%.o,$(LIB_SOURCES))

MAIN_OBJECT := $(BUILD_DIR)/main.o
TEST_OBJECT := $(BUILD_DIR)/test_main.o

APP_BIN := $(BUILD_DIR)/app
TEST_BIN := $(BUILD_DIR)/run_tests

.PHONY: all test clean check_openmp

all: $(APP_BIN)

$(APP_BIN): $(LIB_OBJECTS) $(MAIN_OBJECT)
	$(CXX) $(LDFLAGS) -o $@ $(LIB_OBJECTS) $(MAIN_OBJECT)

test: check_openmp $(TEST_BIN)
	timeout 120 ./$(TEST_BIN)

check_openmp:
	@grep -Eq '^[[:space:]]*#pragma omp' $(SRC_DIR)/mandelbrot.cpp || { echo '[FAIL] src/mandelbrot.cpp no longer contains any OpenMP pragma'; exit 1; }

$(TEST_BIN): $(LIB_OBJECTS) $(TEST_OBJECT)
	$(CXX) $(LDFLAGS) -o $@ $(LIB_OBJECTS) $(TEST_OBJECT)

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR)/test_main.o: $(TEST_DIR)/test_main.cpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

clean:
	rm -rf $(BUILD_DIR)

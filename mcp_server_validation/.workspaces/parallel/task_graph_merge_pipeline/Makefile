CXX ?= g++
CXXFLAGS := -std=c++17 -Wall -Wextra -Wpedantic -O2 -fopenmp -Iinclude
LDFLAGS := -fopenmp
MAKEFLAGS += -j$(shell nproc 2>/dev/null || echo 2)

SRC_DIR := src
TEST_DIR := tests
BUILD_DIR := build

LIB_SOURCES := $(filter-out $(SRC_DIR)/main.cpp,$(wildcard $(SRC_DIR)/*.cpp))
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
	timeout 300 ./$(TEST_BIN)

# Every file must still contain at least as many OpenMP pragmas as the
# original project (see tests/pragma_baseline.txt): the parallel loops have
# to be repaired, not removed.
check_openmp:
	@sh tests/check_pragmas.sh

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

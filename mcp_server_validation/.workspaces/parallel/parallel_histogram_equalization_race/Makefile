CXX ?= g++
CXXFLAGS := -std=c++17 -Wall -Wextra -Wpedantic -O2 -fopenmp -Iinclude
LDFLAGS := -fopenmp

SRC_DIR := src
TEST_DIR := tests
BUILD_DIR := build

LIB_SOURCES := $(SRC_DIR)/matrix.cpp $(SRC_DIR)/histogram.cpp $(SRC_DIR)/pipeline.cpp
LIB_OBJECTS := $(patsubst $(SRC_DIR)/%.cpp,$(BUILD_DIR)/%.o,$(LIB_SOURCES))

MAIN_OBJECT := $(BUILD_DIR)/main.o
TEST_OBJECT := $(BUILD_DIR)/test_main.o

PIPELINE_BIN := $(BUILD_DIR)/pipeline
TEST_BIN := $(BUILD_DIR)/run_tests

.PHONY: all test clean

all: $(PIPELINE_BIN)

$(PIPELINE_BIN): $(LIB_OBJECTS) $(MAIN_OBJECT)
	$(CXX) $(LDFLAGS) -o $@ $(LIB_OBJECTS) $(MAIN_OBJECT)

test: $(TEST_BIN)
	./$(TEST_BIN)

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
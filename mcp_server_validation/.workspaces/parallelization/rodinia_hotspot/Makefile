CXX ?= c++
OMP_FLAGS ?= $(shell if [ "$$(uname)" = Darwin ]; then echo "-Xpreprocessor -fopenmp -I/usr/local/opt/libomp/include -L/usr/local/opt/libomp/lib -lomp"; else echo "-fopenmp"; fi)
all: build/hotspot
build/hotspot: src/hotspot.cpp
	@mkdir -p build
	$(CXX) -O3 $(OMP_FLAGS) $< -o $@
test: all
	bash tests/test_parallelization.sh
clean:
	rm -rf build

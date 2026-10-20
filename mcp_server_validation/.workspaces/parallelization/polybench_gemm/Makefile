.PHONY: all test clean

CC ?= cc
CFLAGS ?= -O3 -std=c11 -fopenmp -DMEDIUM_DATASET

all: build/gemm

build/gemm: src/gemm.c src/gemm.h src/polybench.c src/polybench.h
	@mkdir -p build
	$(CC) $(CFLAGS) -Isrc src/gemm.c src/polybench.c -lm -o $@

test: all
	bash tests/test_parallelization.sh

clean:
	rm -rf build

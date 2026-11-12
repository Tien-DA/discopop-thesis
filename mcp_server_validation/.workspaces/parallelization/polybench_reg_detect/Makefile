.PHONY: all test clean
CC ?= cc
OMP_FLAGS ?= $(shell if [ "$$(uname)" = Darwin ]; then echo "-Xpreprocessor -fopenmp -I/usr/local/opt/libomp/include -L/usr/local/opt/libomp/lib -lomp"; else echo "-fopenmp"; fi)
CFLAGS ?= -O3 -std=c11 -D_POSIX_C_SOURCE=200112L -DSMALL_DATASET $(OMP_FLAGS)
all: build/reg_detect
build/reg_detect: src/reg_detect.c src/reg_detect.h src/polybench.c src/polybench.h
	@mkdir -p build
	$(CC) $(CFLAGS) -Isrc src/reg_detect.c src/polybench.c -lm -o $@
test: all
	bash tests/test_parallelization.sh
clean:
	rm -rf build

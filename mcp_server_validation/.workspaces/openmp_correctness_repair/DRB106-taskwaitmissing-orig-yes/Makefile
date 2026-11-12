ifeq ($(origin CC), default)
CC := clang
endif
CC ?= clang
CFLAGS ?= -std=c11 -O0 -g -fopenmp=libomp
SOURCE := $(firstword $(wildcard src/*.c))

.PHONY: all test clean

all: build/app

build/app: $(SOURCE)
	mkdir -p build
	$(CC) $(CFLAGS) $< -o $@

test:
	CC=$(CC) bash tests/test_race.sh "$(SOURCE)" tests/expected.out

clean:
	rm -rf build

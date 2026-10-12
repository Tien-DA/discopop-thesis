CC ?= gcc
CFLAGS ?= -std=c11 -O0 -g -fopenmp
SOURCE := $(firstword $(wildcard src/*.c))

.PHONY: all test clean

all: build/app

build/app: $(SOURCE)
	mkdir -p build
	$(CC) $(CFLAGS) $< -o $@

test:
	CC=$(CC) tests/test_race.sh "$(SOURCE)" tests/expected.out

clean:
	rm -rf build

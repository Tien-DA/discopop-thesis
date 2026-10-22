CC ?= gcc
CFLAGS ?= -std=c11 -O0 -g -fopenmp
SOURCE := src/DRB183-atomic3-yes.c
REFERENCE := tests/reference/DRB182-atomic3-no.c

.PHONY: all test clean

all: build/app

build/app: $(SOURCE)
	mkdir -p build
	$(CC) $(CFLAGS) $< -o $@

test:
	CC=$(CC) bash tests/test_race.sh "$(SOURCE)" "$(REFERENCE)"

clean:
	rm -rf build

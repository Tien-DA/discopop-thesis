CC ?= gcc
CFLAGS ?= -std=c11 -O0 -g -fopenmp
SOURCE := src/DRB111-linearmissing-orig-yes.c
REFERENCE := tests/reference/DRB112-linear-orig-no.c

.PHONY: all test clean

all: build/app

build/app: $(SOURCE)
	mkdir -p build
	$(CC) $(CFLAGS) $< -o $@

test:
	CC=$(CC) bash tests/test_race.sh "$(SOURCE)" "$(REFERENCE)"

clean:
	rm -rf build

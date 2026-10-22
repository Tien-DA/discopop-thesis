CC ?= gcc
CFLAGS ?= -std=c11 -O0 -g -fopenmp
SOURCE := src/DRB140-reduction-barrier-orig-yes.c
REFERENCE := tests/reference/DRB141-reduction-barrier-orig-no.c

.PHONY: all test clean

all: build/app

build/app: $(SOURCE)
	mkdir -p build
	$(CC) $(CFLAGS) $< -o $@

test:
	CC=$(CC) bash tests/test_race.sh "$(SOURCE)" "$(REFERENCE)"

clean:
	rm -rf build

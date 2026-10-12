COMPILER ?= gcc
FLAGS ?= -std=c11 -O0 -g -fopenmp
LIBS ?= -lm
SOURCES = src/c_md.c src/common/ompscrCommon.c src/common/wtime.c
RUN_ARGS = 100 5

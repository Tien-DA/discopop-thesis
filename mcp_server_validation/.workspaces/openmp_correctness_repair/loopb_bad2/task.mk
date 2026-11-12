COMPILER ?= $(if $(CC),$(CC),clang)
FLAGS ?= -std=c11 -O0 -g -fopenmp=libomp
LIBS ?= -lm
SOURCES = src/c_loopB.badSolution2.c src/common/ompscrCommon.c src/common/wtime.c
RUN_ARGS = 1000 20

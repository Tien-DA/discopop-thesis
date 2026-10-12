COMPILER ?= gcc
FLAGS ?= -std=c11 -O0 -g -fopenmp
LIBS ?= -lm
SOURCES = src/c_testPath.c src/AStack.c src/tg.c src/common/ompscrCommon.c src/common/wtime.c
RUN_ARGS = 1 29 src/GraphExamples/exampleGraph_01.gph

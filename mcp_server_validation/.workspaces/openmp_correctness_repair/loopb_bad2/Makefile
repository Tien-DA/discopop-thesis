include task.mk

.PHONY: all test clean

all: build/app

build/app: $(SOURCES)
	mkdir -p build
	$(COMPILER) $(FLAGS) -Isrc/include -Isrc/common $(SOURCES) -o $@ $(LIBS)

build/tsan-app: $(SOURCES)
	mkdir -p build
	$(COMPILER) $(FLAGS) -fsanitize=thread -Isrc/include -Isrc/common $(SOURCES) -o $@ $(LIBS)

test:
	bash tests/test_race.sh $(RUN_ARGS)

clean:
	rm -rf build

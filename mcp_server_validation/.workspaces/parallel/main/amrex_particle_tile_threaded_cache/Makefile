.PHONY: all test clean

UPSTREAM_TEST_DIR := Tests/Particles/Redistribute

all:
	$(MAKE) -C $(UPSTREAM_TEST_DIR) USE_MPI=FALSE USE_OMP=TRUE BL_NO_FORT=TRUE

test:
	tests/test_upstream_race.sh

clean:
	$(MAKE) -C $(UPSTREAM_TEST_DIR) BL_NO_FORT=TRUE clean

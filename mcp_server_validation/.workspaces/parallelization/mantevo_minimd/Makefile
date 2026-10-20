.PHONY: all test clean

# Keep mpicxx as the compiler driver so it supplies mpi.h and MPI link flags.
# DiscoPoP sets OMPI_CXX/MPICH_CXX for this command in its generated script.
MINIMD_CXX := mpicxx

all:
	$(MAKE) -C src -f Makefile.default copy CC=$(MINIMD_CXX) LINK=$(MINIMD_CXX)

test: all
	bash tests/test_parallelization.sh

clean:
	$(MAKE) -C src -f Makefile.default clean
	rm -f src/miniMD

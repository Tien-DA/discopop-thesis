# Official OmpSCR reference

The `loopb_bad2` task retains the race-positive
`applications/c_LoopsWithDependencies/c_loopB.badSolution2.c` program.
Its hidden reference is the author's
[`c_loopB.pipelineSolution.c`](https://sourceforge.net/projects/ompscr/files/OmpSCR/OmpSCR%20Full%20Distribution%20v2.0/OmpSCR_v2.0.tar.gz/download)
from the official OmpSCR v2.0 SourceForge release. The release also supplies
`debug_V.c`, which exposes the final vector without modifying either program.
The test builds both with `-DDEBUG`, compares the final vectors for one, two,
and four workers, and checks the candidate with ThreadSanitizer. This reference
represents the published pipeline solution for the intended dependency loop;
it is a different parallelization strategy, not a minimal patch to the faulty
source. The hidden reference also includes byte-for-byte copies of the
release's common library and headers, so its behavior does not depend on
agent-editable support files.

The downloaded release archive has SHA-256
`7a0d77596f4dc1a0043284ba9674e34d7de34457ea39aee70565dee305ecb705`.
The copied source and debug helper have SHA-256
`25a936898d546d8ce45aee2a9614eec9f8cffaeaf54109ad3ed31f90c0364324`
and `721272fff1eebb8c2e8b0f13575333138a43829779a69a3ae78db585baaa4b6a`,
respectively. Both files were verified byte-for-byte against the release.

The official v2.0 release contains no corresponding corrected C/C++ source
for `c_testPath`, `c_md`, `cpp_qsomp1`, or `cpp_qsomp5`. Those four tasks
were replaced by official LLNL DataRaceBench pairs documented in
[DATARACEBENCH_REFERENCES.md](DATARACEBENCH_REFERENCES.md). This reduces
application-level coverage; restoring it requires independently published
race-positive/race-free application pairs.

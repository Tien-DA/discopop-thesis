# Official DataRaceBench references

The fourteen race-positive C sources and their fourteen race-free references in this
benchmark are byte-for-byte copies of `micro-benchmarks/` at the official LLNL DataRaceBench tag
[`v1.4.1`](https://github.com/LLNL/dataracebench/tree/v1.4.1/micro-benchmarks),
commit `7d07c5d637fa80f1fd7c239bdc34ae53094badc2`. Their individual
`provenance.json` files identify both upstream files. The `-yes` source is the
agent's task; the paired `-no` source is hidden in `tests/reference/` and used
by the evaluator. Five original tasks without a matching official repair were
replaced with five tasks that have one. DataRaceBench is a race detection suite,
so each pair was checked for equivalent computation and output before use.

| Race-positive task | Official race-free reference | Relationship and oracle use |
| --- | --- | --- |
| `DRB013` | [`DRB104-nowait-barrier-orig-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB104-nowait-barrier-orig-no.c) | Same array computation and output, with the missing barrier restored. The oracle compares complete output. |
| `DRB027` | [`DRB072-taskdep1-orig-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB072-taskdep1-orig-no.c) | Same two writes to `i`, ordered with task dependencies. The reference asserts `i == 2`; the oracle now requires `i=2`. The reference itself has no output to compare. |
| `DRB095` | [`DRB096-doall2-taskloop-collapse-orig-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB096-doall2-taskloop-collapse-orig-no.c) | Same two-dimensional update and output; `collapse(2)` privatizes the inner loop index. |
| `DRB106` | [`DRB105-taskwait-orig-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB105-taskwait-orig-no.c) | Same Fibonacci function with the wait before reading child results. The published program uses input 30; a test-only driver calls its unchanged `fib` function with input 10 to match the task. The oracle compares the result. |
| `DRB109` | [`DRB110-ordered-orig-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB110-ordered-orig-no.c) | Same counter loop and output, with the missing `ordered` region restored. The oracle compares complete output. |
| `DRB111` | [`DRB112-linear-orig-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB112-linear-orig-no.c) | Same numerical loop and output; the `linear` clause privatizes the index. |
| `DRB119` | [`DRB118-nestlock-orig-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB118-nestlock-orig-no.c) | Same nested-lock program and output, with locking restored inside `incr_b`. The oracle compares complete output. |
| `DRB136` | [`DRB135-taskdep-mutexinoutset-orig-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB135-taskdep-mutexinoutset-orig-no.c) | Same task graph and output; `mutexinoutset` serializes conflicting updates. |
| `DRB140` | [`DRB141-reduction-barrier-orig-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB141-reduction-barrier-orig-no.c) | Same reduction and output; a barrier orders initialization before reduction. |
| `DRB173` | [`DRB174-non-sibling-taskdep-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB174-non-sibling-taskdep-no.c) | Same nested task graph and output; `taskwait` orders the child tasks. |
| `DRB183` | [`DRB182-atomic3-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB182-atomic3-no.c) | Same producer/consumer signal; the official version uses an atomic write to match the atomic read. |
| `DRB193` | [`DRB192-critical-section3-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB192-critical-section3-no.c) | Same signal protocol; both sections use the same critical region. |
| `DRB195` | [`DRB194-diffusion1-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB194-diffusion1-no.c) | Same stencil; the official version swaps two distinct buffers after each step. |
| `DRB201` | [`DRB200-sync1-no.c`](https://github.com/LLNL/dataracebench/blob/v1.4.1/micro-benchmarks/DRB200-sync1-no.c) | Same two-thread state update; the official version acquires the lock before the first write, ordering both writes. |

The official `-no` files are copied unchanged under each task's hidden
`tests/reference/` directory. SHA-256 hashes in table order:

```text
ccffe05219970451d558c8a40b7379f329e18066811bad7133c7bc3d7cc5cbfa
70b2b792c9e956bd3a3f6527ef53700a3b556ada6c01b57ab0a87c9878036ec5
7d14c5b444dc10ea5a88115918e12836f900f30d34319de053d9b153bcb5690b
feb1d1c9b9a18eb513c72129824aba27881533b2dafda1e9e694ec64b3b873d7
36e6ee8f6c68ae31fb177f8c8a500bebce7437ba7837959f3644222c33a0c949
cc7e5becfb1beaf424db46b4d4b0ba81a9b9344dabe554c5f15216d3f94dafb1
a230c1b1c391163b033df8b646bb2c6ff814552713ca1f94e235b5112a60441c
28162e8d568f3d52993a64146190c32a6fc51562dadf30190f97424a99735a50
4e331f955ac1568439d1855b7c4d5ee939da8f4d1d1e83475446990dec57dfae
d97f2b1e28eb6f6b8a4ec19dccabfaf2f579efe091177cf92acf85f7924c3167
f652733d5555ba0f40e3ae9ef4b1961854a12f89caa16421335d749b73a5e1fa
4a06be76755643a69b23c194746f445a48b3dec550eab8279f98d5fef69fdf40
fee630b5be72d8cc92737f4800feaa294cfe62e50847d4625cef84a290d3b85e
bcd80e4109a287b09d51d5c4499b570db0e7e657c072b75b7ae29b7a1a2300cd
```

The five newly added tasks compare complete output at one, two, and four workers
with their official reference and check the candidate with ThreadSanitizer.
`DRB027` uses the official reference's assertion because that program has no
output. `DRB106` uses a test-only driver to match its input size.
Four more official pairs replace OmpSCR programs for which no published repair
was found. Their oracles compare complete output under one-, two-, and
four-worker settings and check the candidate with ThreadSanitizer. The
`DRB183`, `DRB193`, and `DRB201` programs explicitly request two threads, so
those settings do not change their team size.

# Benchmark tasks

The benchmark currently contains 20 tasks. Each task runs in `direct`,
`full_discopop`, and `mcp` modes. Correctness tasks require a race-free,
functionally correct repair that preserves OpenMP parallel work. Performance
tasks also record task-specific runtime measurements.

## OpenMP correctness repair

### DataRaceBench

| Task name | Fault to repair |
| --- | --- |
| `drb009_lastprivate_missing` | Missing `lastprivate` |
| `drb011_unprotected_decrement` | Unprotected decrement |
| `drb013_missing_barrier` | Missing synchronization barrier |
| `drb021_missing_reduction` | Missing reduction |
| `drb023_parallel_sections` | Race in parallel sections |
| `drb027_missing_task_dependency` | Missing task dependency |
| `drb073_missing_inner_private` | Missing private inner-loop state |
| `drb106_missing_taskwait` | Missing task wait |
| `drb109_missing_ordered` | Missing ordered synchronization |
| `drb119_missing_nested_lock` | Missing nested lock |

### OmpSCR applications

| Task name | Program |
| --- | --- |
| `ompscr_graph_search` | Graph search |
| `ompscr_loopa_bad` | Dependency loop A |
| `ompscr_loopb_bad1` | Dependency loop B, variant 1 |
| `ompscr_loopb_bad2` | Dependency loop B, variant 2 |
| `ompscr_molecular_dynamic` | Molecular dynamics |
| `ompscr_qsomp1` | Parallel quicksort, variant 1 |
| `ompscr_qsomp2` | Parallel quicksort, variant 2 |
| `ompscr_qsomp5` | Parallel quicksort, variant 5 |

## OpenMP parallelization

| Task name | Program |
| --- | --- |
| `mantevo_minimd_openmp_optimization` | Mantevo miniMD; preserve MPI + OpenMP behavior and improve shared-memory execution. |
| `polybench_gemm_openmp` | PolyBench/C GEMM; parallelize the compute kernel while preserving the exact result. |

Task definitions and their build, test, profiling, and optional performance
commands are in `.workspaces/**/benchmark.json`. See [README.md](README.md)
for setup and execution instructions.

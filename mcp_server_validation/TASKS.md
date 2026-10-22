# Benchmark tasks

The benchmark currently contains 17 tasks. Each task runs in `direct`,
`full_discopop`, and `mcp` modes. Correctness tasks require a race-free,
functionally correct repair that preserves OpenMP parallel work. Performance
tasks also record task-specific runtime measurements. The 15 race-repair tasks
award a separate performance point after the correctness oracle passes; see
[README.md](README.md#performance-measurements) for the paired-reference policy.

## OpenMP correctness repair

### DataRaceBench

| Task ID in `benchmark.json` | Fault to repair |
| --- | --- |
| `drb013_missing_barrier` | Missing synchronization barrier |
| `drb027_missing_task_dependency` | Missing task dependency |
| `drb095_taskloop_inner_private` | Missing private inner-loop state in a taskloop |
| `drb106_missing_taskwait` | Missing task wait |
| `drb109_missing_ordered` | Missing ordered synchronization |
| `drb111_missing_linear` | Missing `linear` clause for a loop index |
| `drb119_missing_nested_lock` | Missing nested lock |
| `drb136_missing_mutexinoutset` | Missing mutually exclusive task dependency |
| `drb140_reduction_barrier` | Missing barrier before reduction |
| `drb173_non_sibling_task_dependency` | Race between nested non-sibling tasks |
| `drb183_atomic_signal` | Unsynchronized atomic signal write |
| `drb193_critical_signal` | Mismatched named critical sections |
| `drb195_diffusion_alias` | Aliased diffusion buffers |
| `drb201_lock_order` | Incorrect lock ordering for shared state |

### OmpSCR application

| Task ID in `benchmark.json` | Program |
| --- | --- |
| `ompscr_loopb_bad2` | Dependency loop B, variant 2 |

## OpenMP parallelization

| Task ID in `benchmark.json` | Program |
| --- | --- |
| `mantevo_minimd_openmp_optimization` | Mantevo miniMD; preserve MPI + OpenMP behavior and improve shared-memory execution. |
| `polybench_gemm_openmp` | PolyBench/C GEMM; parallelize the compute kernel while preserving the exact result. |

Task definitions and their build, test, profiling, and optional performance
commands are in `.workspaces/**/benchmark.json`. See [README.md](README.md)
for setup and execution instructions.

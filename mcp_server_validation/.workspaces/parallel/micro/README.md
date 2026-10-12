# DataRaceBench repair tasks

These ten CPU/OpenMP repair tasks vendor source files unchanged from
[DataRaceBench v1.4.1](https://github.com/LLNL/dataracebench/releases/tag/v1.4.1),
commit `7d07c5d637fa80f1fd7c239bdc34ae53094badc2`. Each selected source has the
published ground truth `data race = yes`.

| Task | DataRaceBench source | Published pattern |
| --- | --- | --- |
| `drb009_lastprivate_missing` | DRB009 | Missing `lastprivate` |
| `drb011_unprotected_decrement` | DRB011 | Unprotected decrement |
| `drb013_missing_barrier` | DRB013 | Missing barrier |
| `drb021_missing_reduction` | DRB021 | Missing reduction |
| `drb023_parallel_sections` | DRB023 | Concurrent section writes |
| `drb027_missing_task_dependency` | DRB027 | Missing task dependency |
| `drb073_missing_inner_private` | DRB073 | Missing private loop variable |
| `drb106_missing_taskwait` | DRB106 | Missing taskwait |
| `drb109_missing_ordered` | DRB109 | Missing ordered synchronization |
| `drb119_missing_nested_lock` | DRB119 | Missing nested lock |

Every task contains the upstream license and a `provenance.json` file. Its
`make test` command compiles the candidate with OpenMP and ThreadSanitizer,
runs it with four workers, rejects a reported data race, and checks the task's
documented output invariant.

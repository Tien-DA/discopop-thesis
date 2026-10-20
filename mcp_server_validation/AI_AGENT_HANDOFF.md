# Handoff prompt for the DiscoPoP MCP benchmark thesis

Use this document as the starting context when working on this repository. Read the named source files before changing behavior. Do not assume that older README files describe the current benchmark runner.

## Project goal

This repository is the DiscoPoP project. DiscoPoP analyzes C and C++ programs and helps identify parallelism, dependencies, correctness risks, and performance opportunities.

The thesis work in this repository asks a focused question:

> Does giving a coding agent access to DiscoPoP through an MCP server help it repair real OpenMP correctness problems better than source-code reasoning alone?

The benchmark compares the same coding agent and the same task in three conditions:

1. `direct`: the agent sees only the repository source and normal shell tools.
2. `full_discopop`: the runner runs DiscoPoP before the agent starts; generated analysis is available in `.discopop`.
3. `mcp`: the agent must initialize and use the DiscoPoP MCP server itself. The prompt requires meaningful MCP evidence before editing and validation after editing.

The coding agent is OpenCode. The self-hosted university model is `Qwen/Qwen3.8-27B`, exposed through `http://localhost:18000/v1` on the Linux benchmark machine.

## Important directories

| Path | Meaning |
| --- | --- |
| `mcp_server/` | DiscoPoP MCP server implementation. |
| `mcp_server/server.py` | MCP stdio server, tool registration, tool-set selection, daemon/proxy modes, argument handling. |
| `mcp_server/tools/core/` | Main agent-facing workflows. |
| `mcp_server/tools/low_level/` | More detailed diagnostic tools, available only with `--tools all`. |
| `mcp_server_validation/` | Benchmark runner and benchmark tasks used in the thesis. |
| `mcp_server_validation/benchmark_runner.py` | CLI entry point. Run it through `./run` from this directory. |
| `mcp_server_validation/benchmark/` | Loader, selector, prompts, runner, evaluator, batch runner, and case types. |
| `mcp_server_validation/llm/opencode.py` | Writes a temporary OpenCode configuration, starts OpenCode, captures JSON events, token use, and MCP calls. |
| `mcp_server_validation/discopop/runner.py` | Runs DiscoPoP in the `full_discopop` condition. |
| `mcp_server_validation/.workspaces/openmp_correctness_repair/` | OpenMP bug-repair tasks, divided into `micro`, `meso`, and `main`. |
| `mcp_server_validation/.workspaces/parallelization/` | Reserved for future tasks that add or improve parallelism. |
| `mcp_server_validation/runs/` | Generated benchmark output. Do not treat it as source data. |

## DiscoPoP MCP server

The package entry point is `discopop_mcp_server`, defined by `mcp_server/pyproject.toml` and implemented by `mcp_server.server:main`.

The server normally runs over MCP stdio. It can also run as a local daemon and be accessed by a proxy. Its default tool set is deliberately small because every exposed tool schema costs model context.

### Default tools

| Tool | Use it for |
| --- | --- |
| `prepare_project_analysis` | Create or update the DiscoPoP project configuration. It is the normal first call for a fresh repository. |
| `gather_data` | Build and execute with DiscoPoP instrumentation and collect analysis data. |
| `triage_parallel_failure` | Decide whether a failure depends on worker count and narrow down the likely cause. |
| `assess_parallel_region` | Inspect a suspected OpenMP region and return a repair-oriented assessment. |
| `validate_parallel_behavior` | Compare one-worker and multi-worker behavior after a repair. |
| `evaluate_parallel_performance` | Measure speed and scaling after correctness is stable. |
| `run_auto_tuning` | Explore safe tuning choices after data collection. |
| `manage_patches` | Inspect or apply bounded patch operations related to the workflow. |

### Tools enabled only with `--tools all`

| Tool | Use it for |
| --- | --- |
| `compare_threaded_executions` | Direct comparison of executions with different thread counts. |
| `diagnose_parallel_correctness` | Lower-level correctness diagnosis. |
| `trace_symbol_slice` | Trace a focused slice around a symbol when higher-level evidence is not enough. |

The server instructions explicitly tell agents not to read `.discopop` files directly. MCP tools should provide compact evidence. A normal repair workflow is:

1. Prepare the project and gather data if data does not exist.
2. Establish whether the behavior changes with worker count.
3. Assess the relevant parallel region.
4. Edit the source.
5. Build and validate one-worker versus multi-worker behavior.
6. Measure performance only after correctness is stable.

Do not count “MCP enabled” as MCP use. `OpenCodeClient` counts actual MCP tool-use events in OpenCode's JSON event stream.

## Benchmark runner

`benchmark_runner.py` loads every `benchmark.json` recursively below `.workspaces`. The current tree has 19 tasks:

- 10 `micro` tasks
- 8 `meso` tasks
- 1 `main` task

`benchmark/loader.py` turns each `benchmark.json` into a `BenchmarkCase`. Each case must provide:

```json
{
  "task": "What the coding agent must repair",
  "build_command": "make all",
  "test_command": "make test",
  "profiling_command": "command used by DiscoPoP"
}
```

`benchmark/runner.py` runs every selected case in `direct`, `full_discopop`, and `mcp` modes. For each mode it:

1. Copies the task into a separate workspace under `runs/.../<mode>/workspace`.
2. Excludes `build`, `tests`, `.discopop`, `.git`, and Python cache files from the agent copy.
3. Runs DiscoPoP only in `full_discopop`. In `mcp`, OpenCode calls the MCP server itself.
4. Writes the mode prompt and temporary `opencode.json`.
5. Starts OpenCode and saves `events.jsonl` plus token and MCP-use data.
6. Evaluates the agent's changed source in a separate evaluation workspace.
7. Restores the original task's lowercase `tests/` directory only in that evaluation workspace.
8. Saves build result, test result, generated patch, event log, and final result JSON.

If the first attempt fails, the runner gives the same OpenCode session one remediation turn with limited evaluator diagnostics. `MAX_SESSION_TURNS` is currently 2.

### Hidden-test rule

Only a directory named lowercase `tests/` is hidden and restored. This convention is mandatory for evaluator-only files such as test scripts, fixed test revisions, expected outputs, and upstream patches.

Do not place hidden material elsewhere. The AMReX task stores its public upstream test under `upstream_test/` because macOS treats `Tests` and `tests` as the same directory while Linux does not.

### OpenCode and model configuration

`mcp_server_validation/llm/opencode.py` creates `opencode.json` in the isolated workspace. It uses the `@ai-sdk/openai-compatible` provider, provider name `HPC_Lab`, base URL `http://localhost:18000/v1`, and model `Qwen/Qwen3.8-27B`.

Do not restore the old `LLMClient` preflight request to `/v1/responses`. The university server returns `404` for that endpoint. OpenCode is the actual agent and must be allowed to make requests through its own compatible provider configuration.

`mcp_server_validation/config.json` records the same model and tunnel information, but the active CLI values are currently in `benchmark_runner.py` and `OpenCodeClient`.

## Benchmark data

All current tasks target OpenMP correctness. They must preserve real parallel work; a repair that removes OpenMP or serializes the task is not acceptable.

### Micro tier: DataRaceBench

Location: `mcp_server_validation/.workspaces/openmp_correctness_repair/micro/`

There are 10 C11 race-positive DataRaceBench v1.4.1 tasks:

- DRB009 lastprivate missing
- DRB011 unprotected decrement
- DRB013 missing barrier
- DRB021 missing reduction
- DRB023 parallel sections
- DRB027 missing task dependency
- DRB073 missing inner private
- DRB106 missing taskwait
- DRB109 missing ordered
- DRB119 missing nested lock

The source is copied from LLNL DataRaceBench tag `v1.4.1`, commit `7d07c5d637fa80f1fd7c239bdc34ae53094badc2`. Each task has `provenance.json`, an upstream license, a small build adapter, and hidden tests using ThreadSanitizer plus expected output where available.

These are small, controlled OpenMP examples. They are suitable for basic correctness coverage but do not prove that DiscoPoP helps with large, multi-file code.

### Meso tier: OmpSCR

Location: `mcp_server_validation/.workspaces/openmp_correctness_repair/meso/`

There are 8 OmpSCR v2.0 tasks from upstream commit `d277761f6fdc22cfcb52893385cbb802d592d729`:

- `loopa_bad`
- `loopb_bad1`
- `loopb_bad2`
- `molecular_dynamic`
- `graph_search`
- `qsomp1`
- `qsomp2`
- `qsomp5`

These are larger than micro tasks and include project code, shared OmpSCR runtime files, original licensing, and build adapters. Their hidden test scripts currently build with ThreadSanitizer and reject removal of OpenMP pragmas.

The meso tests need Linux validation before they are used for thesis results. Their race oracle is weaker than the main task's provenance because it is based on the benchmark source and the local harness rather than an upstream bug-fix commit.

### Main tier: real bug from Git history

Location: `mcp_server_validation/.workspaces/openmp_correctness_repair/main/amrex_particle_tile_threaded_cache/`

This is the strongest current task. It comes from AMReX, a real C++ HPC project using OpenMP.

| Item | Value |
| --- | --- |
| Project | AMReX, `https://github.com/AMReX-Codes/amrex` |
| Buggy commit | `b5e000952a0190f94320bb3f6549cdf7e0d8c895` |
| Fix commit | `6f2c4aff90ae3b8a5df8877008de4bc21a71b00b` |
| Upstream fix | PR #5404: `Fix for race condition when using getConstParticleTileData in threaded region.` |
| Buggy file | `Src/Particle/AMReX_ParticleTile.H` |
| Upstream test | `Tests/Particles/Redistribute/main.cpp` |

The workspace contains an archived source snapshot from the buggy commit, selected AMReX build files, the public upstream test tree under `upstream_test/`, and original license files. It also has local benchmark files:

- root `Makefile`: normalizes commands to `make all`, `make test`, and `make clean`;
- `benchmark.json`: the agent-facing task description and commands;
- `provenance.json`: commits, URL, hashes, source path, test path, and snapshot method;
- lowercase `tests/main.cpp.fixed`: the exact upstream test version from the fix commit;
- lowercase `tests/upstream-fix.patch`: the exact upstream Git diff;
- lowercase `tests/test_upstream_race.sh`: evaluator harness that restores the fixed upstream test, builds with OpenMP and ThreadSanitizer, and fails on a race report.

The lower-case `tests/` directory is intentionally hidden from the coding agent. It is not source code that the agent should edit.

The AMReX task was checked for source and test hashes, patch applicability, JSON validity, shell syntax, and `make -n all`. It has not been run end-to-end on the macOS development machine because that machine lacks a usable OpenMP runtime. Validate it on the Linux benchmark machine before reporting a result.

## Running the benchmark

On the Linux machine:

```bash
cd ~/TU_Darmstadt/6.Semester/Thesis/discopop-thesis/mcp_server_validation
source ../venv/bin/activate
./run
```

Choose one task first. The current recommended order is micro, then meso, then main. Do not run `all` until a representative task from each tier builds and tests successfully.

For each run, inspect:

- `runs/<timestamp>_<tier>_<task>/result.json`
- one directory per mode: `direct`, `full_discopop`, `mcp`
- `events.jsonl` for real OpenCode and MCP calls
- `evaluation.json` for build and hidden-test outcome
- `patch.diff` for the agent's source change

## Required Linux environment

The benchmark needs:

- the thesis virtual environment with `discopop_mcp_server` installed;
- an `opencode` CLI executable on `PATH`;
- an active tunnel from `localhost:18000` to the university model server;
- a C/C++ compiler with OpenMP support;
- a ThreadSanitizer setup that works with the selected OpenMP runtime;
- DiscoPoP and its LLVM-related dependencies installed in the environment used by the runner.

The macOS development machine is useful for file and metadata checks, but it is not the reference environment for OpenMP or ThreadSanitizer execution.

## Current limits and work still needed

1. Validate one micro, one meso, and the AMReX main task end-to-end on Linux before treating the suite as runnable evidence.
2. Improve meso functional oracles so they check more than a ThreadSanitizer report and the presence of OpenMP pragmas.
3. Mine and validate more real Git-history tasks for the main tier. Do not invent races or patches. Each new main task must record the project URL, buggy commit, fixed commit, exact source/test hashes, license, and an upstream test or a reproducible upstream behavior.
4. Keep benchmark cases comparable: same agent, model, maximum turns, compiler family, hardware, OpenMP thread policy, and evaluation commands across modes.
5. Keep generated `runs/`, build directories, `.discopop/`, event logs, and agent temporary configuration out of versioned source unless intentionally archived as experimental evidence.

## Rules for future changes

- Preserve upstream source and licenses. Add wrappers and metadata around it; do not silently rewrite an upstream task.
- Store provenance in every imported task. Provenance is evidence for the thesis; it is not executed by the runner.
- Keep evaluator-only files under lowercase `tests/`.
- Do not allow a repair to pass by removing OpenMP, serializing the algorithm, or changing the hidden test.
- Do not claim that a task passes dynamically unless it was run on the Linux OpenMP environment.
- When changing the runner, test the three conditions separately and preserve isolation between their workspaces.
- When changing MCP tools, keep default tool schemas focused. Expose low-level tools only when a task needs them.

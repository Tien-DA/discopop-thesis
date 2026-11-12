# DiscoPoP MCP benchmark

This directory benchmarks an OpenCode coding agent on the same OpenMP-repair
task in four conditions:

| Mode | What the agent can use |
| --- | --- |
| `direct` | Source tree and normal shell tools. |
| `full_discopop` | Source tree plus DiscoPoP analysis generated before the agent starts. |
| `mcp` | Source tree plus the enabled DiscoPoP MCP server; the agent may use it when useful. |
| `force_mcp` | Same MCP runtime, with required DiscoPoP setup and analysis, followed by encouraged use of the remaining tools. |

`mcp` measures voluntary tool adoption. `force_mcp` changes only the prompt's
`BENCHMARK CONDITION`: it requires MCP tools to set up DiscoPoP and generate
analysis, then asks the agent to make an effort to use the remaining tools to
complete the task. Tool selection and subsequent steps follow tool descriptions
and returned evidence, without prescribing tool names. Server configuration, workspace isolation, evaluation,
token accounting, and timing are identical. The runner does not execute tools
on the agent's behalf or add a separate compliance gate to the correctness score;
tool calls and their results remain visible in the recorded events.

The runner keeps the agent workspace and evaluator workspace separate. Files in a
task's lowercase `tests/` directory are copied only into the evaluator workspace,
so an agent cannot modify the oracle. Each mode writes its prompt, OpenCode event
stream, evaluation result, patch, and summary under `runs/`.

For the fourteen DataRaceBench repair tasks, see
[official reference provenance](DATARACEBENCH_REFERENCES.md) for the verified
race-free upstream programs. The OmpSCR dependency-loop reference is documented
in [OmpSCR reference provenance](OMPSCR_REFERENCES.md).

## Supported environment

Run a complete benchmark on **Linux x86_64** (native Linux, a VM, or WSL2). The
15 correctness-repair oracles use **Clang + LLVM libomp + Archer + ThreadSanitizer**.
macOS is useful for Python unit tests and inspection; the full oracle requires Linux.

Use Python 3.10–3.13, a recent Node.js LTS release, the LLVM race-checking toolchain,
and an LLVM/Clang development package supported by the DiscoPoP profiler (19–22).
On Ubuntu/Debian, install the host prerequisites before creating the Python
environment:

```bash
sudo apt update
sudo apt install -y \
  build-essential gcc g++ make cmake git \
  python3 python3-venv python3-dev \
  llvm-19 llvm-19-dev clang-19 libomp-19-dev libclang-rt-19-dev libboost-all-dev
```

Use matching Clang, libomp, Archer and compiler-rt versions. For LLVM 19:

```bash
export CC=clang-19
export COMPILER=clang-19
export ARCHER_LIBRARY=/usr/lib/llvm-19/lib/libarcher.so
test -f "$ARCHER_LIBRARY"
python3 -B tests/test_repair_validation.py ReferenceOracleTests -v
```

Run the Python command from `mcp_server_validation`. If your distribution supplies
another LLVM version supported by DiscoPoP, use that version consistently.
The task Makefiles default to `clang`; explicit `CC` selects a versioned compiler.
`COMPILER` is the OmpSCR build override. The helper locates Archer next to the
selected Clang's resource directory when `ARCHER_LIBRARY` is unset.

Every correctness oracle performs a toolchain self-check first: the binary must
load libomp (not libgomp), Archer must activate, a synchronized task probe must
pass, and a deliberately racy probe must emit a TSan race and exit 66. Failure
is reported as `[Archer setup] ERROR`, not evidence that a reference is wrong.
Archer is explicitly enabled via `OMP_TOOL_LIBRARIES`; its verbose output is
restricted to the self-check so it cannot contaminate candidate stdout or the
OmpSCR vector on stderr. TSan uses `ignore_noninstrumented_modules=1` as
[recommended by Archer](https://openmp.llvm.org/doxygen/dir_d25e7fcf0ab543d5b35a958546f34a9d.html),
with `halt_on_error=1` and `exitcode=66`. The oracle sets its analysis options
explicitly rather than inheriting suppressions or disabled analysis.

The shared `benchmark/validation/archer.sh` is linked from each hidden `tests/archer.sh`.
Workspace copying dereferences the links, so detached evaluation workspaces
contain a standalone copy. Original candidate/reference output checks remain
in each task's `test_race.sh` for tasks without `expected.out`. For the five
tasks with `expected.out`, benchmark correctness checks only the candidate
against that file: no official reference is compiled or run during `make test`.
Reference files remain available for the separate reference-validation suite
and paired performance measurements. Reference validation prints diagnostics directly
and removes its isolated workspace after each task.
For the five tasks with `tests/expected.out`, it also checks the unsanitized
reference stdout against that file for each 1/2/4-thread control. Matching uses
the oracle's `grep -E` regular expressions (or `__EMPTY__`), not literal text
equality. A mismatch fails reference validation even if the oracle passes.
The DRB027 stdout adapter and DRB106 input adapter apply to these checks too;
the terminal prints both adaptations and each expected-output check explicitly.
For the other ten tasks, the nine DRB oracles compare stdout with the reference
using the same printed result format as the starting task. OmpSCR compiles both
programs with `-DDEBUG` and the common hidden `debug_V.c` printer, then compares
the final vector on stderr; stdout headers and timing are excluded.

GCC/G++ packages are still needed by other task families and may provide the
C++ standard library used by the DiscoPoP instrumenting compiler. The 15 repair
performance measurements now default to Clang/libomp too, without TSan or Archer;
do not compare their timings directly to earlier GCC/libgomp runs.

If a DiscoPoP build fails with `cannot find -lstdc++` even though `clang-22`
is installed, point the instrumenting compiler at a complete GCC installation.
The benchmark uses `DISCOPOP_GCC_INSTALL_DIR` rather than `CFLAGS`, so each
task retains the compilation flags defined by its own Makefile:

```bash
export DISCOPOP_GCC_INSTALL_DIR=/usr/lib/gcc/x86_64-linux-gnu/15
test -f "$DISCOPOP_GCC_INSTALL_DIR/libstdc++.so"
```

## Install from a fresh clone

Run these commands at repository root. The requirements file installs the local
DiscoPoP profiler, library, explorer, hotspot detector, and MCP server. The
profiler build produces `discopop_cc` and `discopop_cxx`; it can take several
minutes and requires the LLVM packages above.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r mcp_server_validation/requirements.txt
```

Install and configure OpenCode 2 for the provider and model you want. The
benchmark uses that existing setup and the `opencode run --format json --auto`
interface:

```bash
npm install -g opencode-ai
opencode --version
```

OpenCode 1 uses a different CLI (`--variant`, `--dir`) and is not supported by this runner.
The OpenCode project documents installation and command-line
interface at [its official documentation](https://docs.opencode.ai/docs/).

Confirm the local tools before spending model tokens:

```bash
.venv/bin/discopop_cc --help >/dev/null
.venv/bin/discopop_explorer --help >/dev/null
.venv/bin/discopop_mcp_server --help >/dev/null
opencode --version
clang-19 --version
```

## Configure OpenCode

Set your provider, server, credentials, and model in OpenCode before running
the benchmark. The benchmark does not accept provider, server, API key, or
base-model settings. It reads the model most recently selected in OpenCode's
TUI and passes it to every benchmark run with `--model`. Select a model with
`/models` in OpenCode before starting the benchmark. The provider and
credentials remain under OpenCode's control.

Each run writes a temporary project-level `opencode.json` containing only the
DiscoPoP MCP setting for that benchmark mode. It removes the file when the agent
finishes. Your OpenCode provider, model, credentials, and other settings remain
under OpenCode's control.

The benchmark prints the selected agent, requested variant, and OpenCode's most
recently selected provider, model, and variant once at the start. It reads that
selection from OpenCode's model state once and uses it for all four modes. The
printed provider, model, and variant come from that saved selection, except when
`--reasoning-effort` or `--variant` explicitly overrides the variant. It asks OpenCode for the
selected provider's endpoint when available, and leaves credentials under
OpenCode's control without reading or printing secrets. Each mode omits these
repeated configuration lines.

## Run DRB095

DRB095 is included in the clone at:

`mcp_server_validation/.workspaces/openmp_correctness_repair/DRB095-doall2-taskloop-orig-yes/`

From this directory, list available task names and run only this case:

```bash
cd mcp_server_validation
../.venv/bin/python benchmark_runner.py --list
../.venv/bin/python benchmark_runner.py --case DRB095-doall2-taskloop-orig-yes
```

`--case` accepts the directory name printed by `--list`; the descriptive ID
in `benchmark.json` is metadata.

`./run --case DRB095-doall2-taskloop-orig-yes` is equivalent when the intended virtual
environment is activated. Without `--case`, the runner opens an interactive task
selector; choose `all` only after individual tasks work in your environment.

## Choose the coding agent

`--agent opencode` (default) drives `opencode`; `--agent claude` drives the
Claude Code CLI (`claude -p --output-format stream-json`) instead. Both use your
own existing, already authenticated setup, and both produce the same result
files. `BENCHMARK_AGENT` sets the default for a shell session.

```bash
./run --agent claude --case DRB095-doall2-taskloop-orig-yes
./run --agent claude --claude-model haiku --case DRB095-doall2-taskloop-orig-yes
```

For `claude`, the model defaults to your Claude Code default; select another with
`--claude-model` (an alias such as `sonnet`, `opus` or `haiku`, or a full model
name), or set `BENCHMARK_CLAUDE_MODEL` for a shell session. The MCP server is passed
with `--strict-mcp-config`, so your own MCP servers never reach a run, and
`--reasoning-effort` maps to `--effort` (`off` omits the flag). Claude Code does
not report reasoning tokens separately, so those are recorded as 0.

## Control reasoning effort and view commands

Use `--help` to show all runner options and examples. It works before the
DiscoPoP Python packages are installed.

```bash
./run --help
```

For Claude Code, `--reasoning-effort` controls the `--effort` argument.
`--variant` is an alias for this flag. The Claude default is `medium`; set
`BENCHMARK_REASONING_EFFORT` to change it for a shell session.

For OpenCode 2, the same flag selects a variant of OpenCode's last selected
model for that run. For example, if you last selected `openai/gpt-6.1-sol`,
`--reasoning-effort low` launches `opencode run --model
openai/gpt-6.1-sol#low`. The benchmark reads the model from OpenCode; it does
not configure a provider or model in the benchmark workspace. Without the flag,
it reuses the variant saved for that model in OpenCode. If no named variant was
saved, it passes the model without a variant suffix. `off` maps to OpenCode's `none` variant.
OpenCode decides whether the selected model supports the requested variant.

```bash
# OpenCode with a low reasoning variant
./run --case DRB095-doall2-taskloop-orig-yes --reasoning-effort low


# Faster, lower-cost DRB095 run
./run --agent claude --case DRB095-doall2-taskloop-orig-yes --reasoning-effort low

# Disable thinking traces for the fastest mode supported by the model
./run --agent claude --case DRB095-doall2-taskloop-orig-yes --variant off

# Maximum reasoning depth for a difficult task
./run --agent claude --case DRB095-doall2-taskloop-orig-yes --reasoning-effort xhigh
```

Claude accepts `max`, `xhigh`, `high`, `medium`, `low`, and `off`. OpenCode also
accepts custom variant names defined for its selected model. The selected
value and resulting command are printed in the benchmark log.

The source starts with the known race. A successful agent repair must keep the
OpenMP taskloop, build with `make all`, and pass the evaluator's
Archer/ThreadSanitizer and official-reference output checks with one, two, and four
worker threads. Do not expect
the unmodified source to pass `make test`.

## Results and troubleshooting

One invocation produces:

```text
runs/<timestamp>_openmp_correctness_repair_DRB095-doall2-taskloop-orig-yes/
  result.json
  direct/{workspace,evaluation_workspace,evaluation.json,events.jsonl,patch.diff,result.json}
  full_discopop/{...}
  mcp/{...}
  force_mcp/{...}
```

Read `result.json` for the four-mode summary. `evaluation.json` contains the
compiler/test outcome, `patch.diff` is the source change proposed by the agent,
and `events.jsonl` records OpenCode events used to count tokens and MCP calls.

Each MCP condition has one result row, `mcp` or `force_mcp`, in individual and
batch summaries. Its
token totals include every agent step, including initial DiscoPoP setup and
analysis tool calls. `agent_latency_seconds` includes all agent invocations
and their tool execution; `latency_seconds` (the summary's Latency column)
also includes the evaluator runs between invocation start and final evaluation.
Setup costs are not subtracted. Results do not contain separate cold/warm
measurements or `warm_usage`, `warm_latency_seconds`, or `tokens.warm` fields.

## Performance measurements

Correctness and performance are reported separately. A task may declare an
optional `performance_command` in `benchmark.json`. The command runs only after
the candidate passes build, tests, and any `validator`; its exit status never
changes the task's correctness result. This lets a benchmark report a regression
or an unavailable measurement without treating it as a failed repair.

The command must write one JSON object to standard output with
`"schema_version": 1`. The runner stores the object in both
`evaluation.json` and the mode's `result.json`, and prints its measurements and
comparisons. Hidden task specifications select workloads and trusted references;
the shared evaluator tools perform the measurements. The runner transports and
displays the versioned report, so future task families can use the same interface.

The basic report shape is:

```json
{
  "schema_version": 1,
  "metric": "wall_time_seconds",
  "unit": "seconds",
  "repetitions": 3,
  "measurements": [
    {"label": "reference", "workers": 4, "samples": [1.02, 1.00, 1.01], "median": 1.01},
    {"label": "candidate", "workers": 4, "samples": [0.82, 0.81, 0.83], "median": 0.82}
  ],
  "comparisons": [
    {
      "label": "candidate_vs_reference_4_workers",
      "numerator": "reference_4_workers",
      "denominator": "candidate_4_workers",
      "ratio": 1.23,
      "direction": "higher_is_faster"
    }
  ]
}
```

During evaluator execution, `BENCHMARK_REFERENCE_WORKSPACE` points to a clean
copy of the original task source. It is never copied into the agent workspace.
A task may use this workspace as an upstream baseline, or keep a task-specific
correct reference under its hidden `tests/` directory. Performance scripts must
write only the JSON report to stdout; diagnostic output belongs on stderr.

### Parallelization tasks: controlled paired measurements

All 32 parallelization tasks delegate to `benchmark/performance/performance_parallel.py`
through `BENCHMARK_PARALLEL_PERFORMANCE_TOOL`, set by the evaluator. Their hidden
`tests/performance.json` specifies sources and bounded workload candidates.
The evaluator freshly compiles candidate and reference with the same compiler
and `-O3`/OpenMP flags, bypassing candidate Makefiles, environment `CFLAGS`, and
previous build artifacts. miniMD uses `MPICXX` (default `mpicxx`) and a fixed source
list and compile flags. Source/header changes needed by the task are retained;
PolyBench's support code, dimension header, and instrumentation come from the
hidden reference. Actual compiler version, build commands, and workload dimensions
are recorded in JSON.

Each task measures two workloads: the original small configuration and a larger
reference-calibrated configuration. Calibration tries a bounded list until the
reference kernel (PolyBench) or process (other programs) reaches approximately
100 ms. If it cannot reach the target within that list, the report explicitly
flags `target_reached: false`. PolyBench candidates in the list have an estimated
array-memory cap of 256 MiB; this is not an OS memory limit. The first successful
calibration writes `parallel_performance_plan.json` beside the mode directories,
and all four modes reuse that exact workload. Delete the complete run directory
when starting a fresh experiment on another machine or toolchain.

Before timing each workload, candidate output with 1 and 4 workers is compared
against the reference at that workload. PolyBench streams the real formatted array
dump from stderr through Python SHA-256 and checks its byte count in separate
validation binaries. This does not intercept `fprintf`, so glibc fortified stdio
can operate normally. The dump is buffered and never retained in full in memory.
Hotspot compares output
file SHA-256 hashes; miniMD compares thermodynamic values with the existing
`1e-7` tolerance. This supplements the task's original correctness gate. A failure
makes the performance report unavailable, without rewriting correctness PASS.

Every configuration gets two untimed process warmups. Fifteen paired rounds
follow; each round runs every configuration in seeded randomized order. A round
averages up to 20 separate invocations, calibrated from reference process latency
toward 100 ms. Each speedup is the **median of per-round paired ratios**, with a
95% percentile-bootstrap interval (2,000 resamples of paired rounds). This can
differ from dividing the displayed measurement medians. `above_one`, `below_one`,
or `inconclusive` indicates where the interval lies relative to 1; it is not a
separate performance score. Intervals describe within-run sampling uncertainty,
not all bias or variation between machines and complete benchmark sessions.

The three original comparisons remain: candidate 1 worker versus serial,
candidate 4 workers versus serial, and candidate scaling from 1 to 4 workers.
miniMD retains its four comparisons against its already-parallel upstream code.
All tasks report `end_to_end_wall_time_seconds`, including process launch and
OpenMP/MPI startup. PolyBench additionally reports `kernel_wall_time_seconds`
using an evaluator-owned `CLOCK_MONOTONIC` timer around its instrumentation region,
with cache flushing disabled. Warmups do not preserve an OpenMP team between
process launches. miniMD and Hotspot have no trusted kernel timer in this harness;
their application-reported times are not presented as kernel measurements.

`workloads[].metrics[]` contains both workload reports and their raw samples.
The top-level metric/measurements/comparisons mirror the larger workload's
end-to-end report for existing consumers. The console displays two compact tables:
median times in milliseconds and paired speedups with 95% intervals, for every
workload and metric. `Program` means the complete process; `Kernel` means only
the timed computational region. `t` means threads; `?` marks an interval containing
1 (inconclusive), even when rounded bounds appear equal to 1. The headline is the
performance workload's Program speedup at 4 threads versus its reference. Runtime
probe details are shown only when unexpected; calibration warnings remain visible.
Full-precision values, raw samples, round order, and build metadata remain in
`evaluation.json` and `result.json`; terminal formatting does not change scoring.

The runtime fixes `OMP_DYNAMIC=FALSE`, worker limits, `OMP_PLACES=cores`, and
`OMP_PROC_BIND=close`, and verifies that a separate OpenMP probe can create 1 and
4 threads. This probe does not prove how many threads execute a candidate kernel.
miniMD also confirms the thread count in its output. On Linux, when `taskset` is
available, processes use the same four allowed CPUs, preferring distinct physical
cores when Linux topology information permits; the CPU set is recorded.
Open MPI's default per-rank core binding is disabled to permit OpenMP
workers. CPU frequency, thermal state, SMT, system load, and launcher overhead
remain environmental factors: use a quiet dedicated host and repeat complete runs
before comparing modes. The procedure follows the warmup/repetition principles in
[Google Benchmark](https://google.github.io/benchmark/user_guide.html) and noise
controls discussed by [LLVM](https://llvm.org/docs/Benchmarking.html).

### Self-checking parallelization correctness oracles

`tests/test_parallel_validation.py` exercises the existing task oracles in
temporary workspaces. It covers all 30 PolyBench kernels, Rodinia Hotspot, and
miniMD, without an agent, DiscoPoP, or performance timing. The single file contains
the shared runner and family-specific controls; it does not modify task oracles,
inputs, or reference fixtures.

The 32 task entry points share `benchmark/validation/parallel_validation.py` through
task-local `tests/parallel_validation.py` symlinks. Hidden-test workspace copies
dereference these links, so each evaluation gets a standalone, evaluator-owned
helper. Preserve the links or copy their target when transferring tasks.

Each PolyBench task has an explicit dependency-aware OpenMP control derived from
the hidden serial reference. Hotspot parallelizes independent grid chunks;
miniMD uses the pristine upstream application as its positive control. After
acceptance, the suite checks serial candidates, consistently wrong numerical
output, errors restricted to four threads, missing output, compilation failure,
and runtime failure. PolyBench and Hotspot also reject unused and called empty
parallel regions, disabled regions (`if(0)`), and single-thread regions.
miniMD additionally checks wrong thread reporting and
non-finite thermodynamic values. Numerical mutation is intentional and isolated
to temporary candidates; a positive control is not a performance recommendation.
Numerical rejection must reach the oracle's output comparison; a compilation
error in a numerical control is a self-test failure, not a successful rejection.
The full native integration suite can take several minutes.

```bash
python3 -B tests/test_parallel_validation.py -v
# Select one family or one kernel:
python3 -B tests/test_parallel_validation.py PolyBenchValidationTests -v
python3 -B tests/test_parallel_validation.py HotspotValidationTests -v
python3 -B tests/test_parallel_validation.py MiniMDValidationTests -v
python3 -B tests/test_parallel_validation.py PolyBenchValidationTests.test_polybench_gesummv -v
# Run the oracle-gap regressions separately:
python3 -B tests/test_parallel_validation.py OracleGapTests -v
# Portable infrastructure checks, without native compilation or MPI:
python3 -B tests/test_parallel_validation.py OracleSupportTests -v
```

`OracleGapTests` retains regressions for previously identified gaps: unused
OpenMP regions outside the kernel, miniMD results that are wrong identically at
both thread counts, and a hanging PolyBench candidate. The hanging control uses
a one-second execution limit, separate build limits, and a larger outer watchdog;
it must return the oracle's timeout status (124), not exhaust the self-test limit.

Each oracle first checks the unmodified candidate output at one and four workers
against its trusted reference. miniMD builds its frozen reference in a temporary
directory; `tests/reference/PROVENANCE.txt` identifies the baseline commit.
Thermodynamic comparisons require timesteps 0 and 10 and all four named fields,
finite values, and `abs(candidate-reference) <= 1e-7 + 1e-7 * abs(reference)`.

A separate diagnostic build records distinct OpenMP team workers executing
nonempty innermost loops in `kernel_*` functions (PolyBench), `single_iteration`
(Hotspot), and Lennard-Jones force computation functions (miniMD). At least one
loop site must be executed by multiple workers in active parallel teams; the
diagnostic output must also match the reference. Enclosing nests remain intact
for `collapse(n)`. This uses compiler/OpenMP facilities already required by the
tasks, without an OMPT dependency or a speedup threshold. Unsupported source
syntax fails explicitly. The instrumentation is designed for the benchmark's
loop-based kernels, not arbitrary C/C++ rewrites or adversarial code. It does not
prove race freedom, useful speedup, or correctness beyond the checked inputs and
formatted-output precision.

Execution limits default to 30 seconds per invocation and 240 seconds per build;
override them with `PARALLEL_VALIDATION_TIMEOUT` and
`PARALLEL_VALIDATION_BUILD_TIMEOUT`. The evaluator also bounds each shell command
to 900 seconds (`BENCHMARK_COMMAND_TIMEOUT`). Timeout handling terminates process
groups, allows a short cleanup grace period for nested oracles, then escalates
to SIGKILL. All limits must be finite and positive.

Linux is recommended for complete coverage. Missing OpenMP/MPI toolchains are
reported as SKIP. miniMD requires `mpicxx` and a working `mpirun`. Failures include the
task/control name and captured output. All temporary build/run files are removed.

### Correctness-repair tasks: reference preservation

All 15 race-repair tasks now use a hidden `tests/performance.json` specification
and the shared performance test. It runs only after the correctness oracle
passes. The test builds the candidate and official race-free reference with
the same Clang `-O2 -fopenmp=libomp` flags, without ThreadSanitizer. It warms up both
programs, calibrates a batch to about 150 ms, and runs nine paired rounds in
alternating order. Each pair uses the same input and OpenMP team size. The
reported ratio is the median of the nine reference-time/candidate-time
ratios; a larger value means a faster candidate. The report includes raw
samples and a paired-bootstrap 95% interval.

The performance point is **1** when the interval's lower bound is at least
`0.90`, **0** when its upper bound is below `0.90`, and **inconclusive**
otherwise. The point is also stored as `performance_point` in each mode's
`result.json`; it is `null` when correctness fails or timing is
inconclusive. `0.90` means at least 90% of the reference's throughput, or a
candidate runtime no greater than about 111% of the reference runtime.
This 90% margin is a benchmark policy, not a universal threshold from the
literature. [Google Benchmark's methodology](https://github.com/google/benchmark/blob/main/docs/user_guide.md)
supports warmup, timed batches, repetition, and statistical reporting;
[LLVM's benchmarking guidance](https://llvm.org/docs/Benchmarking.html)
also recommends repeated runs to recognize noise. The use of an uncertainty
interval follows the statistical evaluation principles of
[Georges, Buytaert, and Eeckhout](https://dri.es/files/oopsla07-georges.pdf).

These race-repair programs include very small
[DataRaceBench microbenchmarks](https://github.com/LLNL/dataracebench).
Their score measures complete process latency, including OpenMP startup and
process overhead; it does not isolate kernel throughput or prove scaling.
An inconclusive result should be rerun on a quieter dedicated Linux host.
The parallelization tasks report performance observations and uncertainty
without a pass/fail threshold.

If a mode fails before the agent runs, check these prerequisites in this order:

1. The selected `opencode` (version 2) or `claude` command is on `PATH`.
2. The selected agent is authenticated and has a usable model configured.
3. `discopop_cc`, `discopop_explorer`, and `discopop_mcp_server` come from the same `.venv` used for the runner.
4. Clang/libomp/Archer passes both self-check probes on Linux (set `CC` and `ARCHER_LIBRARY` as above).
5. The profiler sees a supported Clang/LLVM installation (versions 19–22).

`runs/`, `build/`, `.discopop/`, and temporary `opencode.json` files are generated
artifacts and are intentionally ignored by Git.

### Claude finishes without MCP calls

`MCP enabled: True` means the runner configured a server; it does not prove
that Claude connected to it. Interactive Claude may also use a different MCP
configuration: the benchmark uses `--strict-mcp-config` and starts its own
stdio server using `DISCOPOP_MCP_COMMAND`, `DISCOPOP_MCP_SERVER`, `PATH`, the
runner's Python environment, or the source fallback, in that order.

The Claude client prints the server's initial status, advertised DiscoPoP
tools, tool-call names, and a final diagnosis. Each `llm_result.json` stores
`mcp_availability`; the mode result stores these reports under
`mcp.availability_by_invocation`:

- `available_but_not_called`: init reported connected and advertised DiscoPoP
  tools, but no MCP call was observed. The prompt deliberately leaves tool
  use optional; inspect the transcript to understand the agent's approach.
- `server_unavailable_at_init`: init reported failed, needs-auth, or disabled.
  Check the selected executable/environment and captured stderr.
- `availability_unconfirmed`: init was missing, the server was pending or
  unreported, or no DiscoPoP tools were advertised. This is inconclusive,
  because connections and deferred discovery can complete after init.
- `tool_calls_observed`: MCP tool-use events were recorded. This does not
  establish that the tools themselves succeeded; inspect their results.

The [Claude MCP documentation](https://code.claude.com/docs/en/agent-sdk/mcp)
describes init status, tool discovery, and connection timing. These reports
do not force calls or change the benchmark's correctness score. A passing
task with an unavailable server should not be interpreted as a successful
test of MCP's benefit.

The transcript viewer also supports existing Claude logs (no model call):

```bash
python3 tools/inspect_events.py runs/<run>/mcp/events.jsonl
```

It prints the init-based MCP diagnosis, assistant text, tool inputs, and
tool results. Its MCP diagnosis assumes the log is from the MCP condition.

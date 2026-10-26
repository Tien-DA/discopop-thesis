# DiscoPoP MCP benchmark

This directory benchmarks an OpenCode coding agent on the same OpenMP-repair
task in three conditions:

| Mode | What the agent can use |
| --- | --- |
| `direct` | Source tree and normal shell tools. |
| `full_discopop` | Source tree plus DiscoPoP analysis generated before the agent starts. |
| `mcp` | Source tree plus the enabled DiscoPoP MCP server; the agent may use it when useful. |

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
included DataRaceBench oracles compile with GCC, OpenMP, and GCC ThreadSanitizer. macOS's
`/usr/bin/gcc` is Apple Clang and does not support this command, so it is useful
for inspection but is not a supported execution environment for this benchmark.

Use Python 3.10–3.13, a recent Node.js LTS release, GCC/G++ with OpenMP support,
and an LLVM/Clang development package supported by the DiscoPoP profiler (19–22).
On Ubuntu/Debian, install the host prerequisites before creating the Python
environment:

```bash
sudo apt update
sudo apt install -y \
  build-essential gcc g++ make cmake git \
  python3 python3-venv python3-dev \
  llvm-19-dev clang-19 libomp-19-dev libboost-all-dev
```

The system compiler used by the DataRaceBench tasks is `gcc`; do not set `CC` to
Clang for their evaluators. If your distribution uses versioned compiler
names, set `CC` to a GNU GCC executable, for example `export CC=gcc-13`.

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
gcc --version
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
selection from OpenCode's model state once and uses it for all three modes. The
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
ThreadSanitizer and official-reference output checks with one, two, and four
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
```

Read `result.json` for the three-mode summary. `evaluation.json` contains the
compiler/test outcome, `patch.diff` is the source change proposed by the agent,
and `events.jsonl` records OpenCode events used to count tokens and MCP calls.

## Performance measurements

Correctness and performance are reported separately. A task may declare an
optional `performance_command` in `benchmark.json`. The command runs only after
the candidate passes build, tests, and any `validator`; its exit status never
changes the task's correctness result. This lets a benchmark report a regression
or an unavailable measurement without treating it as a failed repair.

The command must write one JSON object to standard output with
`"schema_version": 1`. The runner stores the object in both
`evaluation.json` and the mode's `result.json`, and prints its measurements and
comparisons. Task scripts own the workload, trusted reference implementation,
and any ratios because those choices are task-specific. The shared runner only
transports and displays the report, so future task families can use the same
interface.

The following shape is recommended:

```json
{
  "schema_version": 1,
  "metric": "wall_time_seconds",
  "unit": "seconds",
  "repetitions": 5,
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

All 15 race-repair tasks now use a hidden `tests/performance.json` specification
and the shared performance test. It runs only after the correctness oracle
passes. The test builds the candidate and official race-free reference with
the same GCC `-O2 -fopenmp` flags, without ThreadSanitizer. It warms up both
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
The included GEMM and miniMD tasks continue to report raw performance
observations without a pass/fail threshold.

If a mode fails before the agent runs, check these prerequisites in this order:

1. The selected `opencode` (version 2) or `claude` command is on `PATH`.
2. The selected agent is authenticated and has a usable model configured.
3. `discopop_cc`, `discopop_explorer`, and `discopop_mcp_server` come from the same `.venv` used for the runner.
4. GCC can compile `-fopenmp -fsanitize=thread` and execute the resulting binary on Linux.
5. The profiler sees a supported Clang/LLVM installation (versions 19–22).

`runs/`, `build/`, `.discopop/`, and temporary `opencode.json` files are generated
artifacts and are intentionally ignored by Git.

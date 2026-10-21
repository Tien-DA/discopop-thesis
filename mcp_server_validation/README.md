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

## Supported environment

Run a complete benchmark on **Linux x86_64** (native Linux, a VM, or WSL2). The
included DRB009 oracle compiles with GCC, OpenMP, and GCC ThreadSanitizer. macOS's
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

The system compiler used by the DataRaceBench task is `gcc`; do not set `CC` to
Clang for the DRB009 evaluator. If your distribution uses versioned compiler
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

Install OpenCode 1, which provides the `opencode run --format json --auto`
interface used by this runner:

```bash
npm install -g opencode-ai
opencode --version
```

OpenCode 2 uses a different CLI and is not interchangeable with this runner.
The OpenCode project documents the OpenCode 1 installation and command-line
interface at [its official documentation](https://docs.opencode.ai/docs/).

Confirm the local tools before spending model tokens:

```bash
.venv/bin/discopop_cc --help >/dev/null
.venv/bin/discopop_explorer --help >/dev/null
.venv/bin/discopop_mcp_server --help >/dev/null
opencode --version
gcc --version
```

## Configure the model endpoint

The benchmark calls an OpenAI-compatible endpoint through OpenCode. Set these
variables for your own accessible model; they apply to every benchmark mode:

```bash
export BENCHMARK_LLM_SERVER_URL="https://your-server.example/v1"
export BENCHMARK_LLM_API_KEY="your-api-key"
export BENCHMARK_LLM_MODEL="provider-model-id"
# Optional. The OpenCode provider label defaults to HPC_Lab.
export BENCHMARK_LLM_PROVIDER="HPC_Lab"
```

`BENCHMARK_LLM_SERVER_URL`, `BENCHMARK_LLM_API_KEY`, and
`BENCHMARK_LLM_MODEL` replace the former lab-specific defaults. The generated
OpenCode configuration never gets committed: it is written only inside a run's
isolated workspace.

## Run DRB009

DRB009 is included in the clone at:

`mcp_server_validation/.workspaces/openmp_correctness_repair/DRB009-lastprivatemissing-orig-yes/`

From this directory, list available task names and run only this case:

```bash
cd mcp_server_validation
../.venv/bin/python benchmark_runner.py --list
../.venv/bin/python benchmark_runner.py --case drb009_lastprivate_missing
```

`./run --case drb009_lastprivate_missing` is equivalent when the intended virtual
environment is activated. Without `--case`, the runner opens an interactive task
selector; choose `all` only after individual tasks work in your environment.

## Control reasoning effort and view commands

Use `--help` to show all runner options and examples. It works before the
DiscoPoP Python packages are installed.

```bash
./run --help
```

`--reasoning-effort` controls the OpenCode `--variant` passed to every agent
invocation in the run. `--variant` is an alias for compatibility with OpenCode's
own terminology. The default is `medium`; set
`BENCHMARK_REASONING_EFFORT` to change that default for a shell session.

```bash
# Faster, lower-cost DRB009 run
./run --case drb009_lastprivate_missing --reasoning-effort low

# Disable thinking traces for the fastest mode supported by the model
./run --case drb009_lastprivate_missing --variant off

# Maximum reasoning depth for a difficult task
./run --case drb009_lastprivate_missing --reasoning-effort xhigh
```

Accepted values are `xhigh`, `high`, `medium`, `low`, and `off`. Higher effort
can improve difficult repairs but costs more tokens and latency. The selected
value is printed at the start of a benchmark and recorded in the OpenCode command
shown in the mode log.

The source starts with the known race. A successful agent repair must keep the
OpenMP parallel loop, build with `make all`, and pass the evaluator's
ThreadSanitizer and output checks with two and four worker threads. Do not expect
the unmodified source to pass `make test`.

## Results and troubleshooting

One invocation produces:

```text
runs/<timestamp>_openmp_correctness_repair_DRB009-lastprivatemissing-orig-yes/
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

The included GEMM and miniMD tasks report raw samples, medians, candidate versus
reference ratios, and one-to-four-worker scaling. These are observations only;
the benchmark intentionally does not yet turn them into a performance score or
a pass/fail threshold.

If a mode fails before the agent runs, check these prerequisites in this order:

1. `opencode` is on `PATH` and is OpenCode 1.
2. The model endpoint, key, model identifier, and provider label are accepted by OpenCode.
3. `discopop_cc`, `discopop_explorer`, and `discopop_mcp_server` come from the same `.venv` used for the runner.
4. GCC can compile `-fopenmp -fsanitize=thread` and execute the resulting binary on Linux.
5. The profiler sees a supported Clang/LLVM installation (versions 19–22).

`runs/`, `build/`, `.discopop/`, and temporary `opencode.json` files are generated
artifacts and are intentionally ignored by Git.

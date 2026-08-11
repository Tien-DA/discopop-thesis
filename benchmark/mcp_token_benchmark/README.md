# DiscoPoP MCP benchmark

The benchmark runs the same task in three modes: source code only, source code plus all selected DiscoPoP output, and source code plus the live DiscoPoP MCP server. It stores real token usage returned by the model provider, final answers, MCP transcript, latency and deterministic correctness checks.

## One-command mode

For a project that has already been analysed by DiscoPoP and therefore contains `.discopop/FileMapping.txt` plus static or dynamic dependency output, install the MCP package once:

```bash
pip install -e /path/to/discopop/mcp_server
```

Then, from the target project's source directory, run:

```bash
mcp_token_benchmark
```

The command discovers the loaded LM Studio model at `http://localhost:1234/v1`, finds mapped source files and all textual DiscoPoP artefacts, derives a dependency question plus oracle from the real DiscoPoP result, and writes the report under `.discopop/mcp_token_benchmark/<timestamp>/`.

It cannot safely run DiscoPoP analysis from arbitrary source alone: the build command, program arguments and representative runtime input are project-specific. If `.discopop` data is absent, first configure and run `gather_static_data` or `gather_data`; the command will stop with this precise prerequisite instead of fabricating output.

## Run

Copy `case.template.json`, replace paths and expected facts with a real, already analysed project, then run:

```bash
python benchmark/mcp_token_benchmark/benchmark.py my-cases.json --model <model-name>
```

The generated `benchmark-results/report.json` is the full reproducibility record; `report.md` is the concise summary. The runner supports any OpenAI-compatible `/v1/responses` server. For the OpenAI cloud, set `OPENAI_API_KEY`; for a local server, pass its URL and, if needed, its local token.

### LM Studio

Start the local server and load a model with native tool support. Then use its OpenAI-compatible endpoint:

```bash
python benchmark/mcp_token_benchmark/benchmark.py my-cases.json \
  --model <LM-STUDIO-MODEL-ID> \
  --base-url http://localhost:1234/v1 \
  --repo-root "$PWD" \
  --output-dir benchmark/mcp_token_benchmark/benchmark-results/local-run
```

No API key is required unless authentication is enabled in LM Studio. If it is enabled, add `--api-key <local-token>`.

For safety, `mcp.allowed_tools` is required and should contain only the read-only tool(s) needed by each task, for example `get_data_dependencies`, `get_static_data_dependencies`, `get_execution_results`, or `get_parallelization_patches`. Do not expose `manage_patches`, `gather_data`, or configuration-writing tools.

`expected.must_contain`/`must_match` check the answer; `expected.tool_calls` checks that MCP was actually used with the intended arguments. Run the local checks with:

```bash
python -m unittest benchmark/mcp_token_benchmark/test_benchmark.py -v
```

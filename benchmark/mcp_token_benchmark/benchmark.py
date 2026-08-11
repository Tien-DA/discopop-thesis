"""Reproducible end-to-end benchmark for DiscoPoP context access."""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import platform
import queue
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Sequence

# ============================================================================
# Configuration
# ============================================================================

SYSTEM_PROMPT = """You are evaluating a DiscoPoP analysis task. Give a concise, evidence-based answer.
Do not alter files or run shell commands. State uncertainty rather than inventing facts."""


# ============================================================================
# File handling
# ============================================================================


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _files(base: Path, patterns: Iterable[str]) -> list[Path]:
    """Return all files matching the given patterns."""
    result: list[Path] = []

    for pattern in patterns:
        matches = [Path(item) for item in glob.glob(str(base / pattern), recursive=True)]

        if not matches:
            raise ValueError(f"No files match pattern '{pattern}'")

        result.extend(path for path in matches if path.is_file())

    return sorted(set(result))


def _file_context(
    base: Path,
    patterns: Iterable[str],
    label: str,
) -> str:
    """Read matching files and combine them into labeled context."""
    chunks: list[str] = []

    for path in _files(base, patterns):
        try:
            display_name = path.relative_to(base)
        except ValueError:
            display_name = path

        content = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        chunks.append(f"\n--- {label}: {display_name} ---\n{content}")

    return "".join(chunks)


def _context_stats(context: str) -> dict[str, int]:
    """Return basic size statistics for a context string."""
    return {
        "characters": len(context),
        "lines": len(context.splitlines()),
        "words": len(context.split()),
    }


# ============================================================================
# Answer scoring
# ============================================================================


def _normalize_text(value: str) -> str:
    """Normalize whitespace and case for text comparison."""
    return " ".join(value.casefold().split())


def _score_answer(
    answer: str,
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Check an answer against the deterministic manifest criteria."""
    normalized = _normalize_text(answer)
    checks: list[dict[str, Any]] = []

    for phrase in expected.get("must_contain", []):
        expected_normalized = _normalize_text(str(phrase))
        passed = expected_normalized in normalized

        checks.append(
            {
                "kind": "must_contain",
                "expected": phrase,
                "passed": passed,
            }
        )

    for pattern in expected.get("must_match", []):
        try:
            passed = bool(re.search(pattern, answer, re.IGNORECASE))
            error = None
        except re.error as exc:
            passed = False
            error = str(exc)

        checks.append(
            {
                "kind": "must_match",
                "expected": pattern,
                "passed": passed,
                **({"error": error} if error else {}),
            }
        )

    for phrase in expected.get("must_not_contain", []):
        expected_normalized = _normalize_text(str(phrase))
        passed = expected_normalized not in normalized

        checks.append(
            {
                "kind": "must_not_contain",
                "expected": phrase,
                "passed": passed,
            }
        )

    if expected.get("require_nonempty", False):
        checks.append(
            {
                "kind": "nonempty",
                "expected": True,
                "passed": bool(normalized),
            }
        )

    passed = all(check["passed"] for check in checks)

    return {
        "passed": passed,
        "checks": checks,
        "num_checks": len(checks),
        "num_passed": sum(check["passed"] for check in checks),
    }


# ============================================================================
# MCP tool-call scoring
# ============================================================================


def _score_tool_calls(
    calls: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check whether all expected MCP calls were made."""
    checks: list[dict[str, Any]] = []

    for wanted in expected:
        expected_name = wanted["name"]
        expected_arguments = wanted.get("arguments", {})

        matching_call = None

        for actual in calls:
            if actual.get("name") != expected_name:
                continue

            actual_arguments = actual.get("arguments", {})

            if all(actual_arguments.get(key) == value for key, value in expected_arguments.items()):
                matching_call = actual
                break

        checks.append(
            {
                "expected": wanted,
                "passed": matching_call is not None,
                "matching_call": matching_call,
            }
        )

    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "actual_call_count": len(calls),
        "expected_call_count": len(expected),
    }


# ============================================================================
# Case validation
# ============================================================================


def _validate_case(case: dict[str, Any]) -> None:
    """Validate the required fields of a benchmark case."""
    case_id = case.get("id", "")

    required = (
        "question",
        "source_paths",
        "discopop_output_paths",
        "mcp",
    )

    for key in required:
        if not case.get(key):
            raise ValueError(f"Case '{case_id}' requires '{key}'")

    expected = case.get("expected", {})

    if not (expected.get("must_contain") or expected.get("must_match")):
        raise ValueError(f"Case '{case_id}' requires deterministic answer checks")

    if not expected.get("tool_calls"):
        raise ValueError(f"Case '{case_id}' requires expected.tool_calls")

    if not case["mcp"].get("allowed_tools"):
        raise ValueError(f"Case '{case_id}' requires mcp.allowed_tools")


# ============================================================================
# MCP client
# ============================================================================


class MCPClient:
    """Minimal JSON-RPC client for an MCP server using stdio."""

    def __init__(
        self,
        command: Sequence[str],
        cwd: str,
        timeout: int,
    ):
        self.command = list(command)
        self.cwd = cwd
        self.timeout = timeout
        self.process: subprocess.Popen[str] | None = None
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.request_id = 0

    def __enter__(self) -> "MCPClient":
        """Start the MCP server and initialize the connection."""
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        assert self.process.stdout is not None

        threading.Thread(
            target=self._read,
            daemon=True,
        ).start()

        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "discopop-mcp-benchmark",
                    "version": "1.0",
                },
            },
        )

        self._send(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )

        return self

    def __exit__(self, *_: object) -> None:
        """Terminate the MCP server process."""
        if not self.process:
            return

        self.process.terminate()

        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def _read(self) -> None:
        """Read MCP responses from stdout."""
        assert self.process
        assert self.process.stdout

        for line in self.process.stdout:
            self.lines.put(line)

        self.lines.put(None)

    def _send(self, message: dict[str, Any]) -> None:
        """Send one JSON-RPC message to the MCP server."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP server is not running")

        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> Any:
        """Send a JSON-RPC request and wait for its response."""
        self.request_id += 1
        request_id = self.request_id

        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )

        while True:
            try:
                line = self.lines.get(timeout=self.timeout)
            except queue.Empty as error:
                raise RuntimeError(f"Timed out waiting for MCP '{method}'") from error

            if line is None:
                raise RuntimeError(f"MCP server exited during '{method}'")

            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue

            if message.get("id") != request_id:
                continue

            if "error" in message:
                raise RuntimeError(json.dumps(message["error"]))

            return message.get("result")

    def tools(self, allowed: set[str]) -> list[dict[str, Any]]:
        """Return the configured MCP tools in Responses API format."""
        response = self.request("tools/list", {})
        available = response.get("tools", [])

        tools = [
            {
                "type": "function",
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get(
                    "inputSchema",
                    {"type": "object", "properties": {}},
                ),
                "strict": False,
            }
            for tool in available
            if tool["name"] in allowed
        ]

        missing = allowed - {tool["name"] for tool in tools}

        if missing:
            raise RuntimeError(f"MCP does not expose configured tool(s): {sorted(missing)}")

        return tools

    def call(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Execute an MCP tool call."""
        return self.request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )


# ============================================================================
# Responses API client
# ============================================================================


class ResponsesClient:
    """Minimal client for an OpenAI-compatible Responses API."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def create(
        self,
        request_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a request to the Responses API."""
        headers = {"Content-Type": "application/json"}

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(
            f"{self.base_url}/responses",
            method="POST",
            data=json.dumps(request_data).encode("utf-8"),
            headers=headers,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=600,
            ) as response:
                return json.loads(response.read().decode("utf-8"))

        except urllib.error.HTTPError as error:
            body = error.read().decode(
                "utf-8",
                errors="replace",
            )
            raise RuntimeError(f"Responses API returned HTTP {error.code}: {body}") from error


# ============================================================================
# Response parsing
# ============================================================================


def _usage(response: dict[str, Any]) -> dict[str, int]:
    """Extract token usage information from an API response."""
    usage = response.get("usage", {}) or {}
    input_details = usage.get("input_tokens_details", {}) or {}
    output_details = usage.get("output_tokens_details", {}) or {}

    return {
        "input_tokens": int(usage.get("input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
        "cached_input_tokens": int(input_details.get("cached_tokens", 0)),
        "reasoning_tokens": int(output_details.get("reasoning_tokens", 0)),
    }


def _answer(response: dict[str, Any]) -> str:
    """Extract the final text answer from an API response."""
    return "\n".join(
        content.get("text", "")
        for item in response.get("output", [])
        if item.get("type") == "message"
        for content in item.get("content", [])
        if content.get("type") in {"output_text", "text"}
    ).strip()


# ============================================================================
# Prompt construction
# ============================================================================


def _prompt(
    question: str,
    context: str,
    use_tools: bool = False,
) -> str:
    """Build the prompt used by one benchmark mode."""
    instruction = " Use the available tools when they are needed to answer correctly." if use_tools else ""

    return f"{SYSTEM_PROMPT}\n\n" f"Task:\n{question}\n\n" f"Context:{context}\n\n" f"Answer the task now.{instruction}"


# ============================================================================
# LLM execution
# ============================================================================


def _run_direct(
    client: ResponsesClient,
    model: str,
    prompt: str,
) -> dict[str, Any]:
    """Run one direct LLM request without MCP tools."""
    started = time.monotonic()

    response = client.create(
        {
            "model": model,
            "input": prompt,
        }
    )

    return {
        "prompt": prompt,
        "answer": _answer(response),
        "usage": _usage(response),
        "tool_calls": [],
        "api_responses": [response],
        "latency_seconds": round(time.monotonic() - started, 3),
        "completed": True,
        "error": None,
        "benchmark_error": False,
    }


def _run_mcp(
    client: ResponsesClient,
    model: str,
    prompt: str,
    tools: list[dict[str, Any]],
    mcp: MCPClient,
    max_steps: int,
) -> dict[str, Any]:
    """Run one LLM request with iterative MCP tool access."""
    started = time.monotonic()
    usage: dict[str, int] = {}
    calls: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []

    request_data: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "tools": tools,
        "tool_choice": "auto",
    }

    for step in range(max_steps + 1):
        response = client.create(request_data)
        responses.append(response)

        for key, value in _usage(response).items():
            usage[key] = usage.get(key, 0) + value

        function_calls = [item for item in response.get("output", []) if item.get("type") == "function_call"]

        if not function_calls:
            return {
                "prompt": prompt,
                "answer": _answer(response),
                "usage": usage,
                "tool_calls": calls,
                "api_responses": responses,
                "latency_seconds": round(
                    time.monotonic() - started,
                    3,
                ),
                "completed": True,
                "error": None,
                "benchmark_error": False,
            }

        if step == max_steps:
            break

        outputs = []

        for call in function_calls:
            raw_arguments = call.get("arguments", "{}")

            try:
                arguments = json.loads(raw_arguments)
                result = mcp.call(
                    call["name"],
                    arguments,
                )
                call_error = None

            except Exception as error:
                arguments = raw_arguments
                result = {
                    "status": "error",
                    "message": str(error),
                }
                call_error = str(error)

            calls.append(
                {
                    "name": call.get("name"),
                    "arguments": arguments,
                    "result": result,
                    "error": call_error,
                }
            )

            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": json.dumps(result),
                }
            )

        request_data = {
            "model": model,
            "previous_response_id": response["id"],
            "input": outputs,
            "tools": tools,
            "tool_choice": "auto",
        }

    return {
        "prompt": prompt,
        "answer": "",
        "usage": usage,
        "tool_calls": calls,
        "api_responses": responses,
        "latency_seconds": round(
            time.monotonic() - started,
            3,
        ),
        "completed": False,
        "error": f"Exceeded max_tool_steps={max_steps}",
        "benchmark_error": True,
    }


# ============================================================================
# Safe execution
# ============================================================================


def _run_mode_safely(
    mode: str,
    runner,
) -> dict[str, Any]:
    """Run a benchmark mode while converting exceptions into failed runs."""
    started = time.monotonic()

    try:
        result = runner()
        result.setdefault("benchmark_error", False)
        result.setdefault("error", None)
        return result

    except Exception as error:
        return {
            "mode": mode,
            "prompt": "",
            "answer": "",
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cached_input_tokens": 0,
                "reasoning_tokens": 0,
            },
            "tool_calls": [],
            "api_responses": [],
            "latency_seconds": round(
                time.monotonic() - started,
                3,
            ),
            "completed": False,
            "error": str(error),
            "benchmark_error": True,
        }


# ============================================================================
# Benchmark case
# ============================================================================


def _case_result(
    case: dict[str, Any],
    base: Path,
    repo_root: str,
    client: ResponsesClient,
    model: str,
    max_steps: int,
) -> dict[str, Any]:
    """Execute all three benchmark modes for one case."""
    source = _file_context(
        base,
        case["source_paths"],
        "source",
    )

    raw_output = _file_context(
        base,
        case["discopop_output_paths"],
        "DiscoPoP output",
    )

    expected = case["expected"]
    source_plus_raw = source + raw_output

    result = {
        "id": case["id"],
        "question": case["question"],
        "context": {
            "source": _context_stats(source),
            "raw_discopop_output": _context_stats(raw_output),
            "source_plus_raw": _context_stats(source_plus_raw),
        },
        "modes": {},
    }

    direct_prompt = _prompt(
        case["question"],
        source,
    )

    run = _run_mode_safely(
        "direct_code",
        lambda: _run_direct(
            client,
            model,
            direct_prompt,
        ),
    )
    run["answer_score"] = _score_answer(
        run["answer"],
        expected,
    )
    result["modes"]["direct_code"] = run

    raw_prompt = _prompt(
        case["question"],
        source_plus_raw,
    )

    run = _run_mode_safely(
        "full_discopop_output",
        lambda: _run_direct(
            client,
            model,
            raw_prompt,
        ),
    )
    run["answer_score"] = _score_answer(
        run["answer"],
        expected,
    )
    result["modes"]["full_discopop_output"] = run

    config = case["mcp"]
    allowed = set(config["allowed_tools"])
    command = config.get(
        "command",
        [
            sys.executable,
            "-m",
            "mcp_server.server",
        ],
    )

    def run_mcp_mode():
        with MCPClient(
            command,
            repo_root,
            int(config.get("timeout_seconds", 120)),
        ) as mcp:
            tools = mcp.tools(allowed)

            run = _run_mcp(
                client,
                model,
                _prompt(
                    case["question"],
                    source,
                    use_tools=True,
                ),
                tools,
                mcp,
                max_steps,
            )

            run["tools"] = tools
            return run

    run = _run_mode_safely(
        "mcp_server",
        run_mcp_mode,
    )

    run["answer_score"] = _score_answer(
        run["answer"],
        expected,
    )

    run["tool_score"] = _score_tool_calls(
        run["tool_calls"],
        expected["tool_calls"],
    )

    result["modes"]["mcp_server"] = run

    return result


# ============================================================================
# Pass/fail and statistics
# ============================================================================


def _is_passed(run: dict[str, Any]) -> bool:
    """Determine whether a benchmark run passed all required checks."""
    if not run.get("completed"):
        return False

    if run.get("benchmark_error"):
        return False

    if not run.get("answer_score", {}).get("passed"):
        return False

    tool_score = run.get("tool_score")

    return tool_score is None or tool_score.get("passed", False)


def _safe_mean(values: list[float]) -> float | None:
    """Return the mean or None for an empty list."""
    return statistics.mean(values) if values else None


def _safe_median(values: list[float]) -> float | None:
    """Return the median or None for an empty list."""
    return statistics.median(values) if values else None


def _safe_std(values: list[float]) -> float | None:
    """Return the sample standard deviation."""
    if len(values) < 2:
        return 0.0 if values else None
    return statistics.stdev(values)


def _aggregate_runs(
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate aggregate metrics for repeated benchmark runs."""
    latencies = [float(run["latency_seconds"]) for run in runs if run.get("latency_seconds") is not None]

    input_tokens = [run["usage"]["input_tokens"] for run in runs if run["usage"].get("input_tokens", 0) > 0]

    output_tokens = [run["usage"]["output_tokens"] for run in runs if run["usage"].get("output_tokens", 0) > 0]

    total_tokens = [run["usage"]["total_tokens"] for run in runs if run["usage"].get("total_tokens", 0) > 0]

    passed = [_is_passed(run) for run in runs]

    return {
        "runs": len(runs),
        "passed_runs": sum(passed),
        "pass_rate": sum(passed) / len(passed) if passed else 0.0,
        "latency": {
            "mean": _safe_mean(latencies),
            "median": _safe_median(latencies),
            "std": _safe_std(latencies),
        },
        "input_tokens": {
            "mean": _safe_mean(input_tokens),
            "median": _safe_median(input_tokens),
            "std": _safe_std(input_tokens),
        },
        "output_tokens": {
            "mean": _safe_mean(output_tokens),
            "median": _safe_median(output_tokens),
            "std": _safe_std(output_tokens),
        },
        "total_tokens": {
            "mean": _safe_mean(total_tokens),
            "median": _safe_median(total_tokens),
            "std": _safe_std(total_tokens),
        },
    }


def _relative_reduction(
    baseline: float | None,
    value: float | None,
) -> float | None:
    """Calculate relative reduction from a baseline value."""
    if baseline is None or value is None or baseline == 0:
        return None

    return (baseline - value) / baseline


# ============================================================================
# Markdown report
# ============================================================================


def _markdown(report: dict[str, Any]) -> str:
    """Create a compact Markdown report with aligned tables."""

    lines = [
        "# DiscoPoP MCP Evaluation",
        "",
        f"**Model:** `{report['model']}`  ",
        f"**Benchmark:** `{report['benchmark_version']}`",
        "",
        "## Summary",
        "",
        "| Mode | Runs | Pass Rate | Input Tokens | Output Tokens | Total Tokens | Latency (s) |",
        "|:-----|-----:|----------:|-------------:|--------------:|-------------:|------------:|",
    ]

    mode_names = {
        "direct_code": "Direct Code",
        "full_discopop_output": "Full DiscoPoP Output",
        "mcp_server": "MCP Server",
    }

    for mode, data in report["aggregates"].items():
        lines.append(
            f"| {mode_names.get(mode, mode)} "
            f"| {data['runs']} "
            f"| {data['pass_rate'] * 100:.1f}% "
            f"| {data['input_tokens']['mean']:,.0f} "
            f"| {data['output_tokens']['mean']:,.0f} "
            f"| {data['total_tokens']['mean']:,.0f} "
            f"| {data['latency']['mean']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Trial Results",
            "",
        ]
    )

    for case in report["cases"]:
        lines.extend(
            [
                f"**Case:** `{case['id']}`",
                "",
                "| Trial | Mode | Result | Input | Output | Total | Latency (s) |",
                "|-----:|:-----|:------:|-----:|-------:|------:|------------:|",
            ]
        )

        for mode, runs in case["trials"].items():
            for trial, run in enumerate(runs, 1):
                usage = run["usage"]

                lines.append(
                    f"| {trial} "
                    f"| {mode_names.get(mode, mode)} "
                    f"| {'PASS' if _is_passed(run) else 'FAIL'} "
                    f"| {usage['input_tokens']:,} "
                    f"| {usage['output_tokens']:,} "
                    f"| {usage['total_tokens']:,} "
                    f"| {run['latency_seconds']:.2f} |"
                )

        lines.append("")

    raw = report["aggregates"].get("full_discopop_output")
    mcp = report["aggregates"].get("mcp_server")

    if raw and mcp:
        token_reduction = _relative_reduction(
            raw["input_tokens"]["mean"],
            mcp["input_tokens"]["mean"],
        )

        latency_reduction = _relative_reduction(
            raw["latency"]["mean"],
            mcp["latency"]["mean"],
        )

        lines.extend(
            [
                "## MCP vs Full DiscoPoP Output",
                "",
                "| Metric | Value |",
                "|:-------|------:|",
                (
                    f"| Input-token reduction | " f"{token_reduction * 100:.2f}% |"
                    if token_reduction is not None
                    else "| Input-token reduction | n/a |"
                ),
                (
                    f"| Latency reduction | " f"{latency_reduction * 100:.2f}% |"
                    if latency_reduction is not None
                    else "| Latency reduction | n/a |"
                ),
                "",
            ]
        )

    return "\n".join(lines)


# ============================================================================
# Main benchmark
# ============================================================================


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, execute the benchmark, and save the results."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "manifest",
        type=Path,
        help="Benchmark manifest; paths are relative to this file.",
    )

    parser.add_argument(
        "--model",
        required=True,
        help="LLM model identifier.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmark-results"),
    )

    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
    )

    parser.add_argument(
        "--max-tool-steps",
        type=int,
        default=6,
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of repeated trials per mode and case.",
    )

    parser.add_argument(
        "--base-url",
        default="https://api.openai.com/v1",
        help="OpenAI-compatible Responses API base URL.",
    )

    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENAI_API_KEY"),
        help="Optional bearer token.",
    )

    args = parser.parse_args(argv)

    if args.runs < 1:
        parser.error("--runs must be >= 1")

    if args.max_tool_steps < 0:
        parser.error("--max-tool-steps must be >= 0")

    manifest_path = args.manifest.resolve()
    manifest = _read_json(manifest_path)
    cases = manifest.get("cases", [])

    if not cases:
        raise ValueError("Benchmark manifest contains no cases.")

    for case in cases:
        _validate_case(case)

    client = ResponsesClient(
        args.base_url,
        args.api_key,
    )

    report: dict[str, Any] = {
        "benchmark_version": "Token Usage Reduction for Same MCP Function",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "model": args.model,
        "manifest": str(manifest_path),
        "configuration": {
            "runs": args.runs,
            "max_tool_steps": args.max_tool_steps,
            "base_url": args.base_url,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "cases": [],
        "aggregates": {},
    }

    mode_runs: dict[str, list[dict[str, Any]]] = {
        "direct_code": [],
        "full_discopop_output": [],
        "mcp_server": [],
    }

    for case in cases:
        first = _case_result(
            case,
            manifest_path.parent,
            str(args.repo_root.resolve()),
            client,
            args.model,
            args.max_tool_steps,
        )

        case_trials = {mode: [run] for mode, run in first["modes"].items()}

        for _ in range(args.runs - 1):
            repeated = _case_result(
                case,
                manifest_path.parent,
                str(args.repo_root.resolve()),
                client,
                args.model,
                args.max_tool_steps,
            )

            for mode, run in repeated["modes"].items():
                case_trials[mode].append(run)

        report["cases"].append(
            {
                "id": case["id"],
                "question": case["question"],
                "context": first["context"],
                "trials": case_trials,
                "aggregates": {mode: _aggregate_runs(runs) for mode, runs in case_trials.items()},
            }
        )

        for mode, runs in case_trials.items():
            mode_runs[mode].extend(runs)

    report["aggregates"] = {mode: _aggregate_runs(runs) for mode, runs in mode_runs.items()}

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (args.output_dir / "report.json").write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    markdown = _markdown(report)

    (args.output_dir / "report.md").write_text(
        markdown,
        encoding="utf-8",
    )

    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

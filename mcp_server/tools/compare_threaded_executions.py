"""Execute a prepared representative command across OpenMP thread counts."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool, ToolAnnotations

from mcp_server.tools.helpers import ToolContext

logger = logging.getLogger("discopop-mcp")

TOOL = Tool(
    name="compare_threaded_executions",
    annotations=ToolAnnotations(readOnlyHint=True),
    description=(
        "Run the representative execute.sh from a prepared DiscoPoP configuration with several "
        "OMP_NUM_THREADS values and repetitions. It returns compact output fingerprints and stability "
        "comparisons to the one-thread baseline, helping distinguish a concurrency defect from a normal failure."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {"type": "string", "description": "Absolute project root."},
            "config_name": {"type": "string", "description": "Prepared execution configuration name."},
            "thread_counts": {"type": "array", "items": {"type": "integer"},
                "description": "Positive thread counts. Default: [1, 2, 4]."},
            "repetitions": {"type": "integer", "description": "Runs per count, 1-10. Default: 3.", "default": 3},
            "timeout_seconds": {"type": "integer", "description": "Per-run timeout, 1-600. Default: 60.", "default": 60},
        },
        "required": ["project_path", "config_name"],
        "additionalProperties": False,
    },
)


def _normalise_output(text: str) -> str:
    """Ignore conventional timing lines so timing noise is not reported as a race."""
    return "\n".join(
        line for line in text.splitlines()
        if not line.strip().lower().startswith(("elapsed", "duration", "time:"))
    ).strip()


def _fingerprint(stdout: str, stderr: str, returncode: int) -> str:
    payload = f"rc={returncode}\nstdout={_normalise_output(stdout)}\nstderr={_normalise_output(stderr)}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _sample(stdout: str, stderr: str) -> str | None:
    text = (stdout.strip() or stderr.strip()).replace("\x1b", "")
    if not text:
        return None
    return text[-400:]


def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[TextContent]:
    project_path = str(arguments.get("project_path", ""))
    config_name = str(arguments.get("config_name", ""))
    raw_counts = arguments.get("thread_counts", [1, 2, 4])
    repetitions = max(1, min(10, int(arguments.get("repetitions", 3))))
    timeout = max(1, min(600, int(arguments.get("timeout_seconds", 60))))
    try:
        if not isinstance(raw_counts, list):
            return ctx.error("thread_counts must be an array of positive integers.", project_path, "compare_threaded_executions")
        counts = sorted({int(value) for value in raw_counts})
        if not counts or any(value < 1 for value in counts):
            return ctx.error("thread_counts must contain one or more positive integers.", project_path, "compare_threaded_executions")
        script = Path(project_path) / ".discopop" / "project" / "configs" / config_name / "execute.sh"
        if not script.is_file():
            return ctx.error(f"execute.sh for configuration '{config_name}' was not found. Run prepare_project_analysis first.", project_path, "compare_threaded_executions")

        matrix: list[dict[str, Any]] = []
        for threads in counts:
            fingerprints: list[str] = []
            elapsed: list[float] = []
            sample: str | None = None
            returncodes: list[int | None] = []
            for _ in range(repetitions):
                env = os.environ.copy()
                env["OMP_NUM_THREADS"] = str(threads)
                env["OMP_DYNAMIC"] = "FALSE"
                env["DP_PROJECT_ROOT_DIR"] = project_path
                started = time.monotonic()
                try:
                    completed = subprocess.run(["/bin/bash", str(script)], cwd=project_path, env=env,
                                               text=True, capture_output=True, timeout=timeout)
                    code: int | None = completed.returncode
                    fingerprints.append(_fingerprint(completed.stdout, completed.stderr, completed.returncode))
                    sample = sample or _sample(completed.stdout, completed.stderr)
                except subprocess.TimeoutExpired:
                    code = None
                    fingerprints.append("timeout")
                elapsed.append(round(time.monotonic() - started, 3))
                returncodes.append(code)
            matrix.append({"threads": threads, "repetitions": repetitions, "returncodes": returncodes,
                           "fingerprints": sorted(set(fingerprints)), "stable": len(set(fingerprints)) == 1,
                           "elapsed_seconds": elapsed, "output_sample": sample})

        baseline = next((row for row in matrix if row["threads"] == 1), matrix[0])
        baseline_fingerprints = baseline["fingerprints"]
        for row in matrix:
            row["matches_baseline"] = row["fingerprints"] == baseline_fingerprints and row["stable"]
        divergent = [row["threads"] for row in matrix if not row["matches_baseline"]]
        classification = "matches_baseline"
        if any(not row["stable"] for row in matrix if row["threads"] != 1):
            classification = "likely_nondeterministic_shared_state"
        elif divergent:
            classification = "thread_count_dependent_behavior"
        result = {"status": "success", "project_path": project_path, "config_name": config_name,
                  "baseline_threads": baseline["threads"], "classification": classification,
                  "first_divergent_thread_counts": divergent, "results": matrix}
        ctx.log_response("compare_threaded_executions", result)
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        message = f"Error comparing threaded executions: {exc}"
        logger.error(message, exc_info=True)
        return ctx.error(message, project_path, "compare_threaded_executions")

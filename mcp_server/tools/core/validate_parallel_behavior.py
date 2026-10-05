"""Functional validation gate for an OpenMP repair."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.types import TextContent, Tool, ToolAnnotations

from mcp_server.tools.common.helpers import ToolContext
from mcp_server.tools.low_level import compare_threaded_executions

logger = logging.getLogger("discopop-mcp")

TOOL = Tool(
    name="validate_parallel_behavior",
    annotations=ToolAnnotations(readOnlyHint=True),
    description=(
        "Validate an OpenMP repair against a one-worker baseline across repeated multi-worker runs. "
        "Returns a pass/fail gate, stability result, and compact divergence evidence. Use after every concurrency fix."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {"type": "string", "description": "Absolute project root."},
            "config_name": {"type": "string", "description": "Prepared run configuration."},
            "thread_counts": {"type": "array", "items": {"type": "integer"}, "description": "Counts to validate. Default: [1, 2, 4]."},
            "repetitions": {"type": "integer", "description": "Runs per count, 1-10. Default: 3.", "default": 3},
        },
        "required": ["project_path", "config_name"],
        "additionalProperties": False,
    },
)


def _payload(result: list[TextContent]) -> dict[str, Any]:
    try:
        data = json.loads(result[0].text)
        return data if isinstance(data, dict) else {}
    except (IndexError, json.JSONDecodeError):
        return {}


def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[TextContent]:
    project_path = str(arguments.get("project_path", ""))
    config_name = str(arguments.get("config_name", ""))
    try:
        compared = _payload(compare_threaded_executions.handle({
            "project_path": project_path,
            "config_name": config_name,
            "thread_counts": arguments.get("thread_counts") or [1, 2, 4],
            "repetitions": max(1, min(10, int(arguments.get("repetitions", 3)))),
        }, ctx))
        if compared.get("status") != "success":
            return [TextContent(type="text", text=json.dumps(compared))]
        rows = compared.get("results", [])
        failures = [
            {"threads": row.get("threads"), "stable": row.get("stable"), "matches_baseline": row.get("matches_baseline"), "fingerprints": row.get("fingerprints")}
            for row in rows if not row.get("stable") or not row.get("matches_baseline")
        ]
        passed = not failures
        result = {
            "status": "success",
            "project_path": project_path,
            "config_name": config_name,
            "passed": passed,
            "baseline_threads": compared.get("baseline_threads"),
            "validated_thread_counts": [row.get("threads") for row in rows],
            "failures": failures,
            "next_action": "Build and finish the task." if passed else "Run triage_parallel_failure and assess_parallel_region for the first divergent path.",
        }
        ctx.log_response("validate_parallel_behavior", result)
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        message = f"Error validating parallel behavior: {exc}"
        logger.error(message, exc_info=True)
        return ctx.error(message, project_path, "validate_parallel_behavior")

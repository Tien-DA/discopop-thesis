"""High-level scaling assessment built on repeated representative runs."""

from __future__ import annotations

import json
import logging
from statistics import median
from typing import Any

from mcp.types import TextContent, Tool, ToolAnnotations

from mcp_server.tools.common.helpers import ToolContext
from mcp_server.tools.low_level import compare_threaded_executions

logger = logging.getLogger("discopop-mcp")

TOOL = Tool(
    name="evaluate_parallel_performance",
    annotations=ToolAnnotations(readOnlyHint=True),
    description=(
        "Measure scaling of a representative OpenMP workload and explain whether it regresses, has no useful "
        "speedup, or scales. Use after correctness passes and before expensive autotuning."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {"type": "string", "description": "Absolute project root."},
            "config_name": {"type": "string", "description": "Prepared run configuration."},
            "thread_counts": {"type": "array", "items": {"type": "integer"}, "description": "Counts to measure. Default: [1, 2, 4]."},
            "repetitions": {"type": "integer", "description": "Runs per count, 2-8. Default: 3.", "default": 3},
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
            "repetitions": max(2, min(8, int(arguments.get("repetitions", 3)))),
        }, ctx))
        if compared.get("status") != "success":
            return [TextContent(type="text", text=json.dumps(compared))]
        rows = compared.get("results", [])
        baseline = next((row for row in rows if row.get("threads") == 1), rows[0] if rows else None)
        if not baseline:
            return ctx.error("No completed execution samples were returned.", project_path, "evaluate_parallel_performance")
        baseline_time = median(baseline.get("elapsed_seconds", []))
        scaling = []
        for row in rows:
            elapsed = row.get("elapsed_seconds", [])
            runtime = median(elapsed) if elapsed else 0.0
            threads = int(row.get("threads", 1))
            speedup = round(baseline_time / runtime, 3) if runtime else None
            scaling.append({"threads": threads, "median_seconds": runtime, "speedup": speedup,
                            "efficiency": round(speedup / threads, 3) if speedup is not None else None,
                            "behavior_matches_baseline": row.get("matches_baseline")})
        multi = [row for row in scaling if row["threads"] > 1 and row["speedup"] is not None]
        best = max(multi or scaling, key=lambda row: row["speedup"] or 0)
        if any(not row.get("behavior_matches_baseline") for row in scaling):
            verdict = "invalid_for_performance_comparison"
        elif (best.get("speedup") or 0) < 1:
            verdict = "parallel_regression"
        elif (best.get("speedup") or 0) < 1.15:
            verdict = "no_material_speedup"
        else:
            verdict = "scales_on_representative_workload"
        result = {"status": "success", "project_path": project_path, "config_name": config_name,
                  "verdict": verdict, "best_configuration": best, "scaling": scaling,
                  "next_action": "Use run_auto_tuning only if tuning candidates exist." if verdict != "invalid_for_performance_comparison" else "Fix correctness before interpreting performance."}
        ctx.log_response("evaluate_parallel_performance", result)
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        message = f"Error evaluating parallel performance: {exc}"
        logger.error(message, exc_info=True)
        return ctx.error(message, project_path, "evaluate_parallel_performance")

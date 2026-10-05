"""High-level diagnosis for failures that depend on OpenMP worker count."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from mcp.types import TextContent, Tool, ToolAnnotations

from mcp_server.tools.common.helpers import ToolContext
from mcp_server.tools.low_level import compare_threaded_executions, diagnose_parallel_correctness

logger = logging.getLogger("discopop-mcp")

TOOL = Tool(
    name="triage_parallel_failure",
    annotations=ToolAnnotations(readOnlyHint=True),
    description=(
        "Diagnose an OpenMP correctness failure end-to-end. It compares one- and multi-worker behavior, "
        "ranks likely shared-state causes, and returns the smallest repair direction. Use first when a "
        "parallel task is wrong or unstable."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {"type": "string", "description": "Absolute project root."},
            "config_name": {"type": "string", "description": "Prepared run configuration; omit for static triage only."},
            "thread_counts": {"type": "array", "items": {"type": "integer"}, "description": "Worker counts to compare. Default: [1, 2, 4]."},
            "repetitions": {"type": "integer", "description": "Runs per count, 1-6. Default: 3.", "default": 3},
            "max_causes": {"type": "integer", "description": "Maximum ranked causes, 1-5. Default: 3.", "default": 3},
        },
        "required": ["project_path"],
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
    config_name = str(arguments.get("config_name", "")).strip()
    repetitions = max(1, min(6, int(arguments.get("repetitions", 3))))
    max_causes = max(1, min(5, int(arguments.get("max_causes", 3))))
    thread_counts = arguments.get("thread_counts") or [1, 2, 4]
    try:
        diagnosis = _payload(diagnose_parallel_correctness.handle({
            "project_path": project_path,
            "max_findings": max_causes,
            "include_dependency_evidence": True,
        }, ctx))
        causes = diagnosis.get("findings", [])[:max_causes]
        runtime: Optional[dict[str, Any]] = None
        if config_name:
            execute = Path(project_path) / ".discopop" / "project" / "configs" / config_name / "execute.sh"
            if execute.is_file():
                runtime = _payload(compare_threaded_executions.handle({
                    "project_path": project_path,
                    "config_name": config_name,
                    "thread_counts": thread_counts,
                    "repetitions": repetitions,
                }, ctx))

        classification = "static_hazards_found" if causes else "no_ranked_hazard"
        runtime_summary: dict[str, Any] = {"available": False}
        if runtime and runtime.get("status") == "success":
            runtime_summary = {
                "available": True,
                "classification": runtime.get("classification"),
                "baseline_threads": runtime.get("baseline_threads"),
                "divergent_thread_counts": runtime.get("first_divergent_thread_counts", []),
            }
            if runtime.get("classification") == "likely_nondeterministic_shared_state":
                classification = "nondeterministic_parallel_failure"
            elif runtime.get("classification") == "thread_count_dependent_behavior":
                classification = "thread_count_dependent_failure"
            elif causes:
                classification = "runtime_matches_baseline_but_static_hazards_remain"
            else:
                classification = "no_parallel_failure_observed"

        result = {
            "status": "success",
            "project_path": project_path,
            "classification": classification,
            "runtime_evidence": runtime_summary,
            "likely_causes": [
                {
                    "location": item.get("location"),
                    "shared_object": item.get("shared_object"),
                    "risk": item.get("risk"),
                    "repair_classes": item.get("repair_classes", []),
                    "evidence": item.get("evidence", {}),
                }
                for item in causes
            ],
            "next_action": (
                "Use assess_parallel_region on the first cause before editing, then validate_parallel_behavior after the repair."
                if causes else "No source cause was ranked; inspect the failing path and run validate_parallel_behavior with a representative configuration."
            ),
        }
        ctx.log_response("triage_parallel_failure", result)
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        message = f"Error triaging parallel failure: {exc}"
        logger.error(message, exc_info=True)
        return ctx.error(message, project_path, "triage_parallel_failure")

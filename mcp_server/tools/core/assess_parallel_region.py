"""Turn low-level dependence evidence into an actionable region assessment."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool, ToolAnnotations

from mcp_server.tools.common.analysis_support import functions, lines, relative, symbol_matches
from mcp_server.tools.common.helpers import ToolContext
from mcp_server.tools.low_level import diagnose_parallel_correctness

logger = logging.getLogger("discopop-mcp")
_FOR_VAR = re.compile(r"for\s*\([^;]*?\b([A-Za-z_]\w*)\s*=")
_REDUCTION = re.compile(r"\b([A-Za-z_]\w*)\s*(?:\+=|-=|\*=|/=|\+\+|--)")
_WRITE = re.compile(r"\b([A-Za-z_]\w*)\s*(?:\[[^\]]+\])?\s*(?:=|\+=|-=|\*=|/=|\+\+|--)")

TOOL = Tool(
    name="assess_parallel_region",
    annotations=ToolAnnotations(readOnlyHint=True),
    description=(
        "Assess whether one OpenMP region is safe and what data-sharing repair it needs. Returns a bounded "
        "verdict, ranked hazards, and candidate private/reduction/atomic actions instead of raw dependencies."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {"type": "string", "description": "Absolute project root."},
            "file_path": {"type": "string", "description": "Source file, absolute or project-relative."},
            "start_line": {"type": "integer", "description": "First region line, inclusive."},
            "end_line": {"type": "integer", "description": "Last region line, inclusive."},
            "symbol": {"type": "string", "description": "Function name; use instead of line bounds when appropriate."},
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


def _region(project_path: str, arguments: dict[str, Any]) -> tuple[Path, int, int] | None:
    root = Path(project_path).resolve()
    file_path = str(arguments.get("file_path", "")).strip()
    start = int(arguments.get("start_line", 0) or 0)
    end = int(arguments.get("end_line", 0) or 0)
    symbol = str(arguments.get("symbol", "")).strip()
    if symbol:
        matches = [item for item in functions(project_path) if symbol_matches(item.name, symbol)]
        if matches:
            item = matches[0]
            return item.file, item.start, item.end
    if file_path and start > 0:
        path = Path(file_path)
        path = path if path.is_absolute() else root / path
        return path.resolve(), start, end or start
    return None


def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[TextContent]:
    project_path = str(arguments.get("project_path", ""))
    try:
        selected = _region(project_path, arguments)
        if selected is None:
            return ctx.error("Provide file_path with start_line, or a symbol matching one project function.", project_path, "assess_parallel_region")
        path, start, end = selected
        content = lines(path)
        if not content or start < 1 or end < start or end > len(content):
            return ctx.error("The requested source region is outside the selected file.", project_path, "assess_parallel_region")
        region = content[start - 1 : end]
        text = "\n".join(region)
        loop_vars = sorted(set(_FOR_VAR.findall(text)))
        reductions = sorted({match.group(1) for match in _REDUCTION.finditer(text) if match.group(1) not in loop_vars})
        writes = sorted({match.group(1) for match in _WRITE.finditer(text) if match.group(1) not in loop_vars})
        diagnosis = _payload(diagnose_parallel_correctness.handle({
            "project_path": project_path,
            "file_path": str(path),
            "max_findings": 30,
            "include_dependency_evidence": True,
        }, ctx))
        hazards = [
            item for item in diagnosis.get("findings", [])
            if start <= int((item.get("location") or {}).get("line", -1)) <= end
        ]
        shared = sorted({str(item.get("shared_object")) for item in hazards if item.get("shared_object")})
        atomic = sorted({item.get("shared_object") for item in hazards if item.get("risk") == "contended indexed update" and item.get("shared_object")})
        private = sorted(set(loop_vars))
        verdict = "needs_review"
        if hazards:
            verdict = "unsafe_without_repair"
        elif "#pragma omp" in text:
            verdict = "no_ranked_conflict"
        result = {
            "status": "success",
            "region": {"file": relative(project_path, path), "lines": [start, end]},
            "verdict": verdict,
            "evidence": {"dynamic_dependency_data_available": bool((diagnosis.get("analysis_coverage") or {}).get("dynamic_dependency_evidence_available")), "ranked_hazards": len(hazards)},
            "data_sharing_plan": {
                "private_candidates": private,
                "reduction_candidates": reductions,
                "atomic_or_thread_local_candidates": atomic,
                "shared_writes_to_review": shared or writes,
            },
            "hazards": [
                {"line": (item.get("location") or {}).get("line"), "object": item.get("shared_object"), "risk": item.get("risk"), "repair_classes": item.get("repair_classes", [])}
                for item in hazards[:5]
            ],
            "next_action": "Apply the smallest repair that protects the listed shared write, then call validate_parallel_behavior.",
        }
        ctx.log_response("assess_parallel_region", result)
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        message = f"Error assessing parallel region: {exc}"
        logger.error(message, exc_info=True)
        return ctx.error(message, project_path, "assess_parallel_region")

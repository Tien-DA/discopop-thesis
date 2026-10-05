"""Trace a compact interprocedural slice rooted at a source symbol."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool, ToolAnnotations

from mcp_server.tools.common.analysis_support import declarations, function_calls, functions, lines, relative, symbol_matches
from mcp_server.tools.common.helpers import ToolContext

logger = logging.getLogger("discopop-mcp")

TOOL = Tool(
    name="trace_symbol_slice",
    annotations=ToolAnnotations(readOnlyHint=True),
    description=(
        "Return a bounded caller/callee and mutable-state slice for a C/C++ symbol. "
        "Use it to trace cross-file helpers without dumping source."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {"type": "string", "description": "Absolute project root."},
            "symbol": {"type": "string", "description": "Function or method name."},
            "direction": {"type": "string", "enum": ["callers", "callees", "both"], "default": "both"},
            "depth": {"type": "integer", "description": "Call-graph hops, 1-4. Default: 2.", "default": 2},
            "include_state_accesses": {"type": "boolean", "default": True,
                "description": "Include referenced static/global-like declarations."},
            "max_nodes": {"type": "integer", "description": "Maximum returned functions, 1-50. Default: 20.", "default": 20},
        },
        "required": ["project_path", "symbol"],
        "additionalProperties": False,
    },
)


def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[TextContent]:
    project_path = str(arguments.get("project_path", ""))
    symbol = str(arguments.get("symbol", "")).strip()
    direction = str(arguments.get("direction", "both"))
    depth = max(1, min(4, int(arguments.get("depth", 2))))
    max_nodes = max(1, min(50, int(arguments.get("max_nodes", 20))))
    include_state = bool(arguments.get("include_state_accesses", True))
    try:
        catalogue = functions(project_path)
        roots = [item for item in catalogue if symbol_matches(item.name, symbol)]
        if not roots:
            return ctx.error(f"No function or method matching '{symbol}' was found.", project_path, "trace_symbol_slice")

        source_by_file = {item.file: lines(item.file) for item in catalogue}
        calls = {item: function_calls(source_by_file[item.file], item) for item in catalogue}
        selected: set[Any] = set(roots)
        frontier: set[Any] = set(roots)
        relations: set[tuple[Any, Any, str]] = set()
        for _ in range(depth):
            next_frontier: set[Any] = set()
            for current in frontier:
                for candidate in catalogue:
                    current_calls_candidate = any(symbol_matches(call, candidate.name) for call in calls[current])
                    candidate_calls_current = any(symbol_matches(call, current.name) for call in calls[candidate])
                    if direction in ("callees", "both") and current_calls_candidate:
                        relations.add((current, candidate, "calls"))
                        next_frontier.add(candidate)
                    if direction in ("callers", "both") and candidate_calls_current:
                        relations.add((candidate, current, "calls"))
                        next_frontier.add(candidate)
            next_frontier -= selected
            selected.update(next_frontier)
            frontier = next_frontier
            if not frontier or len(selected) >= max_nodes:
                break

        ordered = sorted(selected, key=lambda item: (str(item.file), item.start))[:max_nodes]
        selected_set = set(ordered)
        node_ids = {item: f"fn-{index + 1}" for index, item in enumerate(ordered)}
        result: dict[str, Any] = {
            "status": "success",
            "project_path": project_path,
            "symbol": symbol,
            "truncated": len(selected) > len(ordered),
            "functions": [
                {
                    "id": node_ids[item], "name": item.name, "file": relative(project_path, item.file),
                    "lines": [item.start, item.end], "contains_openmp": item.is_parallel,
                    "is_root": item in roots,
                }
                for item in ordered
            ],
            "relations": [
                {"from": node_ids[left], "to": node_ids[right], "kind": kind}
                for left, right, kind in sorted(relations, key=lambda item: (item[0].name, item[1].name))
                if left in selected_set and right in selected_set
            ],
        }
        if include_state:
            states: list[dict[str, Any]] = []
            for item in ordered:
                body = source_by_file[item.file][item.start - 1 : item.end]
                for name in sorted(declarations(body)):
                    if any(name in line and "static" in line for line in body):
                        states.append({"function": node_ids[item], "name": name, "kind": "static_local"})
            result["state_accesses"] = states[:max_nodes]
        ctx.log_response("trace_symbol_slice", result)
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        message = f"Error tracing symbol slice: {exc}"
        logger.error(message, exc_info=True)
        return ctx.error(message, project_path, "trace_symbol_slice")

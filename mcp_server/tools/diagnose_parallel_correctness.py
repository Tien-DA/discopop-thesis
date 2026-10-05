"""Rank likely correctness hazards in existing OpenMP regions."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool, ToolAnnotations

from mcp_server.tools.analysis_support import closing_brace, functions, lines, nearest_function, relative, source_files
from mcp_server.tools.helpers import ToolContext

logger = logging.getLogger("discopop-mcp")
_WRITE = re.compile(r"\b(?P<name>[A-Za-z_]\w*)\s*(?P<index>(?:\[[^\]]+\])*)\s*(?P<op>\+\+|--|\+=|-=|\*=|/=|=)")
_LOOP_VAR = re.compile(r"for\s*\([^;]*?(?P<name>[A-Za-z_]\w*)\s*=")
_STATIC = re.compile(r"\bstatic\b[^;=]*?\b(?P<name>[A-Za-z_]\w*)\s*(?:\[|=|;)")

TOOL = Tool(
    name="diagnose_parallel_correctness",
    annotations=ToolAnnotations(readOnlyHint=True),
    description=(
        "Inspect existing OpenMP loops and rank likely shared-state correctness hazards. "
        "It identifies contended indexed updates, read-modify-write operations, static scratch state, "
        "and available DiscoPoP dependency evidence. Use it after gather_data to find repair targets; "
        "it does not propose adding parallelism or modify source."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {"type": "string", "description": "Absolute project root."},
            "max_findings": {"type": "integer", "description": "Maximum ranked findings, 1-30. Default: 12.", "default": 12},
            "file_path": {"type": "string", "description": "Optional absolute or project-relative file to restrict analysis."},
            "include_dependency_evidence": {"type": "boolean", "default": True,
                "description": "Use collected DiscoPoP dependencies when present. Default: true."},
        },
        "required": ["project_path"],
        "additionalProperties": False,
    },
)


def _dependency_lines(project_path: str, ctx: ToolContext) -> set[tuple[int, int]]:
    """Return PET dependency endpoints as (file-id, line), best-effort only."""
    result: set[tuple[int, int]] = set()
    detection = ctx.get_detection_result(project_path)
    if detection is None:
        return result
    try:
        from discopop_explorer.enums.EdgeType import EdgeType
        for _left, _right, dep in detection.pet.g.edges(data="data"):
            if dep.etype != EdgeType.DATA:
                continue
            for location in (dep.source_line, dep.sink_line):
                if location:
                    file_id, line = str(location).split(":", 1)
                    result.add((int(file_id), int(line)))
    except Exception:
        logger.debug("Could not extract dynamic dependency endpoints", exc_info=True)
    return result


def _file_id_by_path(project_path: str, ctx: ToolContext) -> dict[Path, int]:
    mapping = ctx.get_file_mapping(project_path) or {}
    return {path.resolve(): file_id for file_id, path in mapping.items()}


def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[TextContent]:
    project_path = str(arguments.get("project_path", ""))
    max_findings = max(1, min(30, int(arguments.get("max_findings", 12))))
    file_filter = str(arguments.get("file_path", "")).strip()
    include_evidence = bool(arguments.get("include_dependency_evidence", True))
    try:
        root = Path(project_path).resolve()
        selected_files = source_files(project_path)
        if file_filter:
            requested = Path(file_filter)
            requested = requested if requested.is_absolute() else root / requested
            selected_files = [path for path in selected_files if path.resolve() == requested.resolve()]
            if not selected_files:
                return ctx.error(f"file_path is not a project source file: {file_filter}", project_path, "diagnose_parallel_correctness")

        all_functions = functions(project_path)
        endpoints = _dependency_lines(project_path, ctx) if include_evidence else set()
        file_ids = _file_id_by_path(project_path, ctx) if include_evidence else {}
        findings: list[dict[str, Any]] = []
        for path in selected_files:
            content = lines(path)
            file_id = file_ids.get(path.resolve())
            for pragma_index, pragma in enumerate(content):
                if "#pragma omp" not in pragma or "parallel" not in pragma:
                    continue
                body_start = next((index for index in range(pragma_index + 1, len(content)) if "{" in content[index]), None)
                if body_start is None:
                    continue
                body_end = closing_brace(content, body_start)
                region = content[pragma_index : body_end + 1]
                loop_match = _LOOP_VAR.search("\n".join(region[:3]))
                loop_var = loop_match.group("name") if loop_match else "<unknown>"
                owner = nearest_function(all_functions, path, pragma_index + 1)
                for offset, line in enumerate(region):
                    write = _WRITE.search(line)
                    if not write:
                        continue
                    name, index, op = write.group("name"), write.group("index") or "", write.group("op")
                    # Assigning an element addressed exactly by the induction variable is the common safe case.
                    if index and loop_var in index and op == "=":
                        continue
                    line_no = pragma_index + offset + 1
                    protected = (
                        "reduction(" in pragma
                        or "#pragma omp atomic" in line
                        or "#pragma omp critical" in line
                        or any("#pragma omp atomic" in item or "#pragma omp critical" in item for item in region[max(0, offset - 2) : offset])
                    )
                    contended_index = bool(index) and loop_var not in index
                    read_modify_write = op != "=" or bool(index and name in line[line.find(index) + len(index) :])
                    static_declared = any(match.group("name") == name for item in content[:pragma_index] if (match := _STATIC.search(item)))
                    score = 5 + (3 if contended_index else 0) + (2 if read_modify_write else 0) + (2 if static_declared else 0) - (4 if protected else 0)
                    if score < 5:
                        continue
                    dynamic = bool(file_id is not None and (file_id, line_no) in endpoints)
                    risk = "contended indexed update" if contended_index else "shared update in parallel region"
                    if static_declared:
                        risk = "static state accessed from parallel region"
                    repairs = ["make per-iteration scratch private"] if static_declared else ["use atomic update", "use thread-local accumulation then merge"]
                    findings.append({
                        "severity": "high" if score >= 9 else "medium",
                        "score": score,
                        "location": {"file": relative(project_path, path), "line": line_no,
                                     "function": owner.name if owner else None},
                        "parallel_region": {"lines": [pragma_index + 1, body_end + 1], "pragma": pragma.strip()},
                        "shared_object": name,
                        "access": {"operation": op, "index_expression": index or None,
                                   "read_modify_write": read_modify_write},
                        "risk": risk,
                        "evidence": {"dynamic_dependency_touches_write": dynamic,
                                     "protection_detected": protected, "static_storage": static_declared},
                        "repair_classes": repairs,
                    })

        findings.sort(key=lambda item: (-item["score"], item["location"]["file"], item["location"]["line"]))
        result = {
            "status": "success", "project_path": project_path,
            "analysis_coverage": {"openmp_regions_scanned": sum(1 for path in selected_files for line in lines(path) if "#pragma omp" in line),
                                  "dynamic_dependency_evidence_available": bool(endpoints)},
            "findings": findings[:max_findings], "total_findings": len(findings),
            "truncated": len(findings) > max_findings,
        }
        ctx.log_response("diagnose_parallel_correctness", result)
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        message = f"Error diagnosing parallel correctness: {exc}"
        logger.error(message, exc_info=True)
        return ctx.error(message, project_path, "diagnose_parallel_correctness")

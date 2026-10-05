"""Small, token-conscious source-analysis helpers shared by diagnostic tools.

These helpers deliberately return locations and relations, not source text.  They
complement DiscoPoP's dynamic evidence with the naming and ownership information
that a coding agent needs to fix an existing parallel region.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"}
_FUNCTION = re.compile(
    r"^\s*(?:[\w:<>~*&]+\s+)+(?P<name>[\w:~]+)\s*\([^;{}]*\)\s*(?:const\s*)?\{"
)
_CALL = re.compile(r"\b(?P<name>[A-Za-z_]\w*(?:::[A-Za-z_]\w*)?)\s*\(")
_DECL = re.compile(
    r"\b(?:static\s+)?(?:std::\w+(?:<[^;=(){}]+>)?|[A-Za-z_]\w*(?:::[A-Za-z_]\w*)?)"
    r"\s+[&*]?\s*(?P<name>[A-Za-z_]\w*)\s*(?:[=;\[(])"
)


@dataclass(frozen=True)
class FunctionRange:
    file: Path
    name: str
    start: int
    end: int
    is_parallel: bool


def source_files(project_path: str) -> list[Path]:
    root = Path(project_path)
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES and ".discopop" not in path.parts
    )


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def closing_brace(content: list[str], start_index: int) -> int:
    depth = 0
    started = False
    for index in range(start_index, len(content)):
        line = content[index]
        depth += line.count("{") - line.count("}")
        started = started or "{" in line
        if started and depth <= 0:
            return index
    return len(content) - 1


def functions(project_path: str) -> list[FunctionRange]:
    result: list[FunctionRange] = []
    for path in source_files(project_path):
        content = lines(path)
        for index, line in enumerate(content):
            match = _FUNCTION.match(line)
            if not match:
                continue
            end = closing_brace(content, index)
            result.append(
                FunctionRange(
                    file=path,
                    name=match.group("name"),
                    start=index + 1,
                    end=end + 1,
                    is_parallel=any("#pragma omp" in item for item in content[index : end + 1]),
                )
            )
    return result


def symbol_matches(name: str, symbol: str) -> bool:
    return name == symbol or name.rsplit("::", 1)[-1] == symbol.rsplit("::", 1)[-1]


def function_calls(content: list[str], function: FunctionRange) -> set[str]:
    calls: set[str] = set()
    for line in content[function.start - 1 : function.end]:
        for match in _CALL.finditer(line):
            call = match.group("name")
            if call not in {function.name, "if", "for", "while", "switch", "return", "sizeof"}:
                calls.add(call)
    return calls


def declarations(content: Iterable[str]) -> set[str]:
    names: set[str] = set()
    for line in content:
        match = _DECL.search(line)
        if match:
            names.add(match.group("name"))
    return names


def nearest_function(all_functions: list[FunctionRange], path: Path, line: int) -> Optional[FunctionRange]:
    return next((item for item in all_functions if item.file == path and item.start <= line <= item.end), None)


def relative(project_path: str, path: Path) -> str:
    try:
        return str(path.relative_to(project_path))
    except ValueError:
        return str(path)

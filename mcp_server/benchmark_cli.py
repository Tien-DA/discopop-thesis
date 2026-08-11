"""One-command launcher for the DiscoPoP MCP benchmark.

It discovers an already analysed DiscoPoP project, derives one reproducible
dependency task from its real output, and invokes the benchmark runner.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SOURCE_SUFFIXES = {".c", ".cc", ".cp", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
_TEXT_OUTPUT_SUFFIXES = {".json", ".xml", ".txt", ".patch", ".dot"}


def _runner() -> Any:
    runner_path = Path(__file__).resolve().parents[1] / "benchmark" / "mcp_token_benchmark" / "benchmark.py"
    if not runner_path.is_file():
        raise RuntimeError("Benchmark runner is unavailable. Install DiscoPoP from its source checkout with pip install -e ./mcp_server.")
    spec = importlib.util.spec_from_file_location("discopop_mcp_benchmark", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the benchmark runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mapped_sources(project: Path) -> list[Path]:
    mapping = project / ".discopop" / "FileMapping.txt"
    if not mapping.is_file():
        raise RuntimeError("Missing .discopop/FileMapping.txt. Run DiscoPoP analysis before benchmarking.")
    sources = []
    for line in mapping.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split("\t", 1)
        if len(fields) == 2:
            path = Path(fields[1]).resolve()
            if path.is_file() and path.suffix.lower() in _SOURCE_SUFFIXES:
                sources.append(path)
    if not sources:
        raise RuntimeError("FileMapping.txt contains no readable C/C++ source files.")
    return sorted(set(sources))


def _raw_output(project: Path) -> list[Path]:
    root = project / ".discopop"
    files = [path.resolve() for path in root.rglob("*") if path.is_file() and path.suffix.lower() in _TEXT_OUTPUT_SUFFIXES
             and "mcp_token_benchmark" not in path.parts and "mcp_server" not in path.parts]
    if not files:
        raise RuntimeError("No textual DiscoPoP artefacts were found under .discopop.")
    return sorted(files)


def _line_count(path: Path) -> int:
    return max(1, len(path.read_text(encoding="utf-8", errors="replace").splitlines()))


def _content_json(result: Any) -> dict[str, Any]:
    for item in result.get("content", []) if isinstance(result, dict) else []:
        if item.get("type") == "text":
            try:
                value = json.loads(item.get("text", ""))
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue
    return {}


def _oracle(data: dict[str, Any]) -> dict[str, Any]:
    """Create transparent checks from real dependency facts returned by DiscoPoP."""
    dependencies = data.get("dependencies", {})
    facts = [dep for group in dependencies.values() if isinstance(group, list) for dep in group]
    if not facts:
        return {"must_contain": ["no dependencies"]}
    required: list[str] = []
    for fact in facts:
        for value in (fact.get("var_name"), fact.get("dep_type")):
            if isinstance(value, str) and value and value not in required:
                required.append(value)
            if len(required) == 3:
                return {"must_contain": required}
    return {"must_contain": required or ["dependencies"]}


def _detect_model(base_url: str, api_key: str | None) -> str:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    request = urllib.request.Request(f"{base_url.rstrip('/')}/models", headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        models = json.loads(response.read().decode("utf-8")).get("data", [])
    if not models or not models[0].get("id"):
        raise RuntimeError("No model is loaded in LM Studio. Load a tool-capable model, then retry.")
    return str(models[0]["id"])


def _build_case(project: Path, runner: Any) -> dict[str, Any]:
    sources = _mapped_sources(project)
    raw_output = _raw_output(project)
    tool_name = "get_data_dependencies" if (project / ".discopop" / "explorer" / "detection_result_dump.json").is_file() else "get_static_data_dependencies"
    target, end_line = sources[0], _line_count(sources[0])
    arguments = {"project_path": str(project), "file_path": str(target), "start_line": 1, "end_line": end_line}
    with runner.MCPClient(["discopop_mcp_server"], str(project), 120) as mcp:
        data = _content_json(mcp.call(tool_name, arguments))
    if data.get("status") != "success":
        raise RuntimeError(f"DiscoPoP query failed: {data.get('message', data)}")
    expected = _oracle(data)
    expected["tool_calls"] = [{"name": tool_name, "arguments": arguments}]
    return {
        "id": f"auto-dependencies-{target.name}",
        "question": (f"Analyse dependencies in {target.name}, lines 1-{end_line}. State whether there are dependencies; "
                     "if there are, name the relevant variables and dependency types. If none exist, say exactly 'no dependencies'."),
        "source_paths": [str(path) for path in sources], "discopop_output_paths": [str(path) for path in raw_output],
        "expected": expected,
        "mcp": {"allowed_tools": [tool_name], "command": ["discopop_mcp_server"], "timeout_seconds": 120},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the DiscoPoP MCP token benchmark for an analysed project.")
    parser.add_argument("project", nargs="?", default=".", type=Path, help="Project directory (default: current directory)")
    parser.add_argument("--model", help="LM Studio model ID; auto-detected when omitted")
    parser.add_argument("--base-url", default="http://localhost:1234/v1", help="LM Studio/OpenAI-compatible base URL")
    parser.add_argument("--api-key", help="Optional local-server bearer token")
    parser.add_argument("--max-tool-steps", type=int, default=6)
    args = parser.parse_args(argv)

    project = args.project.resolve()
    if not project.is_dir():
        parser.error(f"Project directory does not exist: {project}")
    runner = _runner()
    model = args.model or _detect_model(args.base_url, args.api_key)
    output = project / ".discopop" / "mcp_token_benchmark" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"cases": [_build_case(project, runner)]}
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return runner.main([str(manifest_path), "--model", model, "--base-url", args.base_url, "--repo-root", str(project),
                        "--output-dir", str(output), "--max-tool-steps", str(args.max_tool_steps)] +
                       (["--api-key", args.api_key] if args.api_key else []))


if __name__ == "__main__":
    raise SystemExit(main())

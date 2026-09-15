import ast
import json
import os
import shlex
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class LocalMCPServer:
    name: str
    executable: str
    command_env: str
    executable_env: str
    source_entrypoint: Path
    tool_directory: Path

    def resolve_command(
        self,
        workspace: Path,
    ) -> Optional[list[str]]:
        configured = os.environ.get(self.command_env)
        if configured:
            return shlex.split(configured)

        executable = os.environ.get(self.executable_env)
        if executable:
            return [executable]

        executable = shutil.which(self.executable)
        if executable:
            return [executable]

        venv_executable = (
            Path(sys.executable).parent
            / self.executable
        )
        if venv_executable.is_file():
            return [str(venv_executable)]

        if self.source_entrypoint.is_file():
            return self._write_source_wrapper(workspace)

        return None

    def discover_tool_names(self) -> set[str]:
        """
        Discover MCP tool names from the local server sources without importing
        the MCP package. This keeps usage accounting in sync with the server.
        """

        tool_names: set[str] = set()

        if not self.tool_directory.is_dir():
            return tool_names

        for path in self.tool_directory.glob("*.py"):
            if path.name.startswith("test_") or path.name in {
                "__init__.py",
                "helpers.py",
            }:
                continue

            try:
                tree = ast.parse(
                    path.read_text(encoding="utf-8"),
                    filename=str(path),
                )
            except (OSError, SyntaxError):
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                if not any(
                    isinstance(target, ast.Name)
                    and target.id == "TOOL"
                    for target in node.targets
                ):
                    continue
                if not isinstance(node.value, ast.Call):
                    continue

                for keyword in node.value.keywords:
                    if (
                        keyword.arg == "name"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        tool_names.add(keyword.value.value)

        return tool_names

    def temporary_files(
        self,
        workspace: Path,
    ) -> list[Path]:
        return [
            workspace / f".opencode_{self.name}.py",
        ]

    def _write_source_wrapper(
        self,
        workspace: Path,
    ) -> list[str]:
        wrapper = self.temporary_files(workspace)[0]
        package_root = self.source_entrypoint.parents[1]
        wrapper.write_text(
            "\n".join(
                [
                    "import runpy",
                    "import sys",
                    f"sys.path.insert(0, {str(package_root)!r})",
                    f"server = {str(self.source_entrypoint)!r}",
                    "sys.argv = [server] + sys.argv[1:]",
                    "runpy.run_path(server, run_name='__main__')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return [sys.executable, str(wrapper)]


class OpenCodeClient:
    """Client for running OpenCode as a coding agent."""

    def __init__(
        self,
        model: str,
        mcp_server: Optional[LocalMCPServer] = None,
    ):
        self.model = model
        self.mcp_server = (
            mcp_server
            if mcp_server is not None
            else self._default_discopop_mcp_server()
        )
        self.mcp_tool_names = self.mcp_server.discover_tool_names()

    @staticmethod
    def _default_discopop_mcp_server() -> LocalMCPServer:
        repo_root = Path(__file__).resolve().parents[1]
        return LocalMCPServer(
            name="discopop_mcp_server",
            executable="discopop_mcp_server",
            command_env="DISCOPOP_MCP_COMMAND",
            executable_env="DISCOPOP_MCP_SERVER",
            source_entrypoint=repo_root / "mcp_server" / "server.py",
            tool_directory=repo_root / "mcp_server" / "tools",
        )

    def _write_project_config(
        self,
        workspace: Path,
        mcp_enabled: bool,
    ) -> Path:
        """
        Create a temporary project-level OpenCode configuration.

        This overrides the global MCP configuration for this benchmark
        workspace without modifying ~/.config/opencode/opencode.jsonc.
        """

        config_path = workspace / "opencode.json"
        mcp_command = self.mcp_server.resolve_command(
            workspace
        )

        if mcp_enabled and mcp_command is None:
            raise RuntimeError(
                "MCP mode requested, but the DiscoPoP MCP server could not "
                "be found. Install discopop_mcp_server, set "
                f"{self.mcp_server.command_env}, or run the benchmark from "
                "a checkout that contains mcp_server/server.py."
            )

        config = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                self.mcp_server.name: {
                    "type": "local",
                    "command": mcp_command or [self.mcp_server.executable],
                    "enabled": mcp_enabled,
                }
            },
        }

        with config_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                config,
                file,
                indent=2,
            )

        return config_path

    def _extract_mcp_usage(
        self,
        raw_events,
    ) -> Dict[str, Any]:
        """
        Inspect OpenCode events and determine whether MCP tools
        were actually used.

        This is intentionally based on the OpenCode event stream
        rather than merely checking whether MCP was enabled.
        """

        mcp_calls = []
        tools = []

        for event in raw_events:

            if event.get("type") != "tool_use":
                continue

            part = event.get("part", {})

            tool_name = part.get("tool")

            if not tool_name:
                continue

            tool_name = str(tool_name)

            # DiscoPoP MCP tools may contain "discopop" or "mcp"
            # in their tool name. Keep this detection broad for now.
            if (
                "discopop" in tool_name.lower()
                or "mcp" in tool_name.lower()
                or tool_name in self.mcp_tool_names
            ):
                mcp_calls.append(event)

                if tool_name not in tools:
                    tools.append(tool_name)

        return {
            "used": len(mcp_calls) > 0,
            "tool_calls": len(mcp_calls),
            "tools": tools,
        }

    def run(
        self,
        prompt: str,
        workspace: Path,
        mcp_enabled: bool = False,
        events_file: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Run OpenCode inside the benchmark workspace.

        Each invocation is an independent OpenCode run.
        A unique benchmark invocation ID is attached to the result
        for session/isolation tracking.
        """

        config_path = self._write_project_config(
            workspace=workspace,
            mcp_enabled=mcp_enabled,
        )

        invocation_id = uuid.uuid4().hex

        command = [
            "opencode",
            "run",
            "--format",
            "json",
            "--auto",
            "--model",
            self.model,
            "--dir",
            str(workspace),
            prompt,
        ]

        print("OpenCode invocation:")
        print(f"Invocation ID: {invocation_id}")
        print(f"MCP enabled:   {mcp_enabled}")

        print("OpenCode command:")
        print(" ".join(command))

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"OpenCode failed with exit code "
                    f"{result.returncode}\n\n"
                    f"stdout:\n{result.stdout}\n\n"
                    f"stderr:\n{result.stderr}"
                )

            output_text = []

            usage = {
                "steps": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
            }

            raw_events = []

            for line in result.stdout.splitlines():

                if not line.strip():
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                raw_events.append(event)

                if event.get("type") == "text":

                    text = (
                        event
                        .get("part", {})
                        .get("text", "")
                    )

                    if text:
                        output_text.append(text)

                elif event.get("type") == "step_finish":

                    tokens = (
                        event
                        .get("part", {})
                        .get("tokens", {})
                    )

                    usage["steps"] += 1

                    usage["input_tokens"] += (
                        tokens.get("input", 0)
                    )

                    usage["output_tokens"] += (
                        tokens.get("output", 0)
                    )

                    usage["total_tokens"] += (
                        tokens.get("total", 0)
                    )

                    usage["reasoning_tokens"] += (
                        tokens.get("reasoning", 0)
                    )

                    cache = tokens.get(
                        "cache",
                        {},
                    )

                    usage["cache_read_tokens"] += (
                        cache.get("read", 0)
                    )

                    usage["cache_write_tokens"] += (
                        cache.get("write", 0)
                    )

            mcp_usage = self._extract_mcp_usage(
                raw_events
            )

            if events_file is not None:

                events_file.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                with events_file.open(
                    "w",
                    encoding="utf-8",
                ) as file:

                    for event in raw_events:

                        file.write(
                            json.dumps(
                                event,
                                ensure_ascii=False,
                            )
                            + "\n"
                        )

            return {
                "output": "\n".join(output_text),
                "stderr": result.stderr,
                "returncode": result.returncode,

                "usage": usage,

                "mcp_enabled": mcp_enabled,
                "mcp_usage": mcp_usage,

                "invocation_id": invocation_id,

                "events_file": (
                    str(events_file)
                    if events_file
                    else None
                ),
            }

        finally:

            # The configuration must never become part of
            # the generated Git patch.

            if config_path.exists():
                config_path.unlink()

            for path in self.mcp_server.temporary_files(
                workspace
            ):
                if path.exists():
                    path.unlink()

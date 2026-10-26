"""
Claude Code Client.

Alternative coding agent for the benchmark, driven through the user's own
``claude`` command line tool (``claude -p --output-format stream-json``).
Authentication and the default model come from the user's Claude Code setup.

The class mirrors ``OpenCodeClient``: same ``run`` signature and result
structure, so the benchmark runner can use either agent.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from llm.opencode import LocalMCPServer, OpenCodeClient


class ClaudeCodeClient:
    """Client for running Claude Code as the benchmark coding agent."""

    # Claude Code effort levels; "off" omits the flag.
    EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

    SETUP_TOOLS = ("prepare_project_analysis",)

    def __init__(
        self,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        mcp_server: Optional[LocalMCPServer] = None,
    ) -> None:
        # None means: the default model of the user's Claude Code setup.
        self.model = model if model is not None else os.environ.get("BENCHMARK_CLAUDE_MODEL")

        self.reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else os.environ.get("BENCHMARK_REASONING_EFFORT", "medium")
        )

        self.mcp_server = (
            mcp_server if mcp_server is not None else OpenCodeClient._default_discopop_mcp_server()
        )
        self.mcp_tool_names = self.mcp_server.discover_tool_names()

    # ------------------------------------------------------------------
    # MCP CONFIGURATION
    # ------------------------------------------------------------------

    def _write_mcp_config(self, workspace: Path, mcp_enabled: bool) -> Path:
        """Write the temporary MCP config; empty unless MCP mode is requested."""
        servers: dict[str, Any] = {}

        if mcp_enabled:
            command = self.mcp_server.resolve_command(workspace)
            if command is None:
                raise RuntimeError(
                    "MCP mode requested, but the DiscoPoP MCP server could not be found.\n\n"
                    "Expected one of:\n"
                    f"  - {self.mcp_server.command_env}\n"
                    f"  - {self.mcp_server.executable_env}\n"
                    f"  - {self.mcp_server.executable} on PATH\n"
                    f"  - {self.mcp_server.source_entrypoint}"
                )
            servers[self.mcp_server.name] = {
                "type": "stdio",
                "command": command[0],
                "args": list(command[1:]),
            }

        config_path = workspace / ".claude_mcp.json"
        config_path.write_text(json.dumps({"mcpServers": servers}, indent=2), encoding="utf-8")
        return config_path

    # ------------------------------------------------------------------
    # EVENT HELPERS
    # ------------------------------------------------------------------

    def _is_mcp_tool(self, tool_name: str) -> bool:
        normalized = tool_name.lower()
        short_name = tool_name.rsplit("__", 1)[-1]
        return (
            tool_name in self.mcp_tool_names
            or short_name in self.mcp_tool_names
            or "discopop" in normalized
            or tool_name.startswith("mcp__")
        )

    def _is_setup_tool(self, tool_name: str) -> bool:
        return any(tool_name.endswith(tool) for tool in self.SETUP_TOOLS)

    # ------------------------------------------------------------------
    # RUN CLAUDE CODE
    # ------------------------------------------------------------------

    def run(
        self,
        prompt: str,
        workspace: Path,
        mcp_enabled: bool = False,
        events_file: Optional[Path] = None,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run one Claude Code invocation in ``workspace``."""

        workspace = Path(workspace).resolve()
        workspace.mkdir(parents=True, exist_ok=True)

        mcp_config_path = self._write_mcp_config(workspace, mcp_enabled)
        invocation_id = uuid.uuid4().hex

        # --strict-mcp-config: never leak MCP servers of the user's own
        # configuration into the benchmark, in particular not into the
        # direct and full_discopop modes.
        command = [
            "claude",
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--mcp-config",
            str(mcp_config_path),
            "--strict-mcp-config",
        ]
        if self.model:
            command.extend(["--model", self.model])
        if self.reasoning_effort in self.EFFORT_LEVELS:
            command.extend(["--effort", self.reasoning_effort])
        if session_id:
            command.extend(["--resume", session_id])
        command.append(prompt)

        print()
        print("=" * 70)
        print("Claude Code invocation")
        print("=" * 70)
        print(f"Invocation ID: {invocation_id}")
        print(f"Model:         {self.model or '(Claude Code default)'}")
        print(f"Reasoning:     {self.reasoning_effort}")
        print(f"MCP enabled:   {mcp_enabled}")
        print(f"Workspace:     {workspace}")
        print()
        print("Claude command:")
        print(" ".join(shlex.quote(part) for part in command))

        try:
            start_time = time.perf_counter()

            process = subprocess.Popen(
                command,
                cwd=workspace,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                bufsize=1,
            )

            stderr_lines: list[str] = []

            def collect_stderr() -> None:
                if process.stderr is not None:
                    stderr_lines.extend(process.stderr)

            stderr_thread = threading.Thread(target=collect_stderr)
            stderr_thread.start()

            raw_events: list[dict[str, Any]] = []
            stdout_lines: list[str] = []
            output_text: list[str] = []
            mcp_counts: dict[str, int] = {}
            returned_session_id: Optional[str] = None
            result_event: dict[str, Any] = {}

            # One assistant message (= one inference step) may be streamed as
            # several events with the same id; keep one record per id.
            steps: dict[str, dict[str, Any]] = {}

            if process.stdout is None:
                raise RuntimeError("Claude Code stdout pipe was not created.")

            for line in process.stdout:
                stdout_lines.append(line)
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue

                raw_events.append(event)

                if isinstance(event.get("session_id"), str):
                    returned_session_id = event["session_id"]

                event_type = event.get("type")

                if event_type == "result":
                    result_event = event
                    continue

                if event_type != "assistant":
                    continue

                message = event.get("message")
                if not isinstance(message, dict):
                    continue

                message_id = str(message.get("id") or f"anonymous_{len(steps)}")
                step = steps.get(message_id)
                if step is None:
                    step = {"usage": {}, "setup": False, "task_mcp": False, "time": 0.0}
                    steps[message_id] = step
                    print(f"[Claude] Step {len(steps)}")
                if isinstance(message.get("usage"), dict):
                    step["usage"] = message["usage"]
                step["time"] = time.perf_counter()

                for block in message.get("content") or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text" and block.get("text"):
                        output_text.append(block["text"])
                    elif block.get("type") == "tool_use":
                        tool_name = str(block.get("name", ""))
                        if not self._is_mcp_tool(tool_name):
                            continue
                        mcp_counts[tool_name] = mcp_counts.get(tool_name, 0) + 1
                        if self._is_setup_tool(tool_name):
                            step["setup"] = True
                        else:
                            step["task_mcp"] = True

            returncode = process.wait()
            stderr_thread.join()
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            # ----------------------------------------------------------
            # TOKEN USAGE
            # ----------------------------------------------------------

            usage = OpenCodeClient._empty_usage()
            warm_usage = OpenCodeClient._empty_usage() if mcp_enabled else None

            step_list = list(steps.values())
            step_usages: list[tuple[int, int, int, int, int, int]] = []
            for step in step_list:
                raw = step["usage"]
                step_input = int(raw.get("input_tokens") or 0)
                step_output = int(raw.get("output_tokens") or 0)
                cache_read = int(raw.get("cache_read_input_tokens") or 0)
                cache_write = int(raw.get("cache_creation_input_tokens") or 0)
                step_usages.append(
                    (
                        step_input,
                        step_output,
                        step_input + step_output + cache_read + cache_write,
                        0,  # Claude Code does not report reasoning tokens separately
                        cache_read,
                        cache_write,
                    )
                )
            for step_usage in step_usages:
                OpenCodeClient._record_step_usage(usage, *step_usage)

            # ----------------------------------------------------------
            # WARM USAGE (after the MCP setup step)
            # ----------------------------------------------------------

            warm_start_index = 0
            warm_start_time = start_time
            setup_used = False
            task_mcp_used = False
            for index, step in enumerate(step_list):
                if step["setup"]:
                    setup_used = True
                    warm_start_index = index + 1
                    warm_start_time = step["time"]
                if step["task_mcp"]:
                    task_mcp_used = True

            warm_started = mcp_enabled and setup_used and task_mcp_used
            if warm_started and warm_usage is not None:
                for step_usage in step_usages[warm_start_index:]:
                    OpenCodeClient._record_step_usage(warm_usage, *step_usage)

            warm_latency_seconds = time.perf_counter() - warm_start_time if warm_started else None

            # ----------------------------------------------------------
            # SAVE RAW EVENTS
            # ----------------------------------------------------------

            if events_file is not None:
                events_file = Path(events_file)
                events_file.parent.mkdir(parents=True, exist_ok=True)
                with events_file.open("w", encoding="utf-8") as file:
                    for event in raw_events:
                        file.write(json.dumps(event, ensure_ascii=False) + "\n")

            if returncode != 0 or result_event.get("is_error"):
                raise RuntimeError(
                    f"Claude Code failed with exit code {returncode}\n\n"
                    f"result:\n{result_event.get('result', '')}\n\n"
                    f"stdout:\n{stdout}\n\n"
                    f"stderr:\n{stderr}"
                )

            mcp_usage: dict[str, Any] = {
                "used": sum(mcp_counts.values()) > 0,
                "tool_calls": sum(mcp_counts.values()),
                "tools": dict(sorted(mcp_counts.items())),
            }

            print()
            print("Claude Code finished.")
            print(f"Steps:          {usage['steps']}")
            print(f"Input tokens:   {usage['input_tokens']:,}")
            print(f"Output tokens:  {usage['output_tokens']:,}")
            print(f"Total tokens:   {usage['total_tokens']:,}")
            print(f"MCP used:       {mcp_usage['used']}")
            print(f"MCP calls:      {mcp_usage['tool_calls']}")
            for tool_name, count in mcp_usage["tools"].items():
                print(f"  {tool_name}: {count}")

            return {
                "output": str(result_event.get("result") or "\n".join(output_text)),
                "stderr": stderr,
                "returncode": returncode,
                "usage": usage,
                "warm_usage": warm_usage if warm_started else None,
                "warm_latency_seconds": warm_latency_seconds,
                "mcp_enabled": mcp_enabled,
                "mcp_usage": mcp_usage,
                "invocation_id": invocation_id,
                "session_id": returned_session_id or session_id,
                "events_file": str(events_file) if events_file is not None else None,
                "total_cost_usd": result_event.get("total_cost_usd"),
            }

        finally:
            if mcp_config_path.exists():
                mcp_config_path.unlink()
            for path in self.mcp_server.temporary_files(workspace):
                if path.exists():
                    path.unlink()

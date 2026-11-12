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
import uuid
from pathlib import Path
from typing import Any, Optional

from llm.opencode import LocalMCPServer, OpenCodeClient


def summarize_mcp_availability(
    init_event: dict[str, Any], server_name: str, enabled: bool, tool_calls: int
) -> dict[str, Any]:
    """Separate configured MCP from evidence of availability in Claude's init.

    Pending servers and deferred tool discovery are inconclusive: init is a
    startup snapshot, not a final connection-status query.
    """
    server = next(
        (item for item in init_event.get("mcp_servers", [])
         if isinstance(item, dict) and item.get("name") == server_name),
        {},
    )
    prefix = f"mcp__{server_name}__"
    advertised_tools = sorted(
        name for name in init_event.get("tools", [])
        if isinstance(name, str) and name.startswith(prefix)
    )
    status = server.get("status", "not_reported")
    if not enabled:
        diagnosis = "disabled"
    elif tool_calls:
        diagnosis = "tool_calls_observed"
    elif status in {"failed", "needs-auth", "disabled"}:
        diagnosis = "server_unavailable_at_init"
    elif status == "connected" and advertised_tools:
        diagnosis = "available_but_not_called"
    else:
        diagnosis = "availability_unconfirmed"
    return {
        "server": server_name,
        "initial_status": status,
        "advertised_tools": advertised_tools,
        "diagnosis": diagnosis,
    }


def summarize_claude_usage(
    steps: dict[str, dict[str, Any]], result_event: dict[str, Any]
) -> dict[str, int]:
    """Prefer result totals: assistant output counts can be placeholders.

    Result usage covers this main-agent turn. Session-wide modelUsage may
    contain earlier turns, so adding it on resumed attempts would double count.
    """
    usage = OpenCodeClient._empty_usage()
    for step in steps.values():
        raw = step["usage"]
        uncached = int(raw.get("input_tokens") or 0)
        output = int(raw.get("output_tokens") or 0)
        read = int(raw.get("cache_read_input_tokens") or 0)
        write = int(raw.get("cache_creation_input_tokens") or 0)
        OpenCodeClient._record_step_usage(
            usage, uncached, output, uncached + output + read + write, 0, read, write)
    raw = result_event.get("usage")
    if isinstance(raw, dict) and any(key in raw for key in (
        "input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"
    )):
        uncached = int(raw.get("input_tokens", usage["uncached_input_tokens"]) or 0)
        output = int(raw.get("output_tokens", usage["output_tokens"]) or 0)
        read = int(raw.get("cache_read_input_tokens", usage["cache_read_tokens"]) or 0)
        write = int(raw.get("cache_creation_input_tokens", usage["cache_write_tokens"]) or 0)
        # Replace message estimates; do not add the result on top of them.
        usage.update(
            uncached_input_tokens=uncached,
            input_tokens=uncached + read + write,
            output_tokens=output,
            total_tokens=uncached + read + write + output,
            cache_read_tokens=read,
            cache_write_tokens=write,
        )
    return usage


class ClaudeCodeClient:
    """Client for running Claude Code as the benchmark coding agent."""

    # Claude Code effort levels; "off" omits the flag.
    EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

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
            init_event: dict[str, Any] = {}
            seen_tool_ids: set[str] = set()

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

                if event_type == "system" and event.get("subtype") == "init":
                    init_event = event
                    availability = summarize_mcp_availability(
                        init_event, self.mcp_server.name, mcp_enabled, 0
                    )
                    print(f"[Claude] MCP initial status: {availability['initial_status']}")
                    print(f"[Claude] MCP advertised tools: {len(availability['advertised_tools'])}")
                    continue

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
                    step = {"usage": {}}
                    steps[message_id] = step
                    print(f"[Claude] Step {len(steps)}")
                if isinstance(message.get("usage"), dict):
                    step["usage"].update(message["usage"])

                for block in message.get("content") or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text" and block.get("text"):
                        output_text.append(block["text"])
                    elif block.get("type") == "tool_use":
                        tool_name = str(block.get("name", ""))
                        tool_id = block.get("id")
                        if isinstance(tool_id, str):
                            if tool_id in seen_tool_ids:
                                continue
                            seen_tool_ids.add(tool_id)
                        print(f"[Claude] Tool: {tool_name}")
                        if not self._is_mcp_tool(tool_name):
                            continue
                        mcp_counts[tool_name] = mcp_counts.get(tool_name, 0) + 1

            returncode = process.wait()
            stderr_thread.join()
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            # ----------------------------------------------------------
            # TOKEN USAGE
            # ----------------------------------------------------------

            usage = summarize_claude_usage(steps, result_event)

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
            mcp_availability = summarize_mcp_availability(
                init_event, self.mcp_server.name, mcp_enabled, mcp_usage["tool_calls"]
            )

            print()
            print("Claude Code finished.")
            print(f"Steps:          {usage['steps']}")
            print(f"Input tokens:   {usage['input_tokens']:,}")
            print(f"Output tokens:  {usage['output_tokens']:,}")
            print(f"Total tokens:   {usage['total_tokens']:,}")
            print(f"MCP used:       {mcp_usage['used']}")
            print(f"MCP calls:      {mcp_usage['tool_calls']}")
            if mcp_enabled:
                print(f"MCP diagnosis:  {mcp_availability['diagnosis']}")
            for tool_name, count in mcp_usage["tools"].items():
                print(f"  {tool_name}: {count}")

            return {
                "output": str(result_event.get("result") or "\n".join(output_text)),
                "stderr": stderr,
                "returncode": returncode,
                "usage": usage,
                "mcp_enabled": mcp_enabled,
                "mcp_usage": mcp_usage,
                "mcp_availability": mcp_availability,
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

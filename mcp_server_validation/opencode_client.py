import json
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


class OpenCodeClient:
    """Client for running OpenCode as a coding agent."""

    DISCOPOP_MCP_COMMAND = (
        "/home/dinhtienvu/TU_Darmstadt/6.Semester/Thesis/"
        "discopop-thesis/venv/bin/discopop_mcp_server"
    )

    def __init__(self, model: str):
        self.model = model

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

        config = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "discopop_mcp_server": {
                    "type": "local",
                    "command": [
                        self.DISCOPOP_MCP_COMMAND
                    ],
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

    @staticmethod
    def _extract_mcp_usage(
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
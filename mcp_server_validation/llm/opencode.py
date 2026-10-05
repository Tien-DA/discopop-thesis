"""
OpenCode Client.

OpenCode is the actual coding agent used by the benchmark.

Responsibilities of OpenCode:
    - read files
    - edit files
    - execute shell commands
    - reason about the task
    - interact with MCP tools

Responsibilities of this class:
    - configure OpenCode
    - configure the LLM provider
    - enable/disable MCP
    - start OpenCode
    - collect JSON events
    - collect token usage
    - count MCP tool calls
"""

from __future__ import annotations

import ast
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# ======================================================================
# LOCAL MCP SERVER
# ======================================================================


@dataclass(frozen=True)
class LocalMCPServer:
    """
    Description of a local DiscoPoP MCP server.
    """

    name: str

    executable: str

    command_env: str

    executable_env: str

    source_entrypoint: Path

    tool_directory: Path

    # ------------------------------------------------------------------
    # RESOLVE MCP SERVER COMMAND
    # ------------------------------------------------------------------

    def resolve_command(
        self,
        workspace: Path,
    ) -> Optional[list[str]]:
        """
        Resolve the command used to start the MCP server.

        Resolution order:

        1. Explicit command environment variable.
        2. Explicit executable environment variable.
        3. Executable available on PATH.
        4. Executable inside current virtual environment.
        5. Local server.py source wrapper.
        """

        # --------------------------------------------------------------
        # 1. Explicit command
        # --------------------------------------------------------------

        configured_command = os.environ.get(
            self.command_env
        )

        if configured_command:
            return shlex.split(
                configured_command
            )

        # --------------------------------------------------------------
        # 2. Explicit executable
        # --------------------------------------------------------------

        configured_executable = os.environ.get(
            self.executable_env
        )

        if configured_executable:
            return [
                configured_executable
            ]

        # --------------------------------------------------------------
        # 3. PATH
        # --------------------------------------------------------------

        executable = shutil.which(
            self.executable
        )

        if executable:
            return [
                executable
            ]

        # --------------------------------------------------------------
        # 4. Current Python virtual environment
        # --------------------------------------------------------------

        venv_executable = (
            Path(sys.executable).parent
            / self.executable
        )

        if venv_executable.is_file():
            return [
                str(venv_executable)
            ]

        # --------------------------------------------------------------
        # 5. Local source entrypoint
        # --------------------------------------------------------------

        if self.source_entrypoint.is_file():
            return self._write_source_wrapper(
                workspace
            )

        return None

    # ------------------------------------------------------------------
    # DISCOVER TOOL NAMES
    # ------------------------------------------------------------------

    def discover_tool_names(self) -> set[str]:
        """
        Discover MCP tool names from the local MCP source.

        This method does NOT import or execute the MCP server.

        It only parses Python source code with AST so that we can
        later identify MCP calls in the OpenCode event stream.
        """

        tool_names: set[str] = set()

        if not self.tool_directory.is_dir():
            return tool_names

        for path in self.tool_directory.glob("*.py"):

            if path.name.startswith("test_"):
                continue

            if path.name in {
                "__init__.py",
                "helpers.py",
            }:
                continue

            try:
                source = path.read_text(
                    encoding="utf-8"
                )

                tree = ast.parse(
                    source,
                    filename=str(path),
                )

            except (
                OSError,
                SyntaxError,
            ):
                continue

            for node in ast.walk(tree):

                if not isinstance(
                    node,
                    ast.Assign,
                ):
                    continue

                # Look for:
                #
                # TOOL = ...
                #

                is_tool_assignment = any(
                    isinstance(
                        target,
                        ast.Name,
                    )
                    and target.id == "TOOL"
                    for target in node.targets
                )

                if not is_tool_assignment:
                    continue

                if not isinstance(
                    node.value,
                    ast.Call,
                ):
                    continue

                for keyword in node.value.keywords:

                    if keyword.arg != "name":
                        continue

                    if not isinstance(
                        keyword.value,
                        ast.Constant,
                    ):
                        continue

                    if not isinstance(
                        keyword.value.value,
                        str,
                    ):
                        continue

                    tool_names.add(
                        keyword.value.value
                    )

        return tool_names

    # ------------------------------------------------------------------
    # TEMPORARY FILES
    # ------------------------------------------------------------------

    def temporary_files(
        self,
        workspace: Path,
    ) -> list[Path]:
        """
        Return temporary files created by this MCP configuration.
        """

        return [
            workspace
            / f".opencode_{self.name}.py"
        ]

    # ------------------------------------------------------------------
    # CREATE SOURCE WRAPPER
    # ------------------------------------------------------------------

    def _write_source_wrapper(
        self,
        workspace: Path,
    ) -> list[str]:
        """
        Create a temporary Python wrapper for server.py.
        """

        wrapper = (
            self.temporary_files(
                workspace
            )[0]
        )

        package_root = (
            self.source_entrypoint.parents[1]
        )

        wrapper.write_text(
            "\n".join(
                [
                    "import runpy",
                    "import sys",
                    (
                        "sys.path.insert("
                        "0, "
                        f"{str(package_root)!r}"
                        ")"
                    ),
                    (
                        "server = "
                        f"{str(self.source_entrypoint)!r}"
                    ),
                    (
                        "sys.argv = "
                        "[server] + sys.argv[1:]"
                    ),
                    (
                        "runpy.run_path("
                        "server, "
                        "run_name='__main__'"
                        ")"
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )

        return [
            sys.executable,
            str(wrapper),
        ]


# ======================================================================
# OPENCODE CLIENT
# ======================================================================


class OpenCodeClient:
    """
    Client for running OpenCode as the benchmark coding agent.
    """

    # ==================================================================
    # LLM CONFIGURATION
    # ==================================================================

    # These values are intentionally hardcoded for now.
    #
    # Later:
    #     user input
    #
    # can replace this configuration.

    SERVER_URL = "http://localhost:18000/v1"

    API_KEY = "ppkitestapikey"

    MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct"

    PROVIDER = "HPC_Lab"

    # ==================================================================
    # INITIALIZATION
    # ==================================================================

    def __init__(
        self,
        model: Optional[str] = None,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        mcp_server: Optional[LocalMCPServer] = None,
    ) -> None:

        self.model = (
            model
            if model is not None
            else self.MODEL
        )

        self.server_url = (
            server_url
            if server_url is not None
            else self.SERVER_URL
        )

        self.api_key = (
            api_key
            if api_key is not None
            else self.API_KEY
        )

        self.mcp_server = (
            mcp_server
            if mcp_server is not None
            else self._default_discopop_mcp_server()
        )

        # Discover the actual MCP function names.
        self.mcp_tool_names = (
            self.mcp_server.discover_tool_names()
        )

    # ==================================================================
    # DEFAULT DISCOPOP MCP SERVER
    # ==================================================================

    @staticmethod
    def _default_discopop_mcp_server() -> LocalMCPServer:
        """
        Return the default DiscoPoP MCP server configuration.
        """

        repo_root = (
            Path(__file__).resolve().parents[1]
        )

        return LocalMCPServer(
            name="discopop_mcp_server",

            executable="discopop_mcp_server",

            command_env="DISCOPOP_MCP_COMMAND",

            executable_env="DISCOPOP_MCP_SERVER",

            source_entrypoint=(
                repo_root
                / "mcp_server"
                / "server.py"
            ),

            tool_directory=(
                repo_root
                / "mcp_server"
                / "tools"
            ),
        )

    # ==================================================================
    # OPEN CODE CONFIGURATION
    # ==================================================================

    def _write_project_config(
            self,
            workspace: Path,
            mcp_enabled: bool,
    ) -> Path:
        """
        Create a temporary project-level OpenCode configuration.

        The provider configuration intentionally matches the previously
        working OpenCode configuration used with the university LLM server.
        """

        config_path = workspace / "opencode.json"

        # --------------------------------------------------------------
        # Resolve MCP command
        # --------------------------------------------------------------

        mcp_command = self.mcp_server.resolve_command(
            workspace
        )

        if mcp_enabled and mcp_command is None:
            raise RuntimeError(
                "MCP mode requested, but the DiscoPoP MCP server "
                "could not be found.\n\n"
                "Expected one of:\n"
                f"  - {self.mcp_server.command_env}\n"
                f"  - {self.mcp_server.executable_env}\n"
                f"  - {self.mcp_server.executable} on PATH\n"
                f"  - {self.mcp_server.source_entrypoint}"
            )

        # --------------------------------------------------------------
        # This MUST match the known-working global OpenCode config.
        # --------------------------------------------------------------

        config = {
            "$schema": "https://opencode.ai/config.json",

            "provider": {
                "HPC_Lab": {
                    "npm": "@ai-sdk/openai-compatible",

                    "name": "HPC_LAB (GH1)",

                    "options": {
                        "baseURL": self.server_url,
                    },

                    "models": {
                        self.model: {
                            "name": self.model,
                        }
                    },
                }
            },

            "mcp": {
                self.mcp_server.name: {
                    "type": "local",

                    "command": (
                        mcp_command
                        if mcp_command is not None
                        else [self.mcp_server.executable]
                    ),

                    "enabled": mcp_enabled,
                }
            },
        }

        config_path.write_text(
            json.dumps(
                config,
                indent=2,
            ),
            encoding="utf-8",
        )

        return config_path

    # ==================================================================
    # EMPTY TOKEN USAGE
    # ==================================================================

    @staticmethod
    def _empty_usage() -> dict[str, int]:
        """
        Return an empty token usage structure.

        The cumulative fields sum token usage across all OpenCode
        inference steps.

        The last-step fields contain token usage from the final
        step only. This allows us to distinguish cumulative token
        consumption from the size of the final model context.
        """

        return {
            # ----------------------------------------------------------
            # Overall / cumulative usage
            # ----------------------------------------------------------

            "steps": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,

            # ----------------------------------------------------------
            # Last inference step
            # ----------------------------------------------------------

            "last_step_input_tokens": 0,
            "last_step_output_tokens": 0,
            "last_step_total_tokens": 0,
            "last_step_reasoning_tokens": 0,
            "last_step_cache_read_tokens": 0,
            "last_step_cache_write_tokens": 0,
        }

    @staticmethod
    def _record_step_usage(
        usage: dict[str, int],
        step_input: int,
        step_output: int,
        step_total: int,
        step_reasoning: int,
        step_cache_read: int,
        step_cache_write: int,
    ) -> int:
        """Add one inference step to a usage bucket."""
        usage["steps"] += 1
        usage["input_tokens"] += step_input
        usage["output_tokens"] += step_output
        usage["total_tokens"] += step_total
        usage["reasoning_tokens"] += step_reasoning
        usage["cache_read_tokens"] += step_cache_read
        usage["cache_write_tokens"] += step_cache_write
        usage["last_step_input_tokens"] = step_input
        usage["last_step_output_tokens"] = step_output
        usage["last_step_total_tokens"] = step_total
        usage["last_step_reasoning_tokens"] = step_reasoning
        usage["last_step_cache_read_tokens"] = step_cache_read
        usage["last_step_cache_write_tokens"] = step_cache_write
        return usage["steps"]

    # ==================================================================
    # MCP USAGE
    # ==================================================================

    def _extract_mcp_usage(
        self,
        raw_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Count actual MCP function calls from OpenCode events.

        Example:

            get_project_summary: 1
            get_data_dependencies: 3
            get_hardware_constraints: 2

        Result:

            {
                "used": true,
                "tool_calls": 6,
                "tools": {
                    "get_data_dependencies": 3,
                    "get_hardware_constraints": 2,
                    "get_project_summary": 1
                }
            }

        IMPORTANT:
        We count actual tool_use events.

        Merely enabling MCP does not count as MCP usage.
        """

        counter = Counter()

        # Keep the complete events as well so that we know how many
        # actual MCP calls occurred.
        mcp_events: list[dict[str, Any]] = []

        for event in raw_events:

            # ----------------------------------------------------------
            # Only tool_use events are relevant
            # ----------------------------------------------------------

            if event.get("type") != "tool_use":
                continue

            part = event.get(
                "part",
                {},
            )

            if not isinstance(
                part,
                dict,
            ):
                continue

            tool_name = part.get(
                "tool"
            )

            if not tool_name:
                continue

            tool_name = str(
                tool_name
            )

            normalized_name = (
                tool_name.lower()
            )

            # ----------------------------------------------------------
            # Determine whether this is an MCP tool
            # ----------------------------------------------------------

            is_mcp_tool = (
                tool_name in self.mcp_tool_names
                or "discopop" in normalized_name
                or "mcp" in normalized_name
            )

            if not is_mcp_tool:
                continue

            # ----------------------------------------------------------
            # Count function
            # ----------------------------------------------------------

            counter[
                tool_name
            ] += 1

            mcp_events.append(
                event
            )

        # --------------------------------------------------------------
        # Sort function names for deterministic result files
        # --------------------------------------------------------------

        tool_counts = dict(
            sorted(
                counter.items()
            )
        )

        return {
            "used": len(mcp_events) > 0,

            "tool_calls": len(
                mcp_events
            ),

            "tools": tool_counts,
        }

    @staticmethod
    def _extract_session_id(raw_events: list[dict[str, Any]]) -> Optional[str]:
        """Find the OpenCode session identifier in a tolerant JSON event stream."""
        pending: list[Any] = list(raw_events)
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                for key in ("sessionID", "session_id", "sessionId"):
                    session_id = value.get(key)
                    if isinstance(session_id, str) and session_id:
                        return session_id
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        return None

    # ==================================================================
    # RUN OPENCODE
    # ==================================================================

    def run(
        self,
        prompt: str,
        workspace: Path,
        mcp_enabled: bool = False,
        events_file: Optional[Path] = None,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Run one OpenCode coding-agent invocation.

        Parameters
        ----------
        prompt:
            Task prompt given to OpenCode.

        workspace:
            Isolated benchmark workspace.

        mcp_enabled:
            False for DIRECT and FULL_DISCOPOP.
            True for MCP.

        events_file:
            Optional JSONL file for raw OpenCode events.

        session_id:
            Continue this OpenCode conversation.  Omit it only for the first
            turn of a benchmark mode.
        """

        workspace = Path(
            workspace
        ).resolve()

        workspace.mkdir(
            parents=True,
            exist_ok=True,
        )

        # --------------------------------------------------------------
        # CREATE TEMPORARY OPENCODE CONFIG
        # --------------------------------------------------------------

        config_path = (
            self._write_project_config(
                workspace=workspace,
                mcp_enabled=mcp_enabled,
            )
        )

        invocation_id = (
            uuid.uuid4().hex
        )

        # --------------------------------------------------------------
        # OPENCODE MODEL ID
        # --------------------------------------------------------------
        #
        # OpenCode expects:
        #
        #     provider/model
        #
        # Here:
        #
        #     benchmark/Qwen/Qwen3-Coder-30B-A3B-Instruct
        # --------------------------------------------------------------

        opencode_model = (
            f"{self.PROVIDER}/{self.model}"
        )

        # --------------------------------------------------------------
        # OPENCODE COMMAND
        # --------------------------------------------------------------

        command = [
            "opencode",
            "run",
            "--format",
            "json",
            "--auto",
            "--model",
            opencode_model,
        ]

        if session_id:
            command.extend(
                [
                    "--session",
                    session_id,
                ]
            )

        command.extend(
            [
            "--dir",
            str(workspace),
            prompt,
            ]
        )

        print()
        print("=" * 70)
        print("OpenCode invocation")
        print("=" * 70)

        print(
            f"Invocation ID: {invocation_id}"
        )

        print(
            f"Model:         {opencode_model}"
        )

        print(
            f"MCP enabled:   {mcp_enabled}"
        )

        print(
            f"Workspace:     {workspace}"
        )

        print()
        print("OpenCode command:")

        print(
            " ".join(
                shlex.quote(
                    part
                )
                for part in command
            )
        )

        try:

            # ----------------------------------------------------------
            # START OPENCODE
            # ----------------------------------------------------------

            invocation_start_time = time.perf_counter()

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            stderr_lines: list[str] = []

            def collect_stderr() -> None:
                if process.stderr is not None:
                    stderr_lines.extend(process.stderr)

            stderr_thread = threading.Thread(target=collect_stderr)
            stderr_thread.start()

            # ----------------------------------------------------------
            # STORAGE
            # ----------------------------------------------------------

            output_text: list[str] = []

            usage = (
                self._empty_usage()
            )

            warm_usage = (
                self._empty_usage()
                if mcp_enabled
                else None
            )

            step_records: list[
                tuple[tuple[int, int, int, int, int, int], bool, bool, float]
            ] = []
            setup_seen_in_step = False
            task_mcp_seen_in_step = False

            raw_events: list[
                dict[str, Any]
            ] = []

            # ----------------------------------------------------------
            # PARSE JSON EVENT STREAM
            # ----------------------------------------------------------

            stdout_lines: list[str] = []

            if process.stdout is None:
                raise RuntimeError("OpenCode stdout pipe was not created.")

            for line in process.stdout:

                stdout_lines.append(line)

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(
                        line
                    )

                except json.JSONDecodeError:
                    # Ignore non-JSON lines.
                    continue

                if not isinstance(
                    event,
                    dict,
                ):
                    continue

                raw_events.append(
                    event
                )

                event_type = event.get(
                    "type"
                )

                if event_type == "tool_use" and mcp_enabled:
                    part = event.get("part", {})
                    if isinstance(part, dict):
                        tool_name = str(part.get("tool", ""))
                        normalized_name = tool_name.lower()
                        is_mcp_tool = (
                            tool_name in self.mcp_tool_names
                            or "discopop" in normalized_name
                            or "mcp" in normalized_name
                        )
                        setup_tools = ("prepare_project_analysis",)
                        is_setup_tool = tool_name in setup_tools or tool_name.endswith(
                            tuple(f"_{tool}" for tool in setup_tools)
                        )
                        if is_mcp_tool:
                            if is_setup_tool:
                                setup_seen_in_step = True
                            else:
                                task_mcp_seen_in_step = True

                # ======================================================
                # TEXT EVENT
                # ======================================================

                if event_type == "text":

                    part = event.get(
                        "part",
                        {},
                    )

                    if not isinstance(
                        part,
                        dict,
                    ):
                        continue

                    text = part.get(
                        "text",
                        "",
                    )

                    if text:
                        output_text.append(
                            text
                        )

                # ======================================================
                # STEP FINISHED
                # ======================================================

                elif event_type == "step_finish":

                    part = event.get(
                        "part",
                        {},
                    )

                    if not isinstance(
                            part,
                            dict,
                    ):
                        continue

                    tokens = part.get(
                        "tokens",
                        {},
                    )

                    if not isinstance(
                            tokens,
                            dict,
                    ):
                        continue

                    # --------------------------------------------------
                    # Extract current step usage
                    # --------------------------------------------------

                    step_input = int(
                        tokens.get(
                            "input",
                            0,
                        )
                        or 0
                    )

                    step_output = int(
                        tokens.get(
                            "output",
                            0,
                        )
                        or 0
                    )

                    step_total = int(
                        tokens.get(
                            "total",
                            0,
                        )
                        or 0
                    )

                    step_reasoning = int(
                        tokens.get(
                            "reasoning",
                            0,
                        )
                        or 0
                    )

                    cache = tokens.get(
                        "cache",
                        {},
                    )

                    if isinstance(
                            cache,
                            dict,
                    ):
                        step_cache_read = int(
                            cache.get(
                                "read",
                                0,
                            )
                            or 0
                        )

                        step_cache_write = int(
                            cache.get(
                                "write",
                                0,
                            )
                            or 0
                        )

                    else:
                        step_cache_read = 0
                        step_cache_write = 0

                    # --------------------------------------------------
                    # Step number
                    # --------------------------------------------------

                    step_number = self._record_step_usage(
                        usage,
                        step_input,
                        step_output,
                        step_total,
                        step_reasoning,
                        step_cache_read,
                        step_cache_write,
                    )

                    step_records.append(
                        (
                            (
                                step_input,
                                step_output,
                                step_total,
                                step_reasoning,
                                step_cache_read,
                                step_cache_write,
                            ),
                            setup_seen_in_step,
                            task_mcp_seen_in_step,
                            time.perf_counter(),
                        )
                    )
                    setup_seen_in_step = False
                    task_mcp_seen_in_step = False

                    # --------------------------------------------------
                    # DEBUG: print per-step token usage
                    # --------------------------------------------------

                    print(
                        f"[OpenCode] Step {step_number}: "
                        f"input={step_input:,}, "
                        f"output={step_output:,}, "
                        f"total={step_total:,}, "
                        f"reasoning={step_reasoning:,}, "
                        f"cache_read={step_cache_read:,}, "
                        f"cache_write={step_cache_write:,}"
                    )

            # ----------------------------------------------------------
            # MCP USAGE
            # ----------------------------------------------------------

            mcp_usage = (
                self._extract_mcp_usage(
                    raw_events
                )
            )

            returned_session_id = self._extract_session_id(raw_events)

            returncode = process.wait()
            stderr_thread.join()
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            warm_start_index = 0
            warm_start_time = invocation_start_time
            setup_used = False
            task_mcp_used = False
            for index, (_, contains_setup, contains_task_mcp, step_time) in enumerate(step_records):
                if contains_setup:
                    setup_used = True
                    warm_start_index = index + 1
                    warm_start_time = step_time
                if contains_task_mcp:
                    task_mcp_used = True

            warm_started = mcp_enabled and setup_used and task_mcp_used
            if warm_started and warm_usage is not None:
                for step_usage, _, _, _ in step_records[warm_start_index:]:
                    self._record_step_usage(warm_usage, *step_usage)

            warm_latency_seconds = (
                time.perf_counter() - warm_start_time
                if warm_started
                else None
            )

            # ----------------------------------------------------------
            # SAVE RAW EVENTS
            # ----------------------------------------------------------

            if events_file is not None:

                events_file = Path(
                    events_file
                )

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

            # ----------------------------------------------------------
            # OPENCODE FAILURE
            # ----------------------------------------------------------

            if returncode != 0:

                raise RuntimeError(
                    "OpenCode failed with exit code "
                    f"{returncode}\n\n"
                    f"stdout:\n"
                    f"{stdout}\n\n"
                    f"stderr:\n"
                    f"{stderr}"
                )

            # ----------------------------------------------------------
            # PRINT SUMMARY
            # ----------------------------------------------------------

            print()
            print("OpenCode finished.")

            def print_usage_summary(
                title: str,
                usage_summary: dict[str, int],
            ) -> None:
                print(title)
                print(f"Steps:             {usage_summary['steps']}")
                print(f"Input tokens:      {usage_summary['input_tokens']:,}")
                print(f"Output tokens:     {usage_summary['output_tokens']:,}")
                print(f"Total tokens:      {usage_summary['total_tokens']:,}")
                print(
                    "Last-step input:   "
                    f"{usage_summary['last_step_input_tokens']:,}"
                )
                print(
                    "Last-step output:  "
                    f"{usage_summary['last_step_output_tokens']:,}"
                )
                print(
                    "Last-step total:   "
                    f"{usage_summary['last_step_total_tokens']:,}"
                )

            if mcp_enabled:
                print_usage_summary("Cold usage (end-to-end):", usage)

            else:
                print_usage_summary("Usage:", usage)

            if warm_started and warm_usage is not None:
                print()
                print_usage_summary("Warm usage (after MCP setup):", warm_usage)

            print(
                f"MCP used:       "
                f"{mcp_usage['used']}"
            )

            print(
                f"MCP calls:      "
                f"{mcp_usage['tool_calls']}"
            )

            if mcp_usage["tools"]:

                print(
                    "MCP functions:"
                )

                for (
                    tool_name,
                    count,
                ) in mcp_usage[
                    "tools"
                ].items():

                    print(
                        f"  {tool_name}: "
                        f"{count}"
                    )

            # ----------------------------------------------------------
            # RETURN RESULT
            # ----------------------------------------------------------

            return {
                "output": "\n".join(
                    output_text
                ),

                "stderr": stderr,

                "returncode": (
                    returncode
                ),

                "usage": usage,

                "warm_usage": (
                    warm_usage if warm_started else None
                ),

                "warm_latency_seconds": warm_latency_seconds,

                "mcp_enabled": (
                    mcp_enabled
                ),

                "mcp_usage": mcp_usage,

                "invocation_id": (
                    invocation_id
                ),

                "session_id": (
                    returned_session_id or session_id
                ),

                "events_file": (
                    str(events_file)
                    if events_file is not None
                    else None
                ),
            }

        finally:

            # ----------------------------------------------------------
            # REMOVE TEMPORARY OPENCODE CONFIG
            # ----------------------------------------------------------

            if config_path.exists():
                config_path.unlink()

            # ----------------------------------------------------------
            # REMOVE TEMPORARY MCP WRAPPER
            # ----------------------------------------------------------

            for path in (
                self.mcp_server.temporary_files(
                    workspace
                )
            ):

                if path.exists():
                    path.unlink()

#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.claude_code import summarize_mcp_availability


def short_path(path: str) -> str:
    if not isinstance(path, str):
        return str(path)

    workspace = "/workspace"
    marker = "/mcp/workspace"

    if marker in path:
        return workspace + path.split(marker, 1)[1]

    return path


def clean_text(text: str, max_lines: int = 20, max_chars: int = 4000) -> str:
    if not text:
        return ""

    text = str(text)

    # Remove very long absolute paths
    text = re.sub(
        r"/home/[^ \n\"']+/mcp/workspace",
        "/workspace",
        text,
    )

    if len(text) > max_chars:
        text = text[:max_chars] + "\n... [truncated]"

    lines = text.splitlines()

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines.append("... [truncated]")

    return "\n".join(lines)


def format_value(value, max_chars=1500):
    if value is None:
        return ""

    if isinstance(value, dict):
        # File tool
        if "filePath" in value:
            value = {"file": short_path(value["filePath"])}

        text = json.dumps(value, indent=2, ensure_ascii=False)

    elif isinstance(value, list):
        text = json.dumps(value, indent=2, ensure_ascii=False)

    else:
        text = str(value)

    text = text.replace(
        "/home/dinhtienvu/TU_Darmstadt/6.Semester/Thesis/"
        "discopop-thesis/mcp_server_validation",
        "",
    )

    return clean_text(text, max_chars=max_chars)


def tool_label(tool: str) -> str:
    prefix = "discopop_mcp_server_"

    if tool.startswith(prefix):
        return "DiscoPoP/" + tool[len(prefix):]

    return tool


def print_separator():
    print("─" * 78)


def print_step(step_no, texts, tools):
    print()
    print(f" STEP {step_no:02d} ")

    for text in texts:
        text = text.strip()

        if not text:
            continue

        print("-----AGENT-----")

        for line in clean_text(text, max_lines=30, max_chars=2500).splitlines():
            print(f"{line}")

    for tool in tools:
        name = tool["name"]
        input_data = tool["input"]
        output = tool["output"]

        print("-----TOOL-----")
        print(f" {tool_label(name)}")

        if input_data:
            print("-----Input-----")
            formatted = format_value(input_data, 1200)

            for line in formatted.splitlines():
                print(f" {line}")

        if output is not None:
            print("-----RESULT-----")

            formatted = format_value(output, 3000)

            for line in formatted.splitlines():
                print(f"{line}")
    print("─" * 77)


def parse_events(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_steps(events):
    if any(event.get("type") == "assistant" for event in events):
        return build_claude_steps(events)

    steps = []
    current = None

    for event in events:
        event_type = event.get("type")
        part = event.get("part", {})

        if event_type == "step_start":
            current = {
                "texts": [],
                "tools": [],
            }

        elif current is None:
            continue

        elif event_type == "text":
            text = part.get("text")
            if text:
                current["texts"].append(text)

        elif event_type == "tool_use":
            state = part.get("state", {})

            current["tools"].append(
                {
                    "name": part.get("tool", "unknown"),
                    "input": state.get("input"),
                    "output": state.get("output"),
                }
            )

        elif event_type == "step_finish":
            steps.append(current)
            current = None

    return steps


def build_claude_steps(events):
    steps = {}
    tool_results = {}
    seen_tools = set()
    for event in events:
        message = event.get("message") or {}
        if not isinstance(message, dict):
            continue
        if event.get("type") == "user":
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_results[block.get("tool_use_id")] = block.get("content")
        if event.get("type") != "assistant":
            continue
        step = steps.setdefault(message.get("id") or f"anonymous_{len(steps)}", {
            "texts": [], "tools": [],
        })
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and block.get("text"):
                step["texts"].append(block["text"])
            elif block.get("type") == "tool_use":
                tool_id = block.get("id")
                if tool_id and tool_id in seen_tools:
                    continue
                if tool_id:
                    seen_tools.add(tool_id)
                step["tools"].append({
                    "id": tool_id, "name": block.get("name", "unknown"),
                    "input": block.get("input"), "output": None,
                })
    for step in steps.values():
        for tool in step["tools"]:
            tool["output"] = tool_results.get(tool["id"])
    return list(steps.values())


def main():
    parser = argparse.ArgumentParser(
        description="Human-readable OpenCode or Claude Code agent transcript"
    )

    parser.add_argument(
        "file",
        type=Path,
        help="Path to events.jsonl",
    )

    parser.add_argument(
        "--from",
        dest="start",
        type=int,
        default=1,
        help="Start step",
    )

    parser.add_argument(
        "--to",
        dest="end",
        type=int,
        default=None,
        help="End step",
    )

    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"File not found: {args.file}")

    events = parse_events(args.file)
    steps = build_steps(events)
    is_claude = any(event.get("type") == "assistant" for event in events)

    end = args.end or len(steps)

    print()
    print("═" * 78)
    print(f" {'Claude Code' if is_claude else 'OpenCode'} AGENT TRANSCRIPT")
    print("═" * 78)
    print(f"File : {args.file}")
    print(f"Steps: {len(steps)}")
    if is_claude:
        init = next((event for event in events if event.get("type") == "system"
                     and event.get("subtype") == "init"), {})
        calls = sum(tool["name"].startswith("mcp__discopop_mcp_server__")
                    for step in steps for tool in step["tools"])
        print("DiscoPoP MCP (assuming MCP condition):")
        print(json.dumps(summarize_mcp_availability(
            init, "discopop_mcp_server", True, calls
        ), indent=2))
        print(f"DiscoPoP MCP calls: {calls}")
    print("═" * 78)

    for i, step in enumerate(steps, 1):
        if i < args.start or i > end:
            continue

        print_step(
            i,
            step["texts"],
            step["tools"],
        )

    print()
    print("═" * 78)
    print(" END OF TRANSCRIPT")
    print("═" * 78)


if __name__ == "__main__":
    main()

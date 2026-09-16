#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


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
    print(f"╭─ STEP {step_no:02d} " + "─" * 67)

    for text in texts:
        text = text.strip()

        if not text:
            continue

        print("│")
        print("│ 🤖 QWEN")
        print("│")

        for line in clean_text(text, max_lines=30, max_chars=2500).splitlines():
            print(f"│ {line}")

    for tool in tools:
        name = tool["name"]
        input_data = tool["input"]
        output = tool["output"]

        print("│")
        print("│ 🔧 TOOL")
        print(f"│ {tool_label(name)}")

        if input_data:
            print("│")
            print("│ Input:")
            formatted = format_value(input_data, 1200)

            for line in formatted.splitlines():
                print(f"│   {line}")

        if output is not None:
            print("│")
            print("│ 📥 RESULT")

            formatted = format_value(output, 3000)

            for line in formatted.splitlines():
                print(f"│ {line}")

    print("│")
    print("╰" + "─" * 77)


def parse_events(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_steps(events):
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


def main():
    parser = argparse.ArgumentParser(
        description="Human-readable OpenCode agent transcript"
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

    end = args.end or len(steps)

    print()
    print("═" * 78)
    print(" OPENCode AGENT TRANSCRIPT")
    print("═" * 78)
    print(f"File : {args.file}")
    print(f"Steps: {len(steps)}")
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
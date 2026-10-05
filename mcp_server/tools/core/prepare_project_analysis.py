# This file is part of the DiscoPoP software (http://www.discopop.tu-darmstadt.de)
#
# Copyright (c) 2020, Technische Universitaet Darmstadt, Germany
#
# This software may be modified and distributed under the terms of
# the 3-Clause BSD License.  See the LICENSE file in the package base
# directory for details.

"""One-call project setup for an agent that needs DiscoPoP analysis."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool, ToolAnnotations

from discopop_library.ProjectManager.utilities.deriveSettingsFiles import derive_settings_files
from discopop_library.ProjectManager.utilities.reset import reset_project
from discopop_library.ProjectManager.utilities.scriptFiles import write_script_file
from mcp_server.tools.common.helpers import ToolContext

logger = logging.getLogger("discopop-mcp")


TOOL = Tool(
    name="prepare_project_analysis",
    annotations=ToolAnnotations(idempotentHint=True),
    description=(
        "Create DiscoPoP build and execution configuration for a project. Then call gather_data."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Absolute project root.",
            },
            "build_command": {
                "type": "string",
                "description": "Build command run from the project root.",
            },
            "run_command": {
                "type": "string",
                "description": "Small representative program run.",
            },
            "config_name": {
                "type": "string",
                "description": "Configuration name. Default: benchmark.",
            },
            "reset": {
                "type": "boolean",
                "description": "Clear old analysis artifacts. Default: false.",
            },
            "base_cc": {
                "type": "string",
                "description": "Base C compiler. Default: gcc.",
            },
            "base_cxx": {
                "type": "string",
                "description": "Base C++ compiler. Default: g++.",
            },
        },
        "required": ["project_path", "build_command", "run_command"],
        "additionalProperties": False,
    },
)


def _script(command: str) -> str:
    return "#!/bin/bash\nset -e\ncd \"$DP_PROJECT_ROOT_DIR\"\n" + command + "\n"


def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[TextContent]:
    """Create the project artefacts required by ``gather_data`` in one call."""
    project_path = str(arguments.get("project_path", ""))
    build_command = str(arguments.get("build_command", "")).strip()
    run_command = str(arguments.get("run_command", "")).strip()
    config_name = str(arguments.get("config_name", "benchmark"))
    reset = bool(arguments.get("reset", False))
    base_cc = str(arguments.get("base_cc", "gcc"))
    base_cxx = str(arguments.get("base_cxx", "g++"))

    if not build_command or not run_command:
        return ctx.error(
            "build_command and run_command must both be non-empty.",
            project_path,
            "prepare_project_analysis",
        )

    try:
        project = Path(project_path)
        if not project.exists():
            return ctx.error(
                f"project_path does not exist: {project_path}", project_path, "prepare_project_analysis"
            )

        if reset:
            pm_args = ctx.make_pm_args(project_path)
            pm_args.reset = True
            pm_args.reset_execution_results = True
            reset_project(pm_args)
            ctx.log_action(project_path, "prepare_project_analysis", "Removed stale analysis artefacts")

        configs_dir = project / ".discopop" / "project" / "configs"
        configs_dir.mkdir(parents=True, exist_ok=True)
        seq_settings = configs_dir / "seq_settings.json"
        if not seq_settings.exists():
            seq_settings.write_text(
                json.dumps({"CC": base_cc, "CXX": base_cxx, "CFLAGS": "", "CXXFLAGS": ""}, indent=2)
            )
            derive_settings_files(str(configs_dir), overwrite=False)
            ctx.log_action(project_path, "prepare_project_analysis", f"Created settings for {base_cc}/{base_cxx}")

        if not config_name or os.sep in config_name or "/" in config_name or config_name.startswith("."):
            return ctx.error(
                f"Invalid config_name '{config_name}'.", project_path, "prepare_project_analysis"
            )

        compile_path = configs_dir / "compile.sh"
        write_script_file(str(compile_path), _script(build_command))
        config_dir = configs_dir / config_name
        config_dir.mkdir(parents=True, exist_ok=True)
        execute_path = config_dir / "execute.sh"
        write_script_file(str(execute_path), _script(run_command))
        ctx.log_action(project_path, "prepare_project_analysis", f"Wrote {compile_path.name} and {execute_path}")

        response = {
            "status": "success",
            "project_path": project_path,
            "config_name": config_name,
            "message": "Project is ready for analysis. Call gather_data next.",
        }
        ctx.log_response("prepare_project_analysis", response)
        return [TextContent(type="text", text=json.dumps(response))]
    except Exception as exc:
        message = f"Error preparing project analysis: {exc}"
        logger.error(message, exc_info=True)
        return [TextContent(type="text", text=json.dumps({"status": "error", "message": message}))]

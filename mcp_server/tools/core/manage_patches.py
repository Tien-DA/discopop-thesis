# This file is part of the DiscoPoP software (http://www.discopop.tu-darmstadt.de)
#
# Copyright (c) 2020, Technische Universitaet Darmstadt, Germany
#
# This software may be modified and distributed under the terms of
# the 3-Clause BSD License.  See the LICENSE file in the package base
# directory for details.

import json
import logging
from pathlib import Path
from typing import Any, Optional

from mcp.types import TextContent, Tool

from mcp_server.tools.common.helpers import (
    APPLICATOR_OK_RETURNCODES,
    ToolContext,
    applicator_failure_details,
    read_application_result,
    run_patch_applicator,
)

logger = logging.getLogger("discopop-mcp")

TOOL = Tool(
    name="manage_patches",
    description=(
        "List, apply, roll back, clear, or reload generated parallelization patches. "
        "Requires gather_data. Prefer run_auto_tuning to choose IDs; apply and rollback modify source files."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Absolute project root.",
            },
            "action": {
                "type": "string",
                "enum": ["apply", "rollback", "clear", "load", "list"],
                "description": "Patch operation.",
            },
            "suggestion_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IDs for apply or rollback.",
            },
        },
        "required": ["project_path", "action"],
        "additionalProperties": False,
    },
)


def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[TextContent]:
    try:
        project_path: str = arguments.get("project_path", "")
        action: str = arguments.get("action", "")
        suggestion_ids: list[str] = arguments.get("suggestion_ids") or []

        discopop_dir = Path(project_path) / ".discopop"

        if not discopop_dir.exists():
            return ctx.error(
                "DiscoPoP directory not found. Run prepare_project_analysis and gather_data first.",
                project_path,
                "manage_patches",
            )

        patch_gen_dir = discopop_dir / "patch_generator"
        file_mapping = discopop_dir / "FileMapping.txt"

        if not patch_gen_dir.exists():
            return ctx.error(
                "patch_generator directory not found. Run gather_data first.",
                project_path,
                "manage_patches",
            )
        if not file_mapping.exists():
            return ctx.error(
                "FileMapping.txt not found. Run gather_data first.",
                project_path,
                "manage_patches",
            )

        if action in ("apply", "rollback") and not suggestion_ids:
            return ctx.error(
                f"'suggestion_ids' must be non-empty for action '{action}'.",
                project_path,
                "manage_patches",
            )

        applicator_args: list[str] = []
        if action == "apply":
            applicator_args = ["--apply"] + suggestion_ids
        elif action == "rollback":
            applicator_args = ["--rollback"] + suggestion_ids
        elif action == "clear":
            applicator_args = ["--clear"]
        elif action == "load":
            applicator_args = ["--load"]
        elif action == "list":
            applicator_args = ["--list"]
        else:
            return ctx.error(f"Unknown action '{action}'.", project_path, "manage_patches")

        ctx.log_action(
            project_path,
            "manage_patches",
            f"action={action}, suggestion_ids={suggestion_ids}, args={applicator_args}",
        )

        proc, run_error = run_patch_applicator(project_path, applicator_args)
        if proc is None:
            return ctx.error(run_error or "discopop_patch_applicator could not be run.", project_path, "manage_patches")

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        # rc=0: success; rc=2: partial success; rc=3: nothing to do (trivially ok)
        if proc.returncode not in APPLICATOR_OK_RETURNCODES:
            # The applicator prints why it gave up on stdout, so an error carrying only
            # stderr is a return code and nothing else -- the caller cannot tell a stale
            # patch from a missing file from a bug, and has nothing to act on.
            output, cause = applicator_failure_details(proc)
            message = f"discopop_patch_applicator failed (rc={proc.returncode})."
            if cause is not None:
                message += " " + cause
            result: dict[str, Any] = {
                "status": "error",
                "project_path": project_path,
                "action": action,
                "message": message,
                "returncode": proc.returncode,
                "output": output,
            }
            ctx.log_response("manage_patches", result)
            return [TextContent(type="text", text=json.dumps(result))]

        # Parse applied suggestions list for list action (stdout: "Applied suggestions:  ['1', '2']")
        applied_suggestions: Optional[list[str]] = None
        if action == "list":
            for line in stdout.splitlines():
                if "Applied suggestions:" in line:
                    try:
                        raw = line.split("Applied suggestions:")[-1].strip()
                        applied_suggestions = json.loads(raw.replace("'", '"'))
                    except Exception:
                        applied_suggestions = [raw]
                    break

        result = {
            "status": "success" if proc.returncode == 0 else "partial",
            "project_path": project_path,
            "action": action,
            "returncode": proc.returncode,
        }
        if suggestion_ids:
            result["suggestion_ids"] = suggestion_ids
        if applied_suggestions is not None:
            result["applied_suggestions"] = applied_suggestions
        # The applicator records exactly which requested suggestions reached the code.
        # Reporting the unapplied ones is what keeps a caller from measuring or
        # reviewing unmodified code in the belief that it was parallelized.
        if action == "apply":
            application = read_application_result(project_path)
            if application:
                result["applied_now"] = application.get("applied", [])
                unapplied = list(application.get("failed", [])) + list(application.get("unknown", []))
                if unapplied:
                    result["not_applied"] = unapplied
                    result["status"] = "partial" if application.get("applied") else "error"
                    result["message"] = (
                        "The following suggestions were NOT applied: "
                        + ", ".join(unapplied)
                        + ". The affected files are unchanged, so the code is not parallelized as requested."
                    )
        if proc.returncode == 2 and "message" not in result:
            result["message"] = "Some patches were applied; others may have failed. Check stderr for details."
        if proc.returncode == 3:
            result["message"] = "Nothing to do (no patches to roll back or load)."
        if stderr:
            result["stderr"] = stderr

        ctx.log_response("manage_patches", result)
        return [TextContent(type="text", text=json.dumps(result))]

    except Exception as e:
        error_msg = f"Error in manage_patches: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=json.dumps({"status": "error", "message": error_msg}))]

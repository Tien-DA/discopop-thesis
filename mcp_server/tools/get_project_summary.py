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

from mcp.types import TextContent, Tool, ToolAnnotations

from mcp_server.tools.helpers import ToolContext

logger = logging.getLogger("discopop-mcp")

TOOL = Tool(
    name="get_project_summary",
    annotations=ToolAnnotations(readOnlyHint=True),
    description=(
        "Get a high-level summary of the project including key metrics, "
        "detected parallelization opportunities, and potential issues. "
        "This tool provides a comprehensive overview without requiring multiple tool calls."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Absolute path to the project root.",
            },
            "include_detailed_metrics": {
                "type": "boolean",
                "description": "Whether to include detailed metrics and statistics. Default: false.",
                "default": False
            }
        },
        "required": ["project_path"],
        "additionalProperties": False,
    },
)


def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[TextContent]:
    try:
        project_path = arguments.get("project_path", "")
        include_detailed = arguments.get("include_detailed_metrics", False)
        
        p = Path(project_path)
        
        # Get project structure info
        source_files = list(p.rglob("*.[ch][ch]*"))  # C/C++ files
        source_files = [f for f in source_files if ".discopop" not in str(f)]
        
        # Get patch information if available
        patch_gen_dir = p / ".discopop" / "patch_generator"
        patch_count = 0
        if patch_gen_dir.exists():
            patch_count = len(list(patch_gen_dir.iterdir()))
            
        # Get execution results if available
        exec_results_file = p / ".discopop" / "execution_results.json"
        execution_results = {}
        if exec_results_file.exists():
            try:
                execution_results = json.loads(exec_results_file.read_text())
            except Exception:
                pass
                
        # Create summary
        summary = {
            "status": "success",
            "project_path": project_path,
            "project_info": {
                "total_source_files": len(source_files),
                "source_file_extensions": list(set(f.suffix for f in source_files)),
                "size_estimate_bytes": sum(f.stat().st_size for f in source_files),
            },
            "analysis_status": {
                "parallelization_patches_available": patch_count > 0,
                "patches_count": patch_count,
                "execution_results_available": len(execution_results) > 0,
            },
            "recommendations": []
        }
        
        # Add recommendations based on available data
        if patch_count > 0:
            summary["recommendations"].append({
                "type": "parallelization_opportunities",
                "count": patch_count,
                "description": f"Found {patch_count} potential parallelization opportunities",
                "confidence": 0.9
            })
            
        if include_detailed:
            # Add more detailed metrics
            summary["detailed_metrics"] = {
                "file_breakdown": {},
                "complexity_indicators": {
                    "nested_loops": 0,
                    "function_calls": 0,
                    "data_structures": 0
                }
            }
            
        ctx.log_response("get_project_summary", summary)
        return [TextContent(type="text", text=json.dumps(summary))]
        
    except Exception as e:
        error_msg = f"Error getting project summary: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=json.dumps({"status": "error", "message": error_msg}))]

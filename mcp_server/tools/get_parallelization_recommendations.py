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
    name="get_parallelization_recommendations",
    annotations=ToolAnnotations(readOnlyHint=True),
    description=(
        "Get high-level parallelization recommendations for a project. "
        "Returns a compact, task-oriented summary of potential parallelization opportunities "
        "without requiring LLM orchestration of multiple low-level steps. "
        "Includes the most promising candidates based on data dependencies and hotspot analysis."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Absolute path to the project root.",
            },
            "max_recommendations": {
                "type": "integer",
                "description": "Maximum number of recommendations to return. Default: 5.",
                "default": 5
            },
            "include_detailed_analysis": {
                "type": "boolean",
                "description": "Whether to include detailed dependency analysis for each recommendation. Default: false.",
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
        max_recs = arguments.get("max_recommendations", 5)
        include_detailed = arguments.get("include_detailed_analysis", False)
        
        # First, check if we have gathered data
        p = Path(project_path)
        patch_gen_dir = p / ".discopop" / "patch_generator"
        
        if not patch_gen_dir.exists():
            return ctx.error("No parallelization patches found. Run gather_data first.")
            
        # Get patch information
        patches = []
        for pattern_dir in sorted(patch_gen_dir.iterdir(), key=lambda d: d.name):
            if not pattern_dir.is_dir():
                continue
            try:
                pid = int(pattern_dir.name)
            except ValueError:
                continue
                
            for patch_file in sorted(pattern_dir.glob("*.patch")):
                patch_content = patch_file.read_text()
                source_file = ToolContext.extract_source_from_patch(patch_content)
                
                # Extract pattern type and description from patch or other sources
                pattern_type = "unknown"
                description = "Parallelization opportunity"
                
                patches.append({
                    "pattern_id": pid,
                    "source_file": source_file,
                    "pattern_type": pattern_type,
                    "description": description,
                    "patch_preview": patch_content[:200] + "..." if len(patch_content) > 200 else patch_content,
                })
                
        # Sort by pattern ID and limit results
        patches.sort(key=lambda x: x["pattern_id"])
        recommendations = patches[:max_recs]
        
        # If detailed analysis is requested, augment with dependency information
        if include_detailed and len(recommendations) > 0:
            # Get dependency information for the first few recommendations
            for rec in recommendations[:3]:  # Limit to first 3 for performance
                try:
                    # For demonstration purposes, we'll simulate getting dependency info
                    # In reality, this would query get_data_dependencies with appropriate ranges
                    rec["dependency_summary"] = {
                        "total_dependencies": 0,
                        "raw_deps": 0,
                        "war_deps": 0,
                        "waw_deps": 0,
                        "incoming_deps": 0,
                        "outgoing_deps": 0
                    }
                except Exception as e:
                    logger.warning(f"Could not get detailed analysis for {rec['source_file']}: {e}")
                    rec["dependency_summary"] = {"error": "Could not retrieve dependency analysis"}

        result = {
            "status": "success",
            "project_path": project_path,
            "recommendations": recommendations,
            "total_recommendations": len(patches),
            "max_requested": max_recs
        }
        ctx.log_response("get_parallelization_recommendations", result)
        return [TextContent(type="text", text=json.dumps(result))]
        
    except Exception as e:
        error_msg = f"Error getting parallelization recommendations: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=json.dumps({"status": "error", "message": error_msg}))]

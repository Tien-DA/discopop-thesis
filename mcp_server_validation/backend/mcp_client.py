"""
MCP Client Module

Client for communicating with MCP servers over stdio.
"""

import asyncio
from typing import Dict, Any, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from utils.logger import setup_logger

logger = setup_logger(__name__)


class MCPClient:
    """
    Client for communicating with an MCP server over stdio.
    """

    def __init__(self, server_command: str):
        self.server_command = server_command
        self.connected = False
        self.available_tools: List[Dict[str, Any]] = []

    async def _list_tools_async(self) -> List[Dict[str, Any]]:
        """
        Start the MCP server and retrieve its available tools.
        """

        server_params = StdioServerParameters(
            command=self.server_command,
            args=[],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:

                await session.initialize()

                result = await session.list_tools()

                tools = []

                for tool in result.tools:
                    tools.append(
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema,
                        }
                    )

                return tools

    def connect(self) -> bool:
        """
        Connect to the MCP server and discover available tools.
        """

        try:
            logger.info(
                "Connecting to MCP server: %s",
                self.server_command,
            )

            self.available_tools = asyncio.run(
                self._list_tools_async()
            )

            self.connected = True

            logger.info(
                "Connected to MCP server. Found %d tools.",
                len(self.available_tools),
            )

            logger.info(
                "Available tools: %s",
                [tool["name"] for tool in self.available_tools],
            )

            return True

        except Exception as exc:
            logger.error(
                "Failed to connect to MCP server: %s",
                exc,
            )

            self.connected = False
            self.available_tools = []

            return False

    def is_connected(self) -> bool:
        """
        Return whether the MCP client is connected.
        """

        return self.connected

    def list_available_tools(self) -> List[Dict[str, Any]]:
        """
        Return the tools discovered from the MCP server.
        """

        return self.available_tools

    def get_tool_schema(
        self,
        tool_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Return the schema for a specific MCP tool.
        """

        for tool in self.available_tools:
            if tool["name"] == tool_name:
                return tool

        return None
#
# This file is part of the DiscoPoP software (http://www.discopop.tu-darmstadt.de)
#
# Copyright (c) 2020, Technische Universitaet Darmstadt, Germany
#
# This software may be modified and distributed under the terms of
# the 3-Clause BSD License.  See the LICENSE file in the package base
# directory for details.

#!/usr/bin/env python3
"""
Test suite for the DiscoPoP MCP Server
"""

import logging
import unittest
from unittest.mock import patch

from mcp_server.server import DEFAULT_TOOL_SET, TOOL_SETS, DiscoPopMCPServer, unavailable_tool_message


class TestDiscoPopMCPServer(unittest.TestCase):
    def setUp(self) -> None:
        self.server = DiscoPopMCPServer(debug=True)

    def test_server_initialization(self) -> None:
        """Test that server initializes correctly"""
        self.assertIsNotNone(self.server.server)
        self.assertTrue(self.server.debug)

    def test_logging_call_info(self) -> None:
        """Test that call logging works"""
        with patch("logging.Logger.info") as mock_info:
            self.server._ctx.log_call("test_tool", {"arg": "value"})
            # Just verify the method doesn't raise

    def test_tool_registration(self) -> None:
        """Test that tools are properly registered"""
        tools = self.server.server.list_tools()
        # Should be registered but tools list is from the handler
        # Just verify no errors occur
        self.assertIsNotNone(tools)


class TestToolSets(unittest.TestCase):
    """The --tools selection: what a client is offered, and what it may call."""

    _SETUP_TOOL_NAMES = {"prepare_project_analysis"}

    def __names(self, tool_set: str) -> set[str]:
        return {mod.TOOL.name for mod in TOOL_SETS[tool_set]}

    def test_the_default_set_offers_the_compact_workflow(self) -> None:
        names = self.__names("default")
        self.assertTrue(self._SETUP_TOOL_NAMES <= names)
        self.assertEqual(DiscoPopMCPServer().tool_set, DEFAULT_TOOL_SET)
        self.assertLess(len(names), len(self.__names("all")))
        self.assertEqual(names, {
            "prepare_project_analysis", "gather_data", "triage_parallel_failure", "assess_parallel_region",
            "validate_parallel_behavior", "evaluate_parallel_performance", "run_auto_tuning", "manage_patches",
        })

    def test_all_set_adds_only_low_level_diagnostic_primitives(self) -> None:
        names = self.__names("all")
        self.assertTrue({"compare_threaded_executions", "diagnose_parallel_correctness", "trace_symbol_slice"} <= names)
        self.assertEqual(len(names), 11)

    def test_the_analysis_set_leaves_out_the_project_setup_tools(self) -> None:
        names = self.__names("analysis")
        self.assertFalse(names & self._SETUP_TOOL_NAMES)
        # everything the analysis route needs is still there
        for expected in (
            "gather_data",
            "run_auto_tuning",
            "manage_patches",
            "triage_parallel_failure",
            "assess_parallel_region",
            "validate_parallel_behavior",
        ):
            self.assertIn(expected, names)

    def test_a_hidden_tool_is_not_dispatchable_and_says_why(self) -> None:
        server = DiscoPopMCPServer(tool_set="analysis")
        self.assertNotIn("prepare_project_analysis", {mod.TOOL.name for mod in server._tools})
        message = unavailable_tool_message("prepare_project_analysis", "analysis")
        self.assertIn("not available in the 'analysis' tool set", message)
        self.assertIn("--tools all", message)

    def test_an_unknown_name_is_still_an_unknown_tool(self) -> None:
        self.assertEqual(unavailable_tool_message("no_such_tool", "analysis"), "Unknown tool: no_such_tool")


class TestServerIntegration(unittest.TestCase):
    """Integration tests for the MCP Server"""

    def test_debug_mode(self) -> None:
        """Test that debug mode sets correct logging level"""
        server = DiscoPopMCPServer(debug=True)
        self.assertTrue(server.debug)

        server_no_debug = DiscoPopMCPServer(debug=False)
        self.assertFalse(server_no_debug.debug)


if __name__ == "__main__":
    unittest.main()

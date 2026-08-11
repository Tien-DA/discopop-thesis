import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mcp_server.benchmark_cli import _oracle

# Load benchmark.py directly
SPEC = importlib.util.spec_from_file_location(
    "discopop_benchmark",
    Path(__file__).with_name("benchmark.py"),
)
benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(benchmark)


class BenchmarkOracleTests(unittest.TestCase):

    def test_empty_dependencies(self):
        oracle = _oracle({"dependencies": {}})
        self.assertEqual(
            oracle["must_contain"],
            ["no dependencies"],
        )

    def test_missing_dependencies_key(self):
        oracle = _oracle({})
        self.assertEqual(
            oracle["must_contain"],
            ["no dependencies"],
        )

    def test_single_dependency(self):
        oracle = _oracle(
            {
                "dependencies": {
                    "intra_region": [
                        {
                            "var_name": "sum",
                            "dep_type": "RAW",
                        }
                    ]
                }
            }
        )

        self.assertEqual(
            oracle["must_contain"],
            ["sum", "RAW"],
        )

    def test_multiple_dependencies(self):
        oracle = _oracle(
            {
                "dependencies": {
                    "intra_region": [
                        {
                            "var_name": "sum",
                            "dep_type": "RAW",
                        },
                        {
                            "var_name": "x",
                            "dep_type": "WAR",
                        },
                    ]
                }
            }
        )

        self.assertEqual(
            oracle["must_contain"],
            ["sum", "RAW", "x"],
        )

    def test_duplicate_facts_are_not_duplicated(self):
        oracle = _oracle(
            {
                "dependencies": {
                    "intra_region": [
                        {
                            "var_name": "sum",
                            "dep_type": "RAW",
                        },
                        {
                            "var_name": "sum",
                            "dep_type": "RAW",
                        },
                    ]
                }
            }
        )

        self.assertEqual(
            oracle["must_contain"],
            ["sum", "RAW"],
        )

    def test_oracle_is_independent_of_llm_answer(self):
        disco_pop_output = {
            "dependencies": {
                "intra_region": [
                    {
                        "var_name": "sum",
                        "dep_type": "RAW",
                    }
                ]
            }
        }

        oracle_1 = _oracle(disco_pop_output)
        oracle_2 = _oracle(disco_pop_output)

        self.assertEqual(oracle_1, oracle_2)


class AnswerScoringTests(unittest.TestCase):

    def test_exact_answer_passes(self):
        result = benchmark._score_answer(
            "There is a RAW dependency on sum.",
            {
                "must_contain": ["sum", "RAW"],
            },
        )

        self.assertTrue(result["passed"])

    def test_missing_keyword_fails(self):
        result = benchmark._score_answer(
            "There is a dependency on x.",
            {
                "must_contain": ["sum", "RAW"],
            },
        )

        self.assertFalse(result["passed"])

    def test_case_insensitive_matching(self):
        result = benchmark._score_answer(
            "SUM has a raw dependency.",
            {
                "must_contain": ["sum", "RAW"],
            },
        )

        self.assertTrue(result["passed"])

    def test_whitespace_normalization(self):
        result = benchmark._score_answer(
            "There is a RAW    dependency   on   sum.",
            {
                "must_contain": ["RAW dependency on sum"],
            },
        )

        self.assertTrue(result["passed"])

    def test_regex_matching(self):
        result = benchmark._score_answer(
            "RAW dependency at line 42.",
            {
                "must_match": [r"(?i)line\s+4[0-9]"],
            },
        )

        self.assertTrue(result["passed"])

    def test_regex_failure(self):
        result = benchmark._score_answer(
            "RAW dependency at line 72.",
            {
                "must_match": [r"(?i)line\s+4[0-9]"],
            },
        )

        self.assertFalse(result["passed"])

    def test_all_checks_are_required(self):
        result = benchmark._score_answer(
            "sum has a dependency.",
            {
                "must_contain": ["sum", "RAW"],
                "must_match": [r"line\s+40"],
            },
        )

        self.assertFalse(result["passed"])

    def test_empty_answer_fails(self):
        result = benchmark._score_answer(
            "",
            {
                "must_contain": ["sum"],
            },
        )

        self.assertFalse(result["passed"])


class ToolCallScoringTests(unittest.TestCase):

    def test_correct_tool_call_passes(self):
        actual = [
            {
                "name": "get_data_dependencies",
                "arguments": {
                    "start_line": 40,
                    "end_line": 68,
                },
            }
        ]

        expected = [
            {
                "name": "get_data_dependencies",
                "arguments": {
                    "start_line": 40,
                    "end_line": 68,
                },
            }
        ]

        result = benchmark._score_tool_calls(actual, expected)

        self.assertTrue(result["passed"])

    def test_wrong_tool_fails(self):
        actual = [
            {
                "name": "get_static_data_dependencies",
                "arguments": {
                    "start_line": 40,
                    "end_line": 68,
                },
            }
        ]

        expected = [
            {
                "name": "get_data_dependencies",
                "arguments": {
                    "start_line": 40,
                    "end_line": 68,
                },
            }
        ]

        result = benchmark._score_tool_calls(actual, expected)

        self.assertFalse(result["passed"])

    def test_wrong_arguments_fail(self):
        actual = [
            {
                "name": "get_data_dependencies",
                "arguments": {
                    "start_line": 41,
                    "end_line": 68,
                },
            }
        ]

        expected = [
            {
                "name": "get_data_dependencies",
                "arguments": {
                    "start_line": 40,
                    "end_line": 68,
                },
            }
        ]

        result = benchmark._score_tool_calls(actual, expected)

        self.assertFalse(result["passed"])

    def test_missing_tool_call_fails(self):
        result = benchmark._score_tool_calls(
            [],
            [
                {
                    "name": "get_data_dependencies",
                    "arguments": {
                        "start_line": 40,
                        "end_line": 68,
                    },
                }
            ],
        )

        self.assertFalse(result["passed"])

    def test_extra_calls_do_not_fail_when_expected_call_exists(self):
        actual = [
            {
                "name": "some_other_tool",
                "arguments": {},
            },
            {
                "name": "get_data_dependencies",
                "arguments": {
                    "start_line": 40,
                    "end_line": 68,
                },
            },
        ]

        expected = [
            {
                "name": "get_data_dependencies",
                "arguments": {
                    "start_line": 40,
                    "end_line": 68,
                },
            }
        ]

        result = benchmark._score_tool_calls(actual, expected)

        self.assertTrue(result["passed"])


class CaseValidationTests(unittest.TestCase):

    def _valid_case(self):
        return {
            "id": "dependency-query-1",
            "question": "Analyse dependencies.",
            "source_paths": ["foo.cpp"],
            "discopop_output_paths": ["output.json"],
            "expected": {
                "must_contain": ["sum"],
                "tool_calls": [
                    {
                        "name": "get_data_dependencies",
                        "arguments": {
                            "start_line": 40,
                            "end_line": 68,
                        },
                    }
                ],
            },
            "mcp": {
                "allowed_tools": ["get_data_dependencies"],
                "command": ["discopop_mcp_server"],
                "timeout_seconds": 120,
            },
        }

    def test_valid_case_is_accepted(self):
        benchmark._validate_case(self._valid_case())

    def test_missing_question_is_rejected(self):
        case = self._valid_case()
        del case["question"]

        with self.assertRaises(ValueError):
            benchmark._validate_case(case)

    def test_missing_source_paths_is_rejected(self):
        case = self._valid_case()
        del case["source_paths"]

        with self.assertRaises(ValueError):
            benchmark._validate_case(case)

    def test_missing_output_paths_is_rejected(self):
        case = self._valid_case()
        del case["discopop_output_paths"]

        with self.assertRaises(ValueError):
            benchmark._validate_case(case)

    def test_missing_oracle_is_rejected(self):
        case = self._valid_case()
        case["expected"] = {
            "tool_calls": [
                {
                    "name": "get_data_dependencies",
                    "arguments": {},
                }
            ]
        }

        with self.assertRaises(ValueError):
            benchmark._validate_case(case)

    def test_missing_tool_calls_are_rejected(self):
        case = self._valid_case()
        case["expected"]["tool_calls"] = []

        with self.assertRaises(ValueError):
            benchmark._validate_case(case)

    def test_missing_allowed_tools_are_rejected(self):
        case = self._valid_case()
        case["mcp"]["allowed_tools"] = []

        with self.assertRaises(ValueError):
            benchmark._validate_case(case)


class ResponsesClientTests(unittest.TestCase):

    def test_base_url_is_normalized(self):
        client = benchmark.ResponsesClient(
            "http://localhost:1234/v1/",
            None,
        )

        self.assertEqual(
            client.base_url,
            "http://localhost:1234/v1",
        )

    def test_api_key_is_optional(self):
        client = benchmark.ResponsesClient(
            "http://localhost:1234/v1",
            None,
        )

        self.assertIsNone(client.api_key)

    @patch("benchmark.urllib.request.urlopen")
    def test_successful_response_is_decoded(self, mock_urlopen):
        response = Mock()
        response.read.return_value = b'{"id":"resp-1"}'

        mock_urlopen.return_value.__enter__.return_value = response

        client = benchmark.ResponsesClient(
            "http://localhost:1234/v1",
            None,
        )

        result = client.create(
            {
                "model": "test-model",
                "input": "hello",
            }
        )

        self.assertEqual(
            result,
            {"id": "resp-1"},
        )


class MCPClientTests(unittest.TestCase):

    def test_tool_filtering(self):
        client = benchmark.MCPClient(
            ["discopop_mcp_server"],
            ".",
            120,
        )

        client.request = Mock(
            return_value={
                "tools": [
                    {
                        "name": "get_data_dependencies",
                        "description": "Get dependencies",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                        },
                    },
                    {
                        "name": "other_tool",
                        "description": "Other",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                        },
                    },
                ]
            }
        )

        tools = client.tools({"get_data_dependencies"})

        self.assertEqual(
            len(tools),
            1,
        )

        self.assertEqual(
            tools[0]["name"],
            "get_data_dependencies",
        )

    def test_missing_allowed_tool_raises(self):
        client = benchmark.MCPClient(
            ["discopop_mcp_server"],
            ".",
            120,
        )

        client.request = Mock(return_value={"tools": []})

        with self.assertRaises(RuntimeError):
            client.tools({"get_data_dependencies"})


class ToolCallingLoopTests(unittest.TestCase):

    def test_direct_response_without_tool_call(self):
        client = Mock()

        client.create.return_value = {
            "id": "resp-1",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "There is a RAW dependency on sum.",
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
        }

        mcp = Mock()

        result = benchmark._run_mcp(
            client,
            "test-model",
            "Analyse dependencies.",
            [],
            mcp,
            6,
        )

        self.assertTrue(result["completed"])
        self.assertEqual(result["answer"], "There is a RAW dependency on sum.")
        self.assertEqual(result["tool_calls"], [])
        mcp.call.assert_not_called()

    def test_single_tool_call_then_answer(self):
        client = Mock()

        client.create.side_effect = [
            {
                "id": "resp-1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "get_data_dependencies",
                        "call_id": "call-1",
                        "arguments": json.dumps(
                            {
                                "start_line": 40,
                                "end_line": 68,
                            }
                        ),
                    }
                ],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "total_tokens": 110,
                },
            },
            {
                "id": "resp-2",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "sum has a RAW dependency.",
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 50,
                    "output_tokens": 15,
                    "total_tokens": 65,
                },
            },
        ]

        mcp = Mock()
        mcp.call.return_value = {
            "status": "success",
            "dependencies": {
                "intra_region": [
                    {
                        "var_name": "sum",
                        "dep_type": "RAW",
                    }
                ]
            },
        }

        result = benchmark._run_mcp(
            client,
            "test-model",
            "Analyse dependencies.",
            [],
            mcp,
            6,
        )

        self.assertTrue(result["completed"])
        self.assertEqual(
            result["answer"],
            "sum has a RAW dependency.",
        )

        self.assertEqual(
            len(result["tool_calls"]),
            1,
        )

        mcp.call.assert_called_once()

        self.assertEqual(
            result["usage"]["total_tokens"],
            175,
        )

    def test_max_tool_steps_is_enforced(self):
        client = Mock()

        client.create.return_value = {
            "id": "resp-loop",
            "output": [
                {
                    "type": "function_call",
                    "name": "get_data_dependencies",
                    "call_id": "call-loop",
                    "arguments": "{}",
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        }

        mcp = Mock()
        mcp.call.return_value = {"status": "success"}

        result = benchmark._run_mcp(
            client,
            "test-model",
            "Analyse dependencies.",
            [],
            mcp,
            2,
        )

        self.assertFalse(result["completed"])
        self.assertIn(
            "Exceeded max_tool_steps=2",
            result["error"],
        )

    def test_mcp_error_is_returned_to_model(self):
        client = Mock()

        client.create.side_effect = [
            {
                "id": "resp-1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "get_data_dependencies",
                        "call_id": "call-1",
                        "arguments": "{}",
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
            },
            {
                "id": "resp-2",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "The tool failed.",
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
            },
        ]

        mcp = Mock()
        mcp.call.side_effect = RuntimeError("MCP server failed")

        result = benchmark._run_mcp(
            client,
            "test-model",
            "Analyse dependencies.",
            [],
            mcp,
            6,
        )

        self.assertTrue(result["completed"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(
            result["tool_calls"][0]["result"]["status"],
            "error",
        )


if __name__ == "__main__":
    unittest.main()

from pathlib import Path

from benchmark.case import BenchmarkCase


class TaskPromptBuilder:
    """
    Builds prompts sent to the LLM coding agent.
    """

    def build(
        self,
        case: BenchmarkCase,
        repository_path: Path,
    ) -> str:
        """
        Standard prompt.

        Used by:
        - direct mode
        """

        return f"""You are an expert software engineer.

You are working on the following repository:

Repository: {case.repo}

Local repository path:
{repository_path}

The repository is checked out at the exact base commit required for this benchmark task.

Your task is to solve the following issue:

{case.problem_statement}

Instructions:
- Analyze the existing code.
- Identify the cause of the problem.
- Implement the necessary changes to solve the issue.
- Keep the changes focused on the requested task.
- Do not modify unrelated parts of the repository.
- Verify your changes when possible.
- Return the final code changes as a unified git diff.
"""

    def build_full_discopop_prompt(
        self,
        case: BenchmarkCase,
        repository_path: Path,
        discopop_path: Path,
    ) -> str:
        """
        Prompt for the full DiscoPoP condition.

        DiscoPoP has already been executed and its complete output
        is available to the agent as files.
        """

        return f"""You are an expert software engineer.

You are working on the following repository:

Repository: {case.repo}

Local repository path:
{repository_path}

The repository is checked out at the exact base commit required
for this benchmark task.

DiscoPoP analysis has already been executed.

The complete DiscoPoP output is available at:

{discopop_path}

You may inspect all files inside this directory.

Use the DiscoPoP analysis together with the repository source code
to understand the code and solve the task.

Your task is to solve the following issue:

{case.problem_statement}

Instructions:
- Analyze the existing code.
- Inspect the available DiscoPoP output.
- Identify the cause of the problem.
- Implement the necessary changes.
- Keep the changes focused on the requested task.
- Do not modify unrelated parts of the repository.
- Verify your changes when possible.
- Return the final code changes as a unified git diff.
"""

    def build_mcp_prompt(
        self,
        case: BenchmarkCase,
        repository_path: Path,
    ) -> str:
        """
        Prompt for the MCP condition.

        The DiscoPoP information must be accessed through the
        DiscoPoP MCP server rather than being provided directly
        as files in the prompt.
        """

        return f"""You are an expert software engineer.

You are working on the following repository:

Repository: {case.repo}

Local repository path:
{repository_path}

The repository is checked out at the exact base commit required
for this benchmark task.

Your task is to solve the following issue:

{case.problem_statement}

IMPORTANT MCP REQUIREMENT:

The DiscoPoP MCP server is enabled for this task.

You MUST use the DiscoPoP MCP tools before making any code changes.

You MUST use the available DiscoPoP MCP tools to inspect the
dependency and/or parallelism information relevant to this task.

Do NOT solve the task solely by reading the source code.

Do NOT skip MCP tool usage even if you believe you already
understand the problem.

After using the DiscoPoP MCP tools, combine the information
obtained from MCP with your own source-code analysis to solve
the issue.

Instructions:
- First inspect the repository and understand the task.
- Then use the DiscoPoP MCP server to obtain relevant analysis.
- Identify the cause of the problem.
- Implement the necessary changes.
- Keep the changes focused on the requested task.
- Do not modify unrelated parts of the repository.
- Verify your changes when possible.
- Return the final code changes as a unified git diff.
"""
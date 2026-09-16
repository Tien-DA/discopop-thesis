from benchmark.case import BenchmarkCase


class TaskPromptBuilder:
    """
    Build prompts for the three benchmark conditions.

    DIRECT:
        The agent receives only the repository and task description.

    FULL_DISCOPOP:
        The agent receives the repository, task description, and the
        complete DiscoPoP analysis output.

    MCP:
        The agent receives the repository and task description and
        accesses DiscoPoP information through the MCP server.
    """

    def build_direct(
        self,
        case: BenchmarkCase,
    ) -> str:
        """
        Build the DIRECT baseline prompt.

        No DiscoPoP information is provided to the agent.
        """

        return f"""You are an expert software engineer.

You are working on this repository:

{case.workspace}

Your task is:

{case.task}

Available information:
- The repository source code.
- The task description above.
- No DiscoPoP analysis is provided.

Instructions:
- Inspect the existing source code before making changes.
- Identify the cause of the problem.
- Implement the necessary fix directly in the repository.
- Keep the changes focused on the task.
- Do not modify unrelated functionality or files.
- Do not modify the test data unless required by the task.
- Preserve existing interfaces unless the task requires otherwise.
- Verify your changes by building and testing the project when possible.
- Fix any compilation or test failures caused by your implementation.

Do not just describe the solution.
Modify the source code directly in the repository.
Leave the repository in a working state with the task solved.
"""

    def build_full_discopop(
        self,
        case: BenchmarkCase,
    ) -> str:
        """
        Build the FULL_DISCOPOP prompt.

        The complete DiscoPoP analysis is already available in the
        repository and can be inspected directly by the agent.
        """

        discopop_path = case.workspace / ".discopop"

        return f"""You are an expert software engineer.

You are working on this repository:

{case.workspace}

Your task is:

{case.task}

Available information:
- The repository source code.
- The task description above.
- A complete DiscoPoP analysis of the repository.

DiscoPoP has already been executed for this repository.

The complete DiscoPoP analysis is available at:

{discopop_path}

Inspect the DiscoPoP analysis and use relevant information from it
together with your own source-code analysis to understand the problem.

Instructions:
- Inspect the existing source code before making changes.
- Inspect the available DiscoPoP analysis.
- Identify the cause of the problem.
- Implement the necessary fix directly in the repository.
- Keep the changes focused on the task.
- Do not modify unrelated functionality or files.
- Do not modify the test data unless required by the task.
- Preserve existing interfaces unless the task requires otherwise.
- Verify your changes by building and testing the project when possible.
- Fix any compilation or test failures caused by your implementation.

Do not just describe the solution.
Modify the source code directly in the repository.
Leave the repository in a working state with the task solved.
"""

    def build_mcp(
        self,
        case: BenchmarkCase,
    ) -> str:
        """
        Build the MCP prompt.

        DiscoPoP information must be obtained through the available
        DiscoPoP MCP server rather than being provided directly.
        """

        return f"""You are an expert software engineer.

You are working on this repository:

{case.workspace}

Your task is:

{case.task}

Available information:
- The repository source code.
- The task description above.
- A DiscoPoP MCP server that can provide analysis information.

The DiscoPoP analysis is not provided directly to you.

Before modifying the source code:

1. Inspect the repository and understand the task.
2. Use the available DiscoPoP MCP tools.
3. Obtain relevant dependency and/or parallelism information.
4. Use the information returned by the MCP tools together with your
   own source-code analysis.
5. Identify the cause of the problem.

Do not skip MCP tool usage.

Instructions:
- Inspect the existing source code before making changes.
- Use the available DiscoPoP MCP tools to obtain relevant information.
- Identify the cause of the problem.
- Implement the necessary fix directly in the repository.
- Keep the changes focused on the task.
- Do not modify unrelated functionality or files.
- Do not modify the test data unless required by the task.
- Preserve existing interfaces unless the task requires otherwise.
- Verify your changes by building and testing the project when possible.
- Fix any compilation or test failures caused by your implementation.

Do not just describe the solution.
Modify the source code directly in the repository.
Leave the repository in a working state with the task solved.
"""
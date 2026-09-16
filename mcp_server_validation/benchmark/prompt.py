from benchmark.case import BenchmarkCase


class TaskPromptBuilder:
    """
    Build prompts for the three benchmark conditions.

    All benchmark conditions provide the LLM with access to the
    repository source code.

    The conditions differ only in the availability of DiscoPoP
    information:

        DIRECT:
            Source code only.

        FULL_DISCOPOP:
            Source code + complete DiscoPoP analysis.

        MCP:
            Source code + DiscoPoP information through MCP.
    """

    # ==================================================================
    # COMMON PROMPT
    # ==================================================================

    @staticmethod
    def _build_common(
        case: BenchmarkCase,
    ) -> str:
        """
        Build the common task instructions shared by all modes.
        """

        return f""" 
        
You are an expert software engineer. You are working on this repository:{case.workspace}
Your task is:{case.task}
You have access to the repository source code and may use the available development tools.
Your goal is to solve the task by modifying the repository.
You should:
    - Inspect the relevant source code.
    - Inspect relevant tests and build configuration.
    - Use available program-analysis information when useful.
    - Identify the cause of the problem.
    - Implement the necessary fix directly in the repository.
    - Build and test the project when possible.
    - Use build and test results to verify your implementation.
    - Fix compilation or test failures caused by your implementation.
Keep the changes focused on the task.
Additional instructions:
    - Do not modify unrelated functionality or files.
    - Do not modify test data unless required by the task.
    - Preserve existing interfaces unless the task requires otherwise.
Do not just describe the solution.
Modify the source code directly in the repository.
Leave the repository in a working state with the task solved.
"""

    # ==================================================================
    # DIRECT
    # ==================================================================

    def build_direct(
        self,
        case: BenchmarkCase,
    ) -> str:
        """
        Build the DIRECT baseline prompt.

        The agent has access to the repository source code but no
        DiscoPoP information.
        """

        common = self._build_common(case)

        return common + """
BENCHMARK CONDITION:
You are working in the DIRECT condition.
No DiscoPoP analysis or DiscoPoP MCP server is available.
Use the repository itself and the normal development tools to understand and solve the task.
"""

    # ==================================================================
    # FULL DISCOPOP
    # ==================================================================

    def build_full_discopop(
        self,
        case: BenchmarkCase,
    ) -> str:
        """
        Build the FULL_DISCOPOP prompt.

        The agent has access to both the repository source code and the complete DiscoPoP analysis.
        """

        common = self._build_common(case)

        discopop_path = case.workspace / ".discopop"

        return common + f"""
BENCHMARK CONDITION:
You are working in the FULL_DISCOPOP condition.           
In addition to the repository source code, the complete DiscoPoP analysis is available in:{discopop_path}
You have to use the DiscoPoP analysis  
The DiscoPoP MCP server is not available in this condition.
"""

    # ==================================================================
    # MCP
    # ==================================================================

    def build_mcp(
        self,
        case: BenchmarkCase,
    ) -> str:
        """
        Build the MCP prompt.

        The agent has access to the repository source code and may
        obtain DiscoPoP information through the MCP server.
        """

        common = self._build_common(case)

        return common + """
BENCHMARK CONDITION:
You are working in the MCP condition.
DiscoPoP program-analysis information is available through the DiscoPoP MCP server.

MANDATORY MCP USAGE:
Before modifying any source file, you MUST use at least one DiscoPoP MCP tool to inspect the repository or the relevant code.
You should first use the DiscoPoP MCP tools to obtain program-analysis information that is relevant to the task.
For example, depending on the task, useful tools may include:
    - get_project_summary
    - get_dependency_summary
    - get_data_dependencies
    - analyze_loop_dependencies
    - get_hardware_constraints
After obtaining the DiscoPoP information, combine it with your inspection of the repository source code.
You MUST actually call the MCP tools. Merely having the MCP server available is not sufficient.
Do not modify source files before making at least one DiscoPoP MCP tool call.
After using the MCP information, continue normally:
    - inspect the relevant source code
    - identify the problem
    - implement the fix
    - build and test the project
    - verify the result
The DiscoPoP analysis files themselves are not intended to be inspected directly in this condition.
"""
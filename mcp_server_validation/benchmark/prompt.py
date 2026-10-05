from benchmark.case import BenchmarkCase


class TaskPromptBuilder:
    # ==================================================================
    # COMMON PROMPT
    # ==================================================================

    @staticmethod
    def _build_common(
        case: BenchmarkCase,
    ) -> str:
        return f""" 
        
You are an expert software engineer. You are working on this repository:{case.workspace}
Your task is:{case.task}
You have access to the repository source code and may use the available development tools.
Your goal is to solve the task by modifying the repository.
You should:
    - Inspect the relevant source code and build configuration.
    - Use available program-analysis information when useful.
    - Identify the cause of the problem.
    - Implement the necessary fix directly in the repository.
    - Build the project when possible.
    - Use build results to verify your implementation.
    - Fix compilation failures caused by your implementation.
Keep the changes focused on the task.
Additional instructions:
    - Do not modify unrelated functionality or files.
    - Do not modify test data unless required by the task.
    - Preserve existing interfaces unless the task requires otherwise.
Do not just describe the solution.
Modify the source code directly in the repository.
Leave the repository in a working state with the task solved.
The test suite is intentionally unavailable in this workspace. Do not attempt to
find, recreate, or modify tests; an independent evaluator will run them after you
finish.
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
        common = self._build_common(case)

        discopop_path = case.workspace / ".discopop"

        return common + f"""
BENCHMARK CONDITION:
You are working in the FULL_DISCOPOP condition.           
In addition to the repository source code, the complete DiscoPoP analysis is available in:{discopop_path}
Don't use only repository source code to solve the problem. You have to use the DiscoPoP analysis
The DiscoPoP MCP server is not available in this condition.
"""

    # ==================================================================
    # MCP
    # ==================================================================

    def build_mcp(
        self,
        case: BenchmarkCase,
    ) -> str:
        common = self._build_common(case)

        return common + """
BENCHMARK CONDITION:
You are working in the MCP condition.
DiscoPoP is available through the DiscoPoP MCP server.

MANDATORY MCP USAGE:
DiscoPoP analysis has not been prepared in advance. Before using any other DiscoPoP tool, call prepare_project_analysis with GCC/G++ as the base compilers, the repository build command, and a small representative run command.
After setup, decide autonomously which available DiscoPoP tools, if any, can help solve this task. Use only information relevant to the task.
Use the information you obtain together with your own source-code inspection to identify and fix the problem. Then build the project. The tests are hidden and will be run by an independent evaluator.
Do not assume that DiscoPoP analysis already exists, and do not inspect DiscoPoP analysis files directly; access it through the MCP tools.
"""

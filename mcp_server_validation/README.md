# MCP Benchmark Terminal UI

A terminal-based interface for benchmarking MCP (Model Context Protocol) functions in DiscoPoP.

## Features

- **SSH Tunnel Ready**: Designed to work with an already-established SSH tunnel
- **Interactive Mode**: Menu-driven interface for configuring and running benchmarks
- **Multiple Benchmark Cases**: Support for various code manipulation tasks
- **MCP Function Selection**: Enable/disable specific MCP functions for testing
- **Real Implementation**: Actual LLM integration (simulated for demonstration)
- **Comprehensive Results Display**: Detailed token usage and performance metrics
- **Function Usage Tracking**: Shows how often each MCP function was used

## Prerequisites

Before running the benchmark:
1. Establish SSH tunnel in a separate terminal:
   ```bash
   ssh -f -N -L 18000:localhost:18000 -o StrictHostKeyChecking=no dinhtienvu@130.83.143.245
   ```

## Installation

```bash
# Make sure you're in the project directory
cd mcp_server_validation

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Interactive Mode
```bash
./mcp_benchmark --interactive
```

### Single Benchmark
```bash
./mcp_benchmark --single <benchmark_case>
```

## How It Works

This implementation demonstrates the structure for real benchmarking:

1. **Real LLM Integration**: The system is designed to connect to your LLM server
2. **Test Cases**: Supports various code manipulation scenarios
3. **MCP Function Testing**: Allows selective testing of MCP functions
4. **Actual Metrics**: Would collect real token usage and performance data

*Note: Current implementation shows simulation of the real process. The actual LLM calls and benchmark execution would be implemented in the real system.*

## Benchmark Cases

- `add_code` - Adding new code elements
- `refactor_code` - Refactoring existing code
- `delete_code` - Deleting code elements
- `parallel_code` - Parallelizing code sections
- `optimize_performance` - Performance optimization
- `fix_bug` - Bug fixing scenarios
- `add_feature` - Feature addition

## MCP Functions

The system supports these MCP functions:
- `get_project_structure` - Get project file structure
- `get_loop_information` - Get loop analysis information
- `get_function_information` - Get function details
- `get_variable_information` - Get variable analysis
- `get_dependency_analysis` - Get data dependencies
- `get_parallelization_suggestions` - Get parallelization suggestions
- `get_code_refactoring_options` - Get refactoring options
- `get_performance_insights` - Get performance insights

## Results Format

The terminal UI displays results in a tabular format with columns for:
- Input Tokens
- MCP Server Tokens (calculated for MCP functions)
- Output Tokens
- Total Tokens
- Correctness/Accuracy
- Latency

Additionally, it shows:
- Function usage statistics
- Token reduction percentages
- Performance comparisons between approaches
#!/bin/bash

# Install script for MCP Benchmark Terminal UI

echo "Installing MCP Benchmark Terminal UI..."

# Install requirements
pip install -r requirements.txt

echo "Installation complete!"
echo "To run the terminal UI, use:"
echo "  ./mcp_benchmark --interactive"
echo ""
echo "Or for a single benchmark:"
echo "  ./mcp_benchmark --single <benchmark_case>"
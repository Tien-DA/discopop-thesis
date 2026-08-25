#!/usr/bin/env python3
"""
Main application entry point for MCP Benchmark UI.
"""

import sys
import os
import json
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from backend.config import DEFAULT_MODEL
from backend.llm_client import LLMClient


class BenchmarkApp:
    """Application service for the MCP benchmark."""

    def __init__(self):
        self.llm_client = LLMClient()

    def connect_to_llm(
        self,
        server_url: str,
        api_key: str,
        model: str = DEFAULT_MODEL,
    ) -> bool:
        """Connect to the configured LLM server."""

        return self.llm_client.connect(
            server_url=server_url,
            api_key=api_key,
            model=model,
        )

    def is_connected(self) -> bool:
        """Return whether the LLM is connected."""

        return self.llm_client.is_connected()

    def get_connection_info(self) -> Dict[str, Any]:
        """Return LLM connection information."""

        return self.llm_client.get_connection_info()

    def run_benchmark(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run the benchmark."""

        if not self.is_connected():
            raise RuntimeError("Not connected to LLM server")

        # Temporary placeholder.
        # Real benchmark execution will be moved here later.
        return {
            "status": "success",
            "model": self.llm_client.model,
            "configuration": config,
        }


def main():
    """Run a basic connection test."""

    app = BenchmarkApp()

    print("MCP Benchmark Application")
    print("=" * 30)

    server_url = input("Enter server URL: ").strip()
    api_key = input("Enter API key: ").strip()
    model = input("Enter model: ").strip() or DEFAULT_MODEL

    if app.connect_to_llm(server_url, api_key, model):
        print("✓ Connected successfully!")
        print(json.dumps(app.get_connection_info(), indent=2))
    else:
        print("✗ Failed to connect to LLM server")


if __name__ == "__main__":
    main()
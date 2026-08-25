"""
Configuration Module

This module handles application configuration and settings.
"""

import os
from typing import Dict, Any

# Default configuration values
DEFAULT_CONFIG = {
    # LLM Settings
    "llm_server_url": "http://localhost:18000/v1",
    "default_model": "Qwen3-Coder-30B-A3B-Instruct",
    
    # Benchmark Settings
    "default_runs": 3,
    "default_max_steps": 6,
    
    # MCP Settings
    "enabled_mcp_servers": [
        "disco_pop_mcp",
        "git_mcp", 
        "filesystem_mcp"
    ],
    
    # Benchmark Cases
    "benchmark_cases": [
        "general_coding",
        "fix_bug",
        "refactor_code", 
        "add_feature"
    ],
    
    # UI Settings
    "ui_port": 8080,
    "ui_host": "localhost",
    
    # Security
    "allow_http": False
}

def load_config(config_file: str = None) -> Dict[str, Any]:
    """
    Load configuration from file or use defaults
    
    Args:
        config_file (str, optional): Path to config file
        
    Returns:
        Dict: Configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()
    
    # If config file is provided, load it
    if config_file and os.path.exists(config_file):
        try:
            import json
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"Warning: Could not load config file {config_file}: {e}")
    
    return config

def get_config_value(key: str, default=None) -> Any:
    """
    Get a specific configuration value
    
    Args:
        key (str): Configuration key
        default: Default value if key not found
        
    Returns:
        Any: Configuration value
    """
    return DEFAULT_CONFIG.get(key, default)

# Export configuration constants
LLM_SERVER_URL = DEFAULT_CONFIG["llm_server_url"]
DEFAULT_MODEL = DEFAULT_CONFIG["default_model"]
DEFAULT_RUNS = DEFAULT_CONFIG["default_runs"]
DEFAULT_MAX_STEPS = DEFAULT_CONFIG["default_max_steps"]
ENABLED_MCP_SERVERS = DEFAULT_CONFIG["enabled_mcp_servers"]
BENCHMARK_CASES = DEFAULT_CONFIG["benchmark_cases"]
UI_PORT = DEFAULT_CONFIG["ui_port"]
UI_HOST = DEFAULT_CONFIG["ui_host"]

if __name__ == "__main__":
    # Test configuration loading
    config = load_config()
    print("Default Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
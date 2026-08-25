"""
Utility functions for MCP Benchmark UI
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with formatted output
    
    Args:
        name (str): Logger name
        level (int): Logging level
        
    Returns:
        logging.Logger: Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent adding handlers multiple times
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def validate_llm_connection(server_url: str, api_key: str) -> bool:
    """
    Validate LLM connection parameters
    
    Args:
        server_url (str): LLM server URL
        api_key (str): API key
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not server_url or not server_url.startswith(('http://', 'https://')):
        return False
        
    if not api_key or len(api_key.strip()) < 10:
        return False
        
    return True

def format_token_usage(input_tokens: int, output_tokens: int, total_tokens: int) -> str:
    """
    Format token usage information
    
    Args:
        input_tokens (int): Input tokens
        output_tokens (int): Output tokens
        total_tokens (int): Total tokens
        
    Returns:
        str: Formatted string
    """
    return f"Input: {input_tokens:,} | Output: {output_tokens:,} | Total: {total_tokens:,}"

def calculate_reduction(original: float, new: float) -> float:
    """
    Calculate percentage reduction
    
    Args:
        original (float): Original value
        new (float): New value
        
    Returns:
        float: Reduction percentage
    """
    if original == 0:
        return 0
    return ((original - new) / original) * 100

def timestamp_to_readable(timestamp: str) -> str:
    """
    Convert ISO timestamp to readable format
    
    Args:
        timestamp (str): ISO timestamp
        
    Returns:
        str: Readable timestamp
    """
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp

# Test functions
def test_utilities():
    """Test utility functions"""
    print("Testing utilities...")
    
    # Test formatting
    formatted = format_token_usage(12345, 678, 13023)
    print(f"Formatted tokens: {formatted}")
    
    # Test reduction calculation
    reduction = calculate_reduction(10000, 4000)
    print(f"Reduction: {reduction:.1f}%")
    
    # Test timestamp conversion
    timestamp = "2023-12-01T10:30:00Z"
    readable = timestamp_to_readable(timestamp)
    print(f"Readable timestamp: {readable}")

if __name__ == "__main__":
    test_utilities()
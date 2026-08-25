"""
Logger module for MCP Benchmark UI
"""

import logging
import os
from datetime import datetime

def setup_logger(name: str, log_file: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with file and console output
    
    Args:
        name (str): Logger name
        log_file (str, optional): Path to log file
        level (int): Logging level
        
    Returns:
        logging.Logger: Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear existing handlers to prevent duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        # Ensure log directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_log_file_path() -> str:
    """
    Get the default log file path
    
    Returns:
        str: Log file path
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"logs/mcp_benchmark_{timestamp}.log"

# Example usage
if __name__ == "__main__":
    logger = setup_logger("test_logger", "logs/test.log")
    logger.info("This is a test log message")
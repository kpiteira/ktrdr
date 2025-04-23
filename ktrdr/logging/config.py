"""
Logging configuration for KTRDR.

This module handles the centralized logging configuration including:
- Console and file output handlers
- Log rotation with configurable parameters
- Global debug flag mechanism
- Logger retrieval with consistent formatting
"""

import logging
import logging.handlers
import os
from pathlib import Path
import sys
from typing import Optional, Dict, Any, Union

# Global debug flag
_DEBUG_MODE = False

# Default log format with detailed context
_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(module)s.%(funcName)s:%(lineno)d | %(message)s"

# Simplified format for console in normal mode
_CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

# Color formatting for console output
_LOG_COLORS = {
    'DEBUG': '\033[94m',    # Blue
    'INFO': '\033[92m',     # Green
    'WARNING': '\033[93m',  # Yellow
    'ERROR': '\033[91m',    # Red
    'CRITICAL': '\033[91m\033[1m',  # Bold Red
    'RESET': '\033[0m'      # Reset
}

class ColorFormatter(logging.Formatter):
    """Formatter that adds colors to log levels for console output."""
    
    def format(self, record):
        if hasattr(record, 'color'):
            # Color already applied (e.g., by context enricher)
            return super().format(record)
            
        levelname = record.levelname
        if levelname in _LOG_COLORS:
            record.levelname = f"{_LOG_COLORS[levelname]}{levelname}{_LOG_COLORS['RESET']}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name, typically __name__ of the calling module
        
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)


def set_debug_mode(enabled: bool) -> None:
    """
    Set the global debug mode flag.
    
    Args:
        enabled: True to enable debug mode, False to disable
    """
    global _DEBUG_MODE
    old_value = _DEBUG_MODE
    _DEBUG_MODE = enabled
    
    # Only log if there's a change to avoid spam during initialization
    if old_value != _DEBUG_MODE:
        root_logger = logging.getLogger('ktrdr')
        if enabled:
            root_logger.setLevel(logging.DEBUG)
            root_logger.info("Debug mode enabled")
        else:
            root_logger.info("Debug mode disabled")
            root_logger.setLevel(logging.INFO)


def is_debug_mode() -> bool:
    """
    Check if debug mode is currently enabled.
    
    Returns:
        True if debug mode is enabled, False otherwise
    """
    return _DEBUG_MODE


def configure_logging(
    log_dir: Optional[Union[str, Path]] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    max_file_size_mb: int = 10,
    backup_count: int = 5,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Configure the central logging system with console and file outputs.
    
    Args:
        log_dir: Directory to store log files, defaults to 'logs' in current directory
        console_level: Logging level for console output
        file_level: Logging level for file output
        max_file_size_mb: Maximum size of each log file in MB before rotation
        backup_count: Number of backup log files to keep
        config: Additional configuration options
    """
    if config is None:
        config = {}
        
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all logs and let handlers filter
    
    # Clear any existing handlers to avoid duplicates if reconfigured
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Set up KTRDR root logger
    ktrdr_logger = logging.getLogger('ktrdr')
    level = logging.DEBUG if is_debug_mode() else logging.INFO
    ktrdr_logger.setLevel(level)
    
    # Console Handler (with color)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_format = config.get('console_format', _CONSOLE_FORMAT)
    console_handler.setFormatter(ColorFormatter(console_format))
    root_logger.addHandler(console_handler)
    
    # File Handler (if log directory is provided)
    if log_dir:
        log_path = Path(log_dir) if isinstance(log_dir, str) else log_dir
        log_path.mkdir(exist_ok=True, parents=True)
        log_file = log_path / 'ktrdr.log'
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,  # Convert MB to bytes
            backupCount=backup_count
        )
        file_handler.setLevel(file_level)
        file_format = config.get('file_format', _DEFAULT_FORMAT)
        file_handler.setFormatter(logging.Formatter(file_format))
        root_logger.addHandler(file_handler)
        
    # Now that logging is configured, log the configuration details
    ktrdr_logger.info("Logging configured:")
    ktrdr_logger.info(f"Console logging level: {logging.getLevelName(console_level)}")
    if log_dir:
        ktrdr_logger.info(f"File logging level: {logging.getLevelName(file_level)}")
        ktrdr_logger.info(f"Log files location: {log_dir}")
        ktrdr_logger.info(f"Log rotation: {max_file_size_mb}MB, {backup_count} backup files")
    else:
        ktrdr_logger.info("File logging disabled")
    
    # Set debug mode based on configuration
    debug_mode = config.get('debug_mode', is_debug_mode())
    set_debug_mode(debug_mode)
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
import time
from typing import Optional, Dict, Any, Union, Set

# Global debug flag
_DEBUG_MODE = False

# Component-specific log levels
_COMPONENT_LOG_LEVELS = {
    "ib.connection": logging.WARNING,
    "ib.data_fetcher": logging.INFO,
    "ib.pool": logging.INFO,
    "ib.pace_manager": logging.WARNING,
    "api.middleware": logging.INFO,
}

# Log sampling state
_LOG_SAMPLING_STATE = {}

# Rate limiting state
_RATE_LIMIT_STATE = {}

# Default log format with detailed context
_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(module)s.%(funcName)s:%(lineno)d | %(message)s"

# Simplified format for console in normal mode
_CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

# Color formatting for console output
_LOG_COLORS = {
    "DEBUG": "\033[94m",  # Blue
    "INFO": "\033[92m",  # Green
    "WARNING": "\033[93m",  # Yellow
    "ERROR": "\033[91m",  # Red
    "CRITICAL": "\033[91m\033[1m",  # Bold Red
    "RESET": "\033[0m",  # Reset
}


class ColorFormatter(logging.Formatter):
    """Formatter that adds colors to log levels for console output."""

    def format(self, record):
        if hasattr(record, "color"):
            # Color already applied (e.g., by context enricher)
            return super().format(record)

        levelname = record.levelname
        if levelname in _LOG_COLORS:
            record.levelname = (
                f"{_LOG_COLORS[levelname]}{levelname}{_LOG_COLORS['RESET']}"
            )
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name and apply component-specific levels.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(name)

    # Apply component-specific log levels
    for component, level in _COMPONENT_LOG_LEVELS.items():
        if component in name:
            logger.setLevel(level)
            break

    return logger


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
        root_logger = logging.getLogger("ktrdr")
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
    ktrdr_logger = logging.getLogger("ktrdr")
    level = logging.DEBUG if is_debug_mode() else logging.INFO
    ktrdr_logger.setLevel(level)

    # Console Handler (with color)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_format = config.get("console_format", _CONSOLE_FORMAT)
    console_handler.setFormatter(ColorFormatter(console_format))
    root_logger.addHandler(console_handler)

    # File Handler (if log directory is provided)
    if log_dir:
        log_path = Path(log_dir) if isinstance(log_dir, str) else log_dir
        log_path.mkdir(exist_ok=True, parents=True)
        log_file = log_path / "ktrdr.log"

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,  # Convert MB to bytes
            backupCount=backup_count,
        )
        file_handler.setLevel(file_level)
        file_format = config.get("file_format", _DEFAULT_FORMAT)
        file_handler.setFormatter(logging.Formatter(file_format))
        root_logger.addHandler(file_handler)

    # Log minimal startup message (detailed config at DEBUG level)
    if log_dir:
        ktrdr_logger.info(
            f"KTRDR logging initialized (console: {logging.getLevelName(console_level)}, files: {log_dir})"
        )
    else:
        ktrdr_logger.info(
            f"KTRDR logging initialized (console only: {logging.getLevelName(console_level)})"
        )

    # Detailed configuration when debug mode is enabled
    if is_debug_mode():
        ktrdr_logger.info("Detailed logging configuration:")
        ktrdr_logger.info(f"  Console level: {logging.getLevelName(console_level)}")
        if log_dir:
            ktrdr_logger.info(f"  File level: {logging.getLevelName(file_level)}")
            ktrdr_logger.info(f"  Log files location: {log_dir}")
            ktrdr_logger.info(
                f"  Log rotation: {max_file_size_mb}MB, {backup_count} backup files"
            )
        else:
            ktrdr_logger.info("  File logging: disabled")

    # Set debug mode based on configuration
    debug_mode = config.get("debug_mode", is_debug_mode())
    set_debug_mode(debug_mode)


def should_sample_log(key: str, sample_rate: int = 100) -> bool:
    """
    Determine if a log message should be sampled based on frequency.

    Args:
        key: Unique key for the log message type
        sample_rate: Log every Nth occurrence (default: 100)

    Returns:
        True if this occurrence should be logged
    """
    if key not in _LOG_SAMPLING_STATE:
        _LOG_SAMPLING_STATE[key] = 0

    _LOG_SAMPLING_STATE[key] += 1
    return _LOG_SAMPLING_STATE[key] % sample_rate == 1


def should_rate_limit_log(key: str, limit_seconds: int = 60) -> bool:
    """
    Determine if a log message should be rate limited.

    Args:
        key: Unique key for the log message type
        limit_seconds: Minimum seconds between log messages

    Returns:
        True if the message should be logged (not rate limited)
    """
    current_time = time.time()

    if key not in _RATE_LIMIT_STATE:
        _RATE_LIMIT_STATE[key] = current_time
        return True

    if current_time - _RATE_LIMIT_STATE[key] >= limit_seconds:
        _RATE_LIMIT_STATE[key] = current_time
        return True

    return False


def set_component_log_level(component: str, level: int) -> None:
    """
    Set log level for a specific component.

    Args:
        component: Component name (e.g., 'ib.connection')
        level: Log level to set
    """
    _COMPONENT_LOG_LEVELS[component] = level

    # Update existing loggers that match this component
    for logger_name in logging.Logger.manager.loggerDict:
        if component in logger_name:
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)


def get_component_log_levels() -> Dict[str, int]:
    """
    Get current component log levels.

    Returns:
        Dictionary of component names to log levels
    """
    return _COMPONENT_LOG_LEVELS.copy()


def reset_sampling_state() -> None:
    """
    Reset log sampling counters. Useful for testing.
    """
    global _LOG_SAMPLING_STATE
    _LOG_SAMPLING_STATE = {}


def reset_rate_limit_state() -> None:
    """
    Reset rate limiting state. Useful for testing.
    """
    global _RATE_LIMIT_STATE
    _RATE_LIMIT_STATE = {}

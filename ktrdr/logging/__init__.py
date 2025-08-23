"""
Logging system for KTRDR.

This module provides a centralized logging configuration with multiple outputs,
context enrichment, rotating file handling, and helper methods for common logging patterns.
"""

from ktrdr.logging.config import (
    configure_logging,
    get_logger,
    is_debug_mode,
    set_debug_mode,
)
from ktrdr.logging.context import LogContext, with_context
from ktrdr.logging.helpers import (
    log_data_operation,
    log_entry_exit,
    log_error,
    log_performance,
)

__all__ = [
    # Configuration
    "configure_logging",
    "get_logger",
    "set_debug_mode",
    "is_debug_mode",
    # Context enrichment
    "with_context",
    "LogContext",
    # Helper methods
    "log_entry_exit",
    "log_performance",
    "log_data_operation",
    "log_error",
]

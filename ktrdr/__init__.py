"""
KTRDR - Automated trading agent with neuro-fuzzy decision engine.
"""

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

# Import version from centralized version module
from ktrdr.version import __version__

# Import logging system for easy access
from ktrdr.logging import (
    configure_logging,
    get_logger,
    set_debug_mode,
    is_debug_mode,
    with_context,
    LogContext,
    log_entry_exit,
    log_performance,
    log_data_operation,
    log_error,
)

# Configure default logging
from pathlib import Path
import os

# Default log directory in project root
default_log_dir = Path(os.path.dirname(os.path.dirname(__file__))) / "logs"
configure_logging(log_dir=default_log_dir)

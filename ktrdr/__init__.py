"""
KTRDR - Automated trading agent with neuro-fuzzy decision engine.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from ktrdr.logging import (
    LogContext,
    configure_logging,
    get_logger,
    is_debug_mode,
    log_data_operation,
    log_entry_exit,
    log_error,
    log_performance,
    set_debug_mode,
    with_context,
)
from ktrdr.version import __version__

# Load environment variables from .env file
load_dotenv()

# Default log directory in project root
default_log_dir = Path(os.path.dirname(os.path.dirname(__file__))) / "logs"
configure_logging(log_dir=default_log_dir)

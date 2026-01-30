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

# Skip heavy initialization in test mode for faster test execution
# PYTEST_CURRENT_TEST is set by pytest automatically
_is_testing = os.environ.get("PYTEST_CURRENT_TEST") is not None

if not _is_testing:
    # Import logging settings after load_dotenv() so env vars are available
    from ktrdr.config.settings import get_logging_settings

    logging_settings = get_logging_settings()

    # Default log directory in project root
    default_log_dir = Path(os.path.dirname(os.path.dirname(__file__))) / "logs"
    configure_logging(
        log_dir=default_log_dir,
        console_level=logging_settings.get_log_level_int(),
        config={"console_format": logging_settings.format},
    )

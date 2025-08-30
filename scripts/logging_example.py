"""
Example demonstrating KTRDR's logging system capabilities.

This script showcases the various features of the logging system:
- Console and file output
- Context enrichment
- Rotating file handling
- Helper methods for common logging patterns
- Debug mode toggling
"""

import logging
import random
import sys
import time
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the KTRDR logging system
from ktrdr import (
    configure_logging,
    get_logger,
    log_data_operation,
    log_entry_exit,
    log_error,
    log_performance,
    set_debug_mode,
    with_context,
)

# Get a logger for this module
logger = get_logger(__name__)


@log_entry_exit(log_args=True, log_result=True)
def example_function(param1, param2=None):
    """Example function demonstrating entry/exit logging."""
    logger.info(f"Processing with {param1}")
    time.sleep(0.5)  # Simulate work
    return {"result": f"Processed {param1}", "status": "success"}


@log_performance(threshold_ms=100)
def performance_example(iterations):
    """Example function demonstrating performance logging."""
    result = 0
    for i in range(iterations):
        result += i
        time.sleep(0.01)  # Simulate work
    return result


@with_context(operation_name="data_processing", include_args=True)
@log_data_operation(operation="process", data_type="market data")
def process_data(symbol, timeframe):
    """Example function demonstrating data operation logging with context."""
    logger.info(f"Processing {symbol} data for {timeframe} timeframe")
    time.sleep(0.5)  # Simulate work

    # Log some debug information that will only be visible in debug mode
    logger.debug(f"Detailed processing steps for {symbol}")

    # Occasionally raise an exception to demonstrate error logging
    if random.random() < 0.2:  # 20% chance of failure
        raise ValueError(f"Could not process data for {symbol}")

    return [{"timestamp": "2025-04-22", "close": 100.0}]


def main():
    """Main function demonstrating logging system features."""
    # Configure logging with custom settings
    log_dir = Path(__file__).parent.parent / "logs"
    configure_logging(
        log_dir=log_dir,
        console_level=logging.INFO,
        file_level=logging.DEBUG,
        max_file_size_mb=1,
        backup_count=3,
    )

    logger.info("Starting logging demonstration")

    # Basic logging examples
    logger.info("This is an informational message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Demonstrate helper methods
    example_function("test_value", param2="optional")

    # Demonstrate performance logging
    performance_example(100)

    # Demonstrate data operation logging
    try:
        process_data("AAPL", "1d")
    except ValueError as e:
        log_error(e, logger=logger)

    # Demonstrate debug mode toggling
    logger.info("Turning on debug mode")
    set_debug_mode(True)

    # This debug message will now be visible
    logger.debug("This debug message should be visible now")

    # Try another data operation in debug mode
    try:
        process_data("MSFT", "1h")
    except ValueError as e:
        log_error(e, logger=logger, include_traceback=True)

    # Turn off debug mode
    logger.info("Turning off debug mode")
    set_debug_mode(False)

    # This debug message will not be visible in console (but will be in the log file)
    logger.debug("This debug message should not be visible in console")

    logger.info("Logging demonstration completed")


if __name__ == "__main__":
    main()

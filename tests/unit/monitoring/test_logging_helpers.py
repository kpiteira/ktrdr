"""Tests for structured logging helper functions."""

import logging
from unittest.mock import MagicMock

from ktrdr.monitoring.logging_helpers import (
    log_operation_complete,
    log_operation_error,
    log_operation_start,
)


def test_log_operation_start():
    """Test log_operation_start creates structured log."""
    logger = MagicMock(spec=logging.Logger)

    log_operation_start(
        logger,
        operation_id="op_test_123",
        operation_type="data_load",
        symbol="AAPL",
        timeframe="1d",
    )

    # Verify logger.info was called
    logger.info.assert_called_once()

    # Get the call arguments
    args, kwargs = logger.info.call_args

    # Verify message
    assert args[0] == "Operation started"

    # Verify extra dict has structured fields
    extra = kwargs["extra"]
    assert extra["operation_id"] == "op_test_123"
    assert extra["operation_type"] == "data_load"
    assert extra["status"] == "started"
    assert extra["symbol"] == "AAPL"
    assert extra["timeframe"] == "1d"


def test_log_operation_complete():
    """Test log_operation_complete creates structured log."""
    logger = MagicMock(spec=logging.Logger)

    log_operation_complete(
        logger, operation_id="op_test_456", duration_ms=1234.5, bars_count=100
    )

    # Verify logger.info was called
    logger.info.assert_called_once()

    # Get the call arguments
    args, kwargs = logger.info.call_args

    # Verify message
    assert args[0] == "Operation completed"

    # Verify extra dict has structured fields
    extra = kwargs["extra"]
    assert extra["operation_id"] == "op_test_456"
    assert extra["status"] == "completed"
    assert extra["duration_ms"] == 1234.5
    assert extra["bars_count"] == 100


def test_log_operation_error():
    """Test log_operation_error creates structured log."""
    logger = MagicMock(spec=logging.Logger)

    error = ValueError("Test error message")

    log_operation_error(logger, operation_id="op_test_789", error=error, symbol="AAPL")

    # Verify logger.error was called
    logger.error.assert_called_once()

    # Get the call arguments
    args, kwargs = logger.error.call_args

    # Verify message
    assert args[0] == "Operation failed"

    # Verify extra dict has structured fields
    extra = kwargs["extra"]
    assert extra["operation_id"] == "op_test_789"
    assert extra["status"] == "failed"
    assert extra["error_type"] == "ValueError"
    assert extra["error_message"] == "Test error message"
    assert extra["symbol"] == "AAPL"

    # Verify exc_info=True for stack trace
    assert kwargs["exc_info"] is True


def test_log_operation_start_minimal():
    """Test log_operation_start with minimal arguments."""
    logger = MagicMock(spec=logging.Logger)

    log_operation_start(logger, operation_id="op_minimal", operation_type="backtesting")

    logger.info.assert_called_once()

    args, kwargs = logger.info.call_args
    extra = kwargs["extra"]

    # Only required fields should be present
    assert extra["operation_id"] == "op_minimal"
    assert extra["operation_type"] == "backtesting"
    assert extra["status"] == "started"


def test_log_operation_complete_with_context():
    """Test log_operation_complete with additional context."""
    logger = MagicMock(spec=logging.Logger)

    log_operation_complete(
        logger,
        operation_id="op_ctx",
        duration_ms=500.0,
        symbol="EURUSD",
        timeframe="1h",
        result_size=1000,
    )

    logger.info.assert_called_once()

    args, kwargs = logger.info.call_args
    extra = kwargs["extra"]

    # Verify all context is preserved
    assert extra["symbol"] == "EURUSD"
    assert extra["timeframe"] == "1h"
    assert extra["result_size"] == 1000


def test_logging_preserves_trace_context():
    """
    Test that logging helpers work with OTEL trace context.

    Note: This tests the structure, not actual OTEL integration
    (OTEL integration tested separately in test_setup.py)
    """
    logger = MagicMock(spec=logging.Logger)

    # Log with structured fields
    log_operation_start(
        logger, operation_id="op_trace", operation_type="training", strategy="momentum"
    )

    # Verify the extra dict structure is compatible with OTEL
    # OTEL will automatically add otelTraceID and otelSpanID
    logger.info.assert_called_once()
    args, kwargs = logger.info.call_args

    # Verify we're using the extra parameter correctly
    assert "extra" in kwargs
    assert isinstance(kwargs["extra"], dict)

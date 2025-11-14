"""Logging helper functions for structured logging."""

import logging
from typing import Any


def log_operation_start(
    logger: logging.Logger,
    operation_id: str,
    operation_type: str,
    **context: Any,
) -> None:
    """
    Log operation start with standard fields.

    Args:
        logger: Logger instance to use
        operation_id: Unique operation identifier
        operation_type: Type of operation (e.g., "data_load", "training")
        **context: Additional context fields to include
    """
    logger.info(
        "Operation started",
        extra={
            "operation_id": operation_id,
            "operation_type": operation_type,
            "status": "started",
            **context,
        },
    )


def log_operation_complete(
    logger: logging.Logger, operation_id: str, duration_ms: float, **context: Any
) -> None:
    """
    Log operation completion with standard fields.

    Args:
        logger: Logger instance to use
        operation_id: Unique operation identifier
        duration_ms: Operation duration in milliseconds
        **context: Additional context fields to include
    """
    logger.info(
        "Operation completed",
        extra={
            "operation_id": operation_id,
            "status": "completed",
            "duration_ms": duration_ms,
            **context,
        },
    )


def log_operation_error(
    logger: logging.Logger, operation_id: str, error: Exception, **context: Any
) -> None:
    """
    Log operation error with standard fields.

    Args:
        logger: Logger instance to use
        operation_id: Unique operation identifier
        error: Exception that occurred
        **context: Additional context fields to include
    """
    logger.error(
        "Operation failed",
        extra={
            "operation_id": operation_id,
            "status": "failed",
            "error_type": type(error).__name__,
            "error_message": str(error),
            **context,
        },
        exc_info=True,
    )

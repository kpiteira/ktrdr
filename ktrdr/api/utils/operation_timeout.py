"""
Global operation timeout wrapper for IB operations.

Provides a global safety net to prevent operations from hanging indefinitely,
even if individual timeouts fail.
"""

import asyncio
import functools
import time
from typing import Any, Callable, TypeVar, Union

from ktrdr import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def with_global_timeout(
    timeout_seconds: float = 30.0, operation_name: str = "IB Operation"
):
    """
    Decorator to add global timeout protection to any async function.

    This is a safety net to prevent operations from hanging indefinitely
    even if their internal timeouts fail.

    Args:
        timeout_seconds: Maximum time to allow operation
        operation_name: Human-readable name for logging
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"{operation_name}_{id(func)}_{start_time}"

            logger.debug(
                f"🕐 Starting {operation_name} with {timeout_seconds}s global timeout"
            )

            try:
                # Execute with global timeout
                result = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=timeout_seconds
                )

                duration = time.time() - start_time
                logger.debug(f"✅ {operation_name} completed in {duration:.2f}s")
                return result

            except asyncio.TimeoutError:
                duration = time.time() - start_time
                logger.error(
                    f"🚨 GLOBAL TIMEOUT: {operation_name} exceeded {timeout_seconds}s limit "
                    f"(actual: {duration:.2f}s). This indicates a hung operation!"
                )

                # Re-raise with more context
                raise asyncio.TimeoutError(
                    f"Global timeout: {operation_name} hung for {duration:.2f}s "
                    f"(limit: {timeout_seconds}s). Possible silent IB connection."
                )

            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"❌ {operation_name} failed after {duration:.2f}s: {e}")
                raise

        return wrapper

    return decorator


async def safe_ib_operation(
    operation: Callable,
    timeout_seconds: float = 30.0,
    operation_name: str = "IB Operation",
    *args,
    **kwargs,
) -> Any:
    """
    Execute an IB operation with global timeout protection.

    This is a function-based alternative to the decorator.

    Args:
        operation: The async function to execute
        timeout_seconds: Maximum time to allow
        operation_name: Human-readable name for logging
        *args, **kwargs: Arguments to pass to operation

    Returns:
        Result of the operation

    Raises:
        asyncio.TimeoutError: If operation hangs beyond timeout
        Exception: Any exception from the operation
    """
    start_time = time.time()

    logger.debug(f"🕐 Executing {operation_name} with {timeout_seconds}s protection")

    try:
        result = await asyncio.wait_for(
            operation(*args, **kwargs), timeout=timeout_seconds
        )

        duration = time.time() - start_time
        logger.debug(f"✅ {operation_name} completed safely in {duration:.2f}s")
        return result

    except asyncio.TimeoutError:
        duration = time.time() - start_time
        logger.error(
            f"🚨 GLOBAL TIMEOUT: {operation_name} hung for {duration:.2f}s "
            f"(limit: {timeout_seconds}s). Forcing termination!"
        )

        raise asyncio.TimeoutError(
            f"Operation '{operation_name}' timed out after {duration:.2f}s. "
            f"This indicates an IB connection or event loop issue."
        )


class OperationTimeoutError(Exception):
    """Raised when an operation times out globally."""

    def __init__(
        self, operation_name: str, timeout_seconds: float, actual_duration: float
    ):
        self.operation_name = operation_name
        self.timeout_seconds = timeout_seconds
        self.actual_duration = actual_duration

        super().__init__(
            f"Operation '{operation_name}' timed out after {actual_duration:.2f}s "
            f"(limit: {timeout_seconds}s)"
        )


def emergency_operation_killer(max_duration: float = 60.0):
    """
    Emergency timeout that kills operations that exceed maximum duration.

    This is the absolute last resort to prevent indefinite hangs.
    """

    async def killer(operation_coro, operation_name: str = "Unknown"):
        start_time = time.time()

        try:
            return await asyncio.wait_for(operation_coro, timeout=max_duration)
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            logger.critical(
                f"🆘 EMERGENCY TIMEOUT: {operation_name} exceeded {max_duration}s! "
                f"Actual duration: {duration:.2f}s. System may be in deadlock!"
            )

            raise OperationTimeoutError(operation_name, max_duration, duration)

    return killer

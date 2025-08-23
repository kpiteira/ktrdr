"""
Retry mechanism with exponential backoff for KTRDR.

This module provides a retry decorator with exponential backoff
for handling transient errors in network operations.
"""

import functools
import random
import time
from typing import Any, Callable, List, Optional, Type, TypeVar, Union

# Import the new logging system
from ktrdr import get_logger
from ktrdr.errors.exceptions import MaxRetriesExceededError, RetryableError

# Type variable for functions that can be decorated with retry
T = TypeVar("T")

# Get module logger
logger = get_logger(__name__)


class RetryConfig:
    """
    Configuration for retry behavior.

    This class holds parameters that control the retry mechanism's behavior,
    including max retries, base delay, max delay, and jitter.

    Attributes:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Multiplicative factor for backoff calculation
        jitter: Whether to add randomness to the delay
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ) -> None:
        """
        Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay between retries in seconds (default: 1.0)
            max_delay: Maximum delay between retries in seconds (default: 60.0)
            backoff_factor: Multiplicative factor for backoff calculation (default: 2.0)
            jitter: Whether to add randomness to the delay (default: True)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter


def calculate_delay(retry_number: int, config: RetryConfig) -> float:
    """
    Calculate the delay for a specific retry attempt.

    Args:
        retry_number: The current retry attempt (0-based)
        config: Retry configuration parameters

    Returns:
        Delay time in seconds
    """
    # Calculate exponential backoff
    delay = min(
        config.max_delay, config.base_delay * (config.backoff_factor**retry_number)
    )

    # Add jitter if configured
    if config.jitter:
        delay = delay * (0.5 + random.random())

    return delay


def retry_with_backoff(
    retryable_exceptions: Optional[
        Union[type[Exception], list[type[Exception]]]
    ] = None,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
    is_retryable: Optional[Callable[[Exception], bool]] = None,
    logger=None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        retryable_exceptions: Exception type(s) that should trigger a retry
        config: Retry configuration parameters
        on_retry: Optional callback function called before each retry
        is_retryable: Optional function to determine if an exception is retryable
        logger: Optional logger to log retry attempts

    Returns:
        Decorator function that adds retry behavior to the decorated function

    Example:
        @retry_with_backoff(retryable_exceptions=[ConnectionError])
        def fetch_data():
            # Function that might encounter network issues
            pass
    """
    # Default to RetryableError if no exceptions specified
    if retryable_exceptions is None:
        retryable_exceptions = RetryableError

    # Use default config if none provided
    if config is None:
        config = RetryConfig()

    # Get logger reference
    log = logger or get_logger(__name__)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            # Try the function up to max_retries + 1 times (initial attempt + retries)
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if this exception is retryable
                    should_retry = False

                    if is_retryable is not None:
                        # Use custom retryable function if provided
                        should_retry = is_retryable(e)
                    elif isinstance(retryable_exceptions, (list, tuple)):
                        # Check if exception is one of the retryable types
                        should_retry = any(
                            isinstance(e, ex_type) for ex_type in retryable_exceptions
                        )
                    else:
                        # Check if exception is of the retryable type
                        should_retry = isinstance(e, retryable_exceptions)

                    # If not retryable or this was the last attempt, raise the exception
                    if not should_retry or attempt >= config.max_retries:
                        if attempt >= config.max_retries:
                            raise MaxRetriesExceededError(
                                f"Maximum retries ({config.max_retries}) exceeded for {func.__name__}",
                                details={
                                    "function": func.__name__,
                                    "max_retries": config.max_retries,
                                    "original_error": str(last_exception),
                                    "original_error_type": type(
                                        last_exception
                                    ).__name__,
                                },
                            ) from last_exception
                        else:
                            raise

                    # Calculate delay for this retry attempt
                    delay = calculate_delay(attempt, config)

                    # Log the retry using the new logging system
                    log.warning(
                        f"Retrying {func.__name__} due to {type(e).__name__}: {str(e)}. "
                        f"Attempt {attempt+1}/{config.max_retries} after {delay:.2f}s delay."
                    )

                    # Call on_retry callback if provided
                    if on_retry is not None:
                        on_retry(e, attempt, delay)

                    # Wait before retrying
                    time.sleep(delay)

            # This should never be reached due to the exception handling above
            raise RuntimeError("Unexpected state in retry decorator")

        return wrapper

    return decorator

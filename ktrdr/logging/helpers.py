"""
Helper methods for common logging patterns.

This module provides decorators and utility functions for common logging
patterns such as entry/exit logging, performance tracking, data operations,
and error logging.
"""

import functools
import inspect
import logging
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, cast

from ktrdr.logging.config import get_logger

# Type variables for function decorators
F = TypeVar("F", bound=Callable[..., Any])


def log_entry_exit(
    logger: Optional[logging.Logger] = None,
    log_args: bool = False,
    log_result: bool = False,
    entry_level: int = logging.DEBUG,
    exit_level: int = logging.DEBUG,
    error_level: int = logging.ERROR,
) -> Callable[[F], F]:
    """
    Decorator to log function entry and exit.

    Args:
        logger: Logger to use (if None, get logger based on module name)
        log_args: Whether to log function arguments
        log_result: Whether to log function return value
        entry_level: Log level for entry messages
        exit_level: Log level for exit messages
        error_level: Log level for error messages

    Returns:
        Decorated function with entry/exit logging
    """

    def decorator(func: F) -> F:
        # Get the module name from the function
        module_name = func.__module__

        # Use provided logger or get one based on module name
        log = logger or get_logger(module_name)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = func.__qualname__

            # Log function entry
            entry_msg = f"Entering {func_name}"
            if log_args and (args or kwargs):
                # Format arguments for logging
                arg_strs: List[str] = []

                # Add positional arguments
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())

                for i, arg in enumerate(args):
                    if i < len(param_names):
                        name = param_names[i]
                        arg_value = (
                            repr(arg)
                            if not isinstance(arg, (int, float, str, bool))
                            else arg
                        )
                        arg_strs.append(f"{name}={arg_value}")
                    else:
                        arg_value = (
                            repr(arg)
                            if not isinstance(arg, (int, float, str, bool))
                            else arg
                        )
                        arg_strs.append(f"{arg_value}")

                # Add keyword arguments
                for name, value in kwargs.items():
                    arg_value = (
                        repr(value)
                        if not isinstance(value, (int, float, str, bool))
                        else value
                    )
                    arg_strs.append(f"{name}={arg_value}")

                entry_msg += f" with args: {', '.join(arg_strs)}"

            log.log(entry_level, entry_msg)

            start_time = time.time()
            try:
                # Call the function
                result = func(*args, **kwargs)

                # Calculate elapsed time
                elapsed = time.time() - start_time

                # Log function exit
                exit_msg = f"Exiting {func_name} after {elapsed:.3f}s"
                if log_result:
                    result_str = (
                        repr(result)
                        if not isinstance(result, (int, float, str, bool))
                        else result
                    )
                    # Truncate very long result strings
                    if isinstance(result_str, str) and len(result_str) > 1000:
                        result_str = result_str[:997] + "..."
                    exit_msg += f" with result: {result_str}"

                log.log(exit_level, exit_msg)
                return result
            except Exception as e:
                # Calculate elapsed time
                elapsed = time.time() - start_time

                # Log the error
                log.log(error_level, f"Error in {func_name} after {elapsed:.3f}s: {e}")

                # Re-raise the exception
                raise

        return cast(F, wrapper)

    return decorator


def log_performance(
    logger: Optional[logging.Logger] = None,
    threshold_ms: float = 0,  # 0 means log all calls
    log_level: int = logging.DEBUG,
) -> Callable[[F], F]:
    """
    Decorator to log function performance.

    Args:
        logger: Logger to use (if None, get logger based on module name)
        threshold_ms: Only log if execution time exceeds threshold (milliseconds)
        log_level: Log level for performance messages

    Returns:
        Decorated function with performance logging
    """

    def decorator(func: F) -> F:
        # Get the module name from the function
        module_name = func.__module__

        # Use provided logger or get one based on module name
        log = logger or get_logger(module_name)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000

            # Log if execution time exceeds threshold
            if elapsed_ms >= threshold_ms:
                func_name = func.__qualname__
                log.log(log_level, f"Performance: {func_name} took {elapsed_ms:.2f}ms")

            return result

        return cast(F, wrapper)

    return decorator


def log_data_operation(
    operation: str,
    data_type: str,
    logger: Optional[logging.Logger] = None,
    log_level: int = logging.INFO,
) -> Callable[[F], F]:
    """
    Decorator to log data operations with consistent formatting.

    Args:
        operation: Operation being performed (e.g., 'load', 'save', 'process')
        data_type: Type of data being operated on (e.g., 'price data', 'indicators')
        logger: Logger to use (if None, get logger based on module name)
        log_level: Log level for data operation messages

    Returns:
        Decorated function with data operation logging
    """

    def decorator(func: F) -> F:
        # Get the module name from the function
        module_name = func.__module__

        # Use provided logger or get one based on module name
        log = logger or get_logger(module_name)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Log start of operation
            log.log(log_level, f"Started {operation} of {data_type}")

            start_time = time.time()
            try:
                # Call the function
                result = func(*args, **kwargs)

                # Calculate operation metrics
                elapsed = time.time() - start_time

                # Attempt to get size/count information from the result
                items_count = None
                if hasattr(result, "__len__"):
                    items_count = len(result)

                # Log successful completion
                completion_msg = (
                    f"Completed {operation} of {data_type} in {elapsed:.3f}s"
                )
                if items_count is not None:
                    completion_msg += f" ({items_count} items)"

                log.log(log_level, completion_msg)
                return result
            except Exception as e:
                # Log operation failure
                elapsed = time.time() - start_time
                log.error(
                    f"Failed {operation} of {data_type} after {elapsed:.3f}s: {e}"
                )

                # Re-raise the exception
                raise

        return cast(F, wrapper)

    return decorator


def log_error(
    exception: Union[Exception, str],
    logger: Optional[logging.Logger] = None,
    level: int = logging.ERROR,
    include_traceback: bool = True,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log an exception or error message with consistent formatting.

    Args:
        exception: Exception object or error message string
        logger: Logger to use (defaults to logger for calling module)
        level: Log level to use
        include_traceback: Whether to include traceback information
        extra: Extra contextual information to include
    """
    # Determine the calling frame to get module information
    frame = inspect.currentframe()
    if frame and frame.f_back:
        module = inspect.getmodule(frame.f_back)
        module_name = module.__name__ if module else "__main__"
    else:
        module_name = "__main__"

    # Use provided logger or get one based on module name
    log = logger or get_logger(module_name)

    # Prepare error message
    if isinstance(exception, Exception):
        error_msg = f"{exception.__class__.__name__}: {str(exception)}"
    else:
        error_msg = str(exception)

    # Add traceback if requested and available
    if include_traceback and isinstance(exception, Exception):
        tb_str = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )
        error_msg += f"\n{tb_str}"

    # Log the error
    log.log(level, error_msg, extra=extra)

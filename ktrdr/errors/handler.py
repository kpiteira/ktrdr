"""
Centralized error handler for KTRDR.

This module provides a centralized error handler with error classification
and utilities for generating user-friendly error messages.
"""

import traceback
from typing import Dict, Any, Optional, Type, List, Callable, Union, TypeVar

# Import the new logging system
from ktrdr import get_logger, log_error as log_exception

from ktrdr.errors.exceptions import (
    KtrdrError,
    DataError,
    ConnectionError,
    ConfigurationError,
    ProcessingError,
    SystemError,
    SecurityError,
)

# Type variable for error handler functions
T = TypeVar("T")

# Get module logger
logger = get_logger(__name__)


class ErrorHandler:
    """
    Centralized error handler for KTRDR.

    This class provides methods for classifying errors, generating user-friendly
    messages, and handling errors according to their type.
    """

    # Error classification dictionary
    ERROR_CLASSES = {
        "data": DataError,
        "connection": ConnectionError,
        "configuration": ConfigurationError,
        "processing": ProcessingError,
        "system": SystemError,
        "security": SecurityError,
    }

    # User-friendly error message templates
    ERROR_MESSAGES = {
        DataError: "Data error: {message}",
        ConnectionError: "Connection error: {message}",
        ConfigurationError: "Configuration error: {message}",
        ProcessingError: "Processing error: {message}",
        SystemError: "System error: {message}",
        SecurityError: "Security issue detected: {message}",
    }

    # Error code prefixes for each error class
    ERROR_CODE_PREFIXES = {
        DataError: "DATA",
        ConnectionError: "CONN",
        ConfigurationError: "CONF",
        ProcessingError: "PROC",
        SystemError: "SYS",
        SecurityError: "SEC",
    }

    # Recovery steps for each error class
    RECOVERY_STEPS = {
        DataError: [
            "Check if the data file exists and is accessible",
            "Verify the data format matches the expected format",
            "Try using a different data source",
        ],
        ConnectionError: [
            "Check your internet connection",
            "Verify the service is available",
            "Try again later or contact support",
        ],
        ConfigurationError: [
            "Check your configuration file for errors",
            "Verify all required configuration settings are present",
            "Reset to default configuration and try again",
        ],
        ProcessingError: [
            "Check the input data for issues",
            "Try with a smaller or simpler dataset",
            "Update to the latest version of the application",
        ],
        SystemError: [
            "Restart the application",
            "Check system resources (memory, disk space)",
            "Contact support for assistance",
        ],
        SecurityError: [
            "Verify input data follows expected patterns",
            "Check permissions on files and directories",
            "Ensure credentials are properly configured",
            "Contact administrator if this issue persists",
        ],
    }

    @classmethod
    def classify_error(cls, error: Exception) -> str:
        """
        Classify an error into one of the predefined categories.

        Args:
            error: The exception to classify

        Returns:
            Error category as a string
        """
        if isinstance(error, KtrdrError):
            for category, error_class in cls.ERROR_CLASSES.items():
                if isinstance(error, error_class):
                    return category

        # Default classification for unexpected errors
        return "system"

    @classmethod
    def handle_error(
        cls,
        error: Exception,
        should_log_error: bool = True,
        raise_error: bool = True,
        logger=None,
    ) -> Dict[str, Any]:
        """
        Handle an error according to its type.

        Args:
            error: The exception to handle
            should_log_error: Whether to log the error
            raise_error: Whether to re-raise the error after handling
            logger: Optional logger to use, defaults to module logger

        Returns:
            Dictionary with error details

        Raises:
            The original exception if raise_error is True
        """
        # Get error category
        category = cls.classify_error(error)

        # Create error details
        error_details = {
            "error": error,
            "category": category,
            "message": str(error),
            "traceback": traceback.format_exc(),
            "user_message": error_to_user_message(error),
            "error_code": get_error_code(error),
            "recovery_steps": get_recovery_steps(error),
        }

        # Log error if requested using the new logging system
        if should_log_error:
            log = logger or get_logger(__name__)
            log_exception(
                error,
                logger=log,
                extra={"category": category, "error_code": error_details["error_code"]},
            )

        # Re-raise if requested
        if raise_error:
            raise error

        return error_details

    @classmethod
    def with_error_handling(
        cls,
        func: Callable[..., T] = None,
        log_error: bool = True,
        raise_error: bool = True,
        logger=None,
        fallback_value: Optional[Any] = None,
    ) -> Union[
        Callable[..., Union[T, Any]],
        Callable[[Callable[..., T]], Callable[..., Union[T, Any]]],
    ]:
        """
        Decorator to add error handling to a function.

        Can be used as a decorator with or without arguments:

        @ErrorHandler.with_error_handling
        def my_function():
            ...

        @ErrorHandler.with_error_handling(log_error=True, raise_error=False)
        def my_function():
            ...

        Args:
            func: The function to decorate
            log_error: Whether to log errors
            raise_error: Whether to re-raise errors
            logger: Optional logger to use
            fallback_value: Value to return if an error occurs and raise_error is False

        Returns:
            Decorated function with error handling or a decorator
        """

        def decorator(
            func_to_decorate: Callable[..., T],
        ) -> Callable[..., Union[T, Any]]:
            def wrapper(*args: Any, **kwargs: Any) -> Union[T, Any]:
                try:
                    return func_to_decorate(*args, **kwargs)
                except Exception as e:
                    cls.handle_error(
                        e,
                        should_log_error=log_error,
                        raise_error=raise_error,
                        logger=logger,
                    )
                    return fallback_value

            return wrapper

        # Handle case where decorator is used without arguments
        if func is not None:
            return decorator(func)

        return decorator


def error_to_user_message(error: Exception) -> str:
    """
    Convert an error to a user-friendly message.

    Args:
        error: The exception to convert

    Returns:
        User-friendly error message
    """
    # Get the error class for message template lookup
    error_class = type(error)

    # Get message from KtrdrError if available
    if isinstance(error, KtrdrError) and hasattr(error, "message"):
        message = error.message
    else:
        message = str(error)

    # Find the closest matching error class for the template
    template = None
    for err_cls, tmpl in ErrorHandler.ERROR_MESSAGES.items():
        if isinstance(error, err_cls):
            template = tmpl
            break

    # If no matching template found, use a generic one
    if template is None:
        template = "An error occurred: {message}"

    # Format the template with the message
    return template.format(message=message)


def get_error_code(error: Exception) -> str:
    """
    Get a unique error code for an error.

    Args:
        error: The exception to get a code for

    Returns:
        Error code string
    """
    # Use the error_code attribute if available
    if isinstance(error, KtrdrError) and error.error_code is not None:
        return error.error_code

    # Otherwise, generate a code based on the error class
    error_class = type(error)
    prefix = None

    # Find the closest matching error class for the prefix
    for err_cls, err_prefix in ErrorHandler.ERROR_CODE_PREFIXES.items():
        if isinstance(error, err_cls):
            prefix = err_prefix
            break

    # If no matching prefix found, use a generic one
    if prefix is None:
        prefix = "ERR"

    # Use the specific error class name as part of the code
    specific_class = error_class.__name__

    return f"{prefix}-{specific_class}"


def get_recovery_steps(error: Exception) -> List[str]:
    """
    Get recovery steps for an error.

    Args:
        error: The exception to get recovery steps for

    Returns:
        List of recovery step strings
    """
    # Find the closest matching error class for recovery steps
    for err_cls, steps in ErrorHandler.RECOVERY_STEPS.items():
        if isinstance(error, err_cls):
            return steps

    # Return generic recovery steps if no match found
    return [
        "Try the operation again",
        "Check the application logs for more details",
        "Contact support if the problem persists",
    ]

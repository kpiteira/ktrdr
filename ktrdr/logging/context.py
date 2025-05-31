"""
Context enrichment for log entries.

This module provides functionality to enrich log messages with contextual
information such as module, function, class, and custom context values.
"""

import functools
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TypeVar, cast

# Type variables for function decorators
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class LogContext:
    """
    Container for contextual information to be added to log entries.

    Attributes:
        operation_id: Unique identifier for the current operation
        user: User associated with the operation
        module: Module where the log was generated
        function: Function where the log was generated
        extra: Additional contextual information
    """

    operation_id: Optional[str] = None
    user: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class ContextEnricher(logging.Filter):
    """
    Logging filter that enriches log records with contextual information.
    """

    def __init__(self) -> None:
        """Initialize the context enricher."""
        super().__init__()
        self.context_stack = []

    def push_context(self, context: LogContext) -> None:
        """
        Push a new context onto the stack.

        Args:
            context: The context to push
        """
        self.context_stack.append(context)

    def pop_context(self) -> Optional[LogContext]:
        """
        Pop the most recent context from the stack.

        Returns:
            The popped context, or None if the stack was empty
        """
        if not self.context_stack:
            return None
        return self.context_stack.pop()

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Enrich log records with context from the current stack.

        Args:
            record: The log record to enrich

        Returns:
            True to include the record in the log output, False to discard
        """
        # Always keep the log record

        # Add context data from the stack to the log record
        if self.context_stack:
            context = self.context_stack[-1]  # Get the most recent context

            # Add operation ID if available
            if context.operation_id:
                record.operation_id = context.operation_id

            # Add user if available
            if context.user:
                record.user = context.user

            # Add module and function if not already set
            if not hasattr(record, "module") and context.module:
                record.module = context.module

            if not hasattr(record, "function") and context.function:
                record.function = context.function

            # Add any extra context data
            for key, value in context.extra.items():
                setattr(record, key, value)

        return True


# Global context enricher instance
_context_enricher = ContextEnricher()

# Initialize the context enricher by adding it to the root logger
logging.getLogger().addFilter(_context_enricher)


def with_context(
    operation_name: Optional[str] = None,
    include_args: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """
    Decorator to add function context to log entries within the function scope.

    Args:
        operation_name: Name of the operation (defaults to function name)
        include_args: Whether to include function arguments in the context
        extra: Additional context data to include

    Returns:
        Decorated function with context enrichment
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get operation name (use function name if not provided)
            op_name = operation_name or func.__name__

            # Create context with module and function information
            module_name = func.__module__
            function_name = func.__qualname__

            context = LogContext(
                module=module_name, function=function_name, extra=extra or {}
            )

            # Add arguments to context if requested
            if include_args:
                # Convert args to a dictionary using parameter names
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                arg_dict = {
                    k: repr(v) if not isinstance(v, (int, float, str, bool)) else v
                    for k, v in bound_args.arguments.items()
                }
                context.extra["args"] = arg_dict

            # Add timestamp for performance tracking
            start_time = time.time()
            context.extra["start_time"] = start_time

            # Push context to the stack
            _context_enricher.push_context(context)

            try:
                # Execute the wrapped function
                return func(*args, **kwargs)
            finally:
                # Remove context from stack
                _context_enricher.pop_context()

        return cast(F, wrapper)

    return decorator

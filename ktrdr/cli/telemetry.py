"""OpenTelemetry instrumentation for CLI commands."""

import asyncio
import functools
import json
from typing import Any, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from ktrdr import get_logger

logger = get_logger(__name__)

# Get tracer for CLI instrumentation
tracer = trace.get_tracer(__name__)

# Type variable for generic decorator
F = TypeVar("F", bound=Callable[..., Any])


def trace_cli_command(command_name: str) -> Callable[[F], F]:
    """
    Decorator to add OpenTelemetry tracing to CLI commands.

    Creates a custom span for the CLI command execution with business attributes:
    - cli.command: Command name
    - cli.args: Command arguments (JSON serialized)
    - operation.id: Operation ID if returned in result

    Args:
        command_name: Name of the CLI command (e.g., "data_load", "train")

    Returns:
        Decorator function

    Example:
        @trace_cli_command("data_show")
        def show_data(symbol: str, timeframe: str):
            # Command implementation
            return result
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper for synchronous functions."""
            span_name = f"cli.{command_name}"

            with tracer.start_as_current_span(span_name) as span:
                # Add CLI-specific attributes
                span.set_attribute("cli.command", command_name)

                # Serialize args/kwargs to JSON (handle non-serializable gracefully)
                try:
                    args_dict = {"args": args, "kwargs": kwargs}
                    span.set_attribute("cli.args", json.dumps(args_dict, default=str))
                except (TypeError, ValueError) as e:
                    logger.debug(f"Could not serialize CLI args: {e}")
                    span.set_attribute("cli.args", str(args_dict))

                try:
                    # Execute command
                    result = func(*args, **kwargs)

                    # Extract operation_id if present in result
                    if isinstance(result, dict) and "operation_id" in result:
                        span.set_attribute("operation.id", result["operation_id"])

                    # Mark span as successful
                    span.set_status(Status(StatusCode.OK))

                    return result

                except Exception as e:
                    # Record exception in span
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper for asynchronous functions."""
            span_name = f"cli.{command_name}"

            with tracer.start_as_current_span(span_name) as span:
                # Add CLI-specific attributes
                span.set_attribute("cli.command", command_name)

                # Serialize args/kwargs to JSON
                try:
                    args_dict = {"args": args, "kwargs": kwargs}
                    span.set_attribute("cli.args", json.dumps(args_dict, default=str))
                except (TypeError, ValueError) as e:
                    logger.debug(f"Could not serialize CLI args: {e}")
                    span.set_attribute("cli.args", str(args_dict))

                try:
                    # Execute async command
                    result = await func(*args, **kwargs)

                    # Extract operation_id if present in result
                    if isinstance(result, dict) and "operation_id" in result:
                        span.set_attribute("operation.id", result["operation_id"])

                    # Mark span as successful
                    span.set_status(Status(StatusCode.OK))

                    return result

                except Exception as e:
                    # Record exception in span
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator

"""OpenTelemetry instrumentation for CLI commands.

PERFORMANCE NOTE: This module uses lazy imports to avoid loading OpenTelemetry
at module import time. OTEL is only imported when a traced function is called.
This keeps `ktrdr --help` fast (<100ms).
"""

import asyncio
import functools
import json
import os
from typing import Any, Callable, TypeVar

# Type variable for generic decorator
F = TypeVar("F", bound=Callable[..., Any])

# Skip tracing in test mode for faster test execution
_is_testing = os.environ.get("PYTEST_CURRENT_TEST") is not None


def trace_cli_command(command_name: str) -> Callable[[F], F]:
    """
    Decorator to add OpenTelemetry tracing to CLI commands.

    Creates a custom span for the CLI command execution with business attributes:
    - cli.command: Command name
    - cli.args: Command arguments (JSON serialized)
    - operation.id: Operation ID if returned in result

    PERFORMANCE NOTE: OpenTelemetry is imported lazily when the decorated
    function is first called, not at decoration time.

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
            # Skip tracing in test mode
            if _is_testing:
                return func(*args, **kwargs)

            # Initialize telemetry infrastructure (OTLP exporter, httpx instrumentation)
            # This is a no-op if already initialized
            from ktrdr.cli import init_telemetry_if_needed

            init_telemetry_if_needed()

            # Lazy import OpenTelemetry
            from opentelemetry import trace
            from opentelemetry.trace import Status, StatusCode

            # Get tracer dynamically to support test fixtures
            tracer = trace.get_tracer(__name__)
            span_name = f"cli.{command_name}"

            with tracer.start_as_current_span(span_name) as span:
                # Add CLI-specific attributes
                span.set_attribute("cli.command", command_name)

                # Serialize args/kwargs to JSON (handle non-serializable gracefully)
                try:
                    args_dict = {"args": args, "kwargs": kwargs}
                    span.set_attribute("cli.args", json.dumps(args_dict, default=str))
                except (TypeError, ValueError):
                    span.set_attribute(
                        "cli.args", str({"args": args, "kwargs": kwargs})
                    )

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
            # Skip tracing in test mode
            if _is_testing:
                return await func(*args, **kwargs)

            # Initialize telemetry infrastructure (OTLP exporter, httpx instrumentation)
            # This is a no-op if already initialized
            from ktrdr.cli import init_telemetry_if_needed

            init_telemetry_if_needed()

            # Lazy import OpenTelemetry
            from opentelemetry import trace
            from opentelemetry.trace import Status, StatusCode

            # Get tracer dynamically to support test fixtures
            tracer = trace.get_tracer(__name__)
            span_name = f"cli.{command_name}"

            with tracer.start_as_current_span(span_name) as span:
                # Add CLI-specific attributes
                span.set_attribute("cli.command", command_name)

                # Serialize args/kwargs to JSON
                try:
                    args_dict = {"args": args, "kwargs": kwargs}
                    span.set_attribute("cli.args", json.dumps(args_dict, default=str))
                except (TypeError, ValueError):
                    span.set_attribute(
                        "cli.args", str({"args": args, "kwargs": kwargs})
                    )

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

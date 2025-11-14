"""OpenTelemetry instrumentation for MCP tools."""

import asyncio
import functools
import json
from typing import Any, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Type variable for generic decorator
F = TypeVar("F", bound=Callable[..., Any])


def trace_mcp_tool(tool_name: str) -> Callable[[F], F]:
    """
    Decorator to add OpenTelemetry tracing to MCP tools.

    Creates a custom span for the MCP tool execution with business attributes:
    - mcp.tool: Tool name
    - mcp.params: Tool parameters (JSON serialized)
    - operation.id: Operation ID if returned in result

    Args:
        tool_name: Name of the MCP tool (e.g., "check_backend_health", "start_training")

    Returns:
        Decorator function

    Example:
        @trace_mcp_tool("check_backend_health")
        async def check_backend_health():
            # Tool implementation
            return result
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper for synchronous functions."""
            # Get tracer dynamically to support test fixtures
            tracer = trace.get_tracer(__name__)
            span_name = f"mcp.tool.{tool_name}"

            with tracer.start_as_current_span(span_name) as span:
                # Add MCP-specific attributes
                span.set_attribute("mcp.tool", tool_name)

                # Serialize params to JSON (handle non-serializable gracefully)
                try:
                    params_dict = {"args": args, "kwargs": kwargs}
                    span.set_attribute("mcp.params", json.dumps(params_dict, default=str))
                except (TypeError, ValueError):
                    # Fallback to string representation
                    span.set_attribute("mcp.params", str(params_dict))

                try:
                    # Execute tool
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
            # Get tracer dynamically to support test fixtures
            tracer = trace.get_tracer(__name__)
            span_name = f"mcp.tool.{tool_name}"

            with tracer.start_as_current_span(span_name) as span:
                # Add MCP-specific attributes
                span.set_attribute("mcp.tool", tool_name)

                # Serialize params to JSON
                try:
                    params_dict = {"args": args, "kwargs": kwargs}
                    span.set_attribute("mcp.params", json.dumps(params_dict, default=str))
                except (TypeError, ValueError):
                    # Fallback to string representation
                    span.set_attribute("mcp.params", str(params_dict))

                try:
                    # Execute async tool
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

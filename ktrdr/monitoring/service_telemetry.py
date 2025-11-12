"""OpenTelemetry instrumentation for API service methods."""

import asyncio
import functools
from contextlib import contextmanager
from typing import Any, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from ktrdr import get_logger

logger = get_logger(__name__)

# Type variable for generic decorator
F = TypeVar("F", bound=Callable[..., Any])

# Mapping of parameter names to OTEL attribute names
ATTRIBUTE_MAPPING = {
    "symbol": "data.symbol",
    "timeframe": "data.timeframe",
    "strategy": "training.strategy",
    "model_id": "model.id",
    "operation_id": "operation.id",
    "start_date": "data.start_date",
    "end_date": "data.end_date",
    "epochs": "training.epochs",
    "batch_size": "training.batch_size",
}


def trace_service_method(span_name: str) -> Callable[[F], F]:
    """
    Decorator to add OpenTelemetry tracing to service methods.

    Creates a custom span for the service method execution with business attributes.
    Automatically maps common parameter names to appropriate OTEL attributes.

    Args:
        span_name: Name of the span (e.g., "data.load", "indicator.calculate")

    Returns:
        Decorator function

    Example:
        @trace_service_method("data.load")
        async def load_data(self, symbol: str, timeframe: str):
            # Method implementation
            return result
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper for synchronous methods."""
            try:
                # Get tracer dynamically to support test fixtures
                tracer = trace.get_tracer(__name__)
            except Exception as e:
                logger.debug(f"Could not get tracer: {e}")
                # Fall back to executing without tracing
                return func(*args, **kwargs)

            with tracer.start_as_current_span(span_name) as span:
                # Add service method attribute
                span.set_attribute("service.method", span_name)

                # Map kwargs to OTEL attributes
                for param_name, param_value in kwargs.items():
                    if param_name in ATTRIBUTE_MAPPING:
                        attr_name = ATTRIBUTE_MAPPING[param_name]
                        span.set_attribute(attr_name, str(param_value))

                try:
                    # Execute method
                    result = func(*args, **kwargs)

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
            """Wrapper for asynchronous methods."""
            try:
                # Get tracer dynamically to support test fixtures
                tracer = trace.get_tracer(__name__)
            except Exception as e:
                logger.debug(f"Could not get tracer: {e}")
                # Fall back to executing without tracing
                return await func(*args, **kwargs)

            with tracer.start_as_current_span(span_name) as span:
                # Add service method attribute
                span.set_attribute("service.method", span_name)

                # Map kwargs to OTEL attributes
                for param_name, param_value in kwargs.items():
                    if param_name in ATTRIBUTE_MAPPING:
                        attr_name = ATTRIBUTE_MAPPING[param_name]
                        span.set_attribute(attr_name, str(param_value))

                try:
                    # Execute async method
                    result = await func(*args, **kwargs)

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


@contextmanager
def create_service_span(span_name: str, **attributes: Any):
    """
    Context manager to create a service span with business attributes.

    This is useful for creating phase-specific spans within service methods.

    Args:
        span_name: Name of the span (e.g., "data.fetch", "data.parse")
        **attributes: Business attributes to attach to the span

    Example:
        with create_service_span("data.fetch", symbol="AAPL", timeframe="1d"):
            data = fetch_data_from_source()

        with create_service_span("data.parse"):
            parsed_data = parse_raw_data(data)
    """
    try:
        # Get tracer dynamically
        tracer = trace.get_tracer(__name__)
    except Exception as e:
        logger.debug(f"Could not get tracer: {e}")
        # If no tracer, just execute without tracing
        yield
        return

    with tracer.start_as_current_span(span_name) as span:
        # Map attributes to OTEL attribute names
        for attr_name, attr_value in attributes.items():
            if attr_name in ATTRIBUTE_MAPPING:
                otel_attr_name = ATTRIBUTE_MAPPING[attr_name]
                span.set_attribute(otel_attr_name, str(attr_value))
            else:
                # For unmapped attributes, use as-is
                span.set_attribute(attr_name, str(attr_value))

        try:
            yield span
            # Mark span as successful
            span.set_status(Status(StatusCode.OK))

        except Exception as e:
            # Record exception
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise

"""Tests for OpenTelemetry instrumentation of API services."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode


@pytest.fixture(autouse=True)
def reset_tracer():
    """Reset tracer provider before each test."""
    # Store original provider
    original_provider = trace.get_tracer_provider()

    yield

    # Restore original provider
    trace._TRACER_PROVIDER = original_provider


@pytest.fixture
def tracer_setup(reset_tracer):
    """Setup in-memory span exporter for testing."""
    # Create in-memory exporter to capture spans
    exporter = InMemorySpanExporter()

    # Create tracer provider with simple processor
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Set as global tracer provider (bypassing warning)
    trace._TRACER_PROVIDER = None
    trace.set_tracer_provider(provider)

    yield exporter

    # Clear spans after test
    exporter.clear()


class TestTraceServiceMethod:
    """Tests for trace_service_method decorator."""

    def test_service_method_creates_span(self, tracer_provider):
        """Test that service method decorator creates a span."""
        from ktrdr.monitoring.service_telemetry import trace_service_method

        provider, exporter = tracer_provider

        @trace_service_method("data.load")
        def load_data(symbol: str, timeframe: str):
            return {"data": "test"}

        result = load_data("AAPL", "1d")

        # Verify result is correct
        assert result == {"data": "test"}

        # Verify span was created
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "data.load"
        assert span.status.status_code == StatusCode.OK

    def test_service_method_captures_business_attributes(self, tracer_provider):
        """Test that business attributes are captured in span."""
        from ktrdr.monitoring.service_telemetry import trace_service_method

        provider, exporter = tracer_provider

        @trace_service_method("data.load")
        def load_data(symbol: str, timeframe: str, operation_id: str = None):
            return {"data": "test"}

        load_data("AAPL", "1d", operation_id="op_123")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        attributes = span.attributes

        # Check business attributes were captured
        assert attributes.get("service.method") == "data.load"
        assert attributes.get("data.symbol") == "AAPL"
        assert attributes.get("data.timeframe") == "1d"
        assert attributes.get("operation.id") == "op_123"

    def test_service_method_async_support(self, tracer_provider):
        """Test that async service methods are supported."""
        import asyncio

        from ktrdr.monitoring.service_telemetry import trace_service_method

        provider, exporter = tracer_provider

        @trace_service_method("indicator.calculate")
        async def calculate_indicators(symbol: str):
            await asyncio.sleep(0.001)  # Simulate async work
            return {"result": "calculated"}

        result = asyncio.run(calculate_indicators("AAPL"))

        assert result == {"result": "calculated"}

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "indicator.calculate"

    def test_service_method_error_handling(self, tracer_provider):
        """Test that exceptions are properly recorded in spans."""
        from ktrdr.monitoring.service_telemetry import trace_service_method

        provider, exporter = tracer_provider

        @trace_service_method("data.load")
        def load_data(symbol: str):
            raise ValueError("Invalid symbol")

        with pytest.raises(ValueError, match="Invalid symbol"):
            load_data("INVALID")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR
        assert span.status.description == "Invalid symbol"

        # Check exception was recorded
        events = span.events
        assert len(events) == 1
        assert events[0].name == "exception"

    def test_service_method_preserves_metadata(self, tracer_provider):
        """Test that function metadata is preserved by decorator."""
        from ktrdr.monitoring.service_telemetry import trace_service_method

        @trace_service_method("test.method")
        def test_function(arg1: str, arg2: int = 5):
            """Test function docstring."""
            return arg1, arg2

        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test function docstring."

    def test_service_method_without_otel(self):
        """Test that decorator works even without OTEL setup."""
        from ktrdr.monitoring.service_telemetry import trace_service_method

        # Don't set up tracer provider

        @trace_service_method("test.method")
        def test_function():
            return "result"

        # Should not raise, just skip tracing
        result = test_function()
        assert result == "result"


class TestCreateServiceSpan:
    """Tests for create_service_span context manager."""

    def test_creates_span_with_attributes(self, tracer_provider):
        """Test creating a span with business attributes."""
        from ktrdr.monitoring.service_telemetry import create_service_span

        provider, exporter = tracer_provider

        with create_service_span(
            "data.fetch", symbol="AAPL", timeframe="1d", operation_id="op_123"
        ):
            pass  # Simulate work

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "data.fetch"
        assert span.attributes.get("data.symbol") == "AAPL"
        assert span.attributes.get("data.timeframe") == "1d"
        assert span.attributes.get("operation.id") == "op_123"

    def test_nested_spans(self, tracer_provider):
        """Test creating nested spans for phases."""
        from ktrdr.monitoring.service_telemetry import create_service_span

        provider, exporter = tracer_provider

        with create_service_span("data.download", symbol="AAPL"):
            with create_service_span("data.fetch"):
                pass
            with create_service_span("data.parse"):
                pass
            with create_service_span("data.validate"):
                pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 4

        # Verify parent-child relationships
        parent_span = [s for s in spans if s.name == "data.download"][0]
        child_spans = [
            s
            for s in spans
            if s.parent and s.parent.span_id == parent_span.context.span_id
        ]

        assert len(child_spans) == 3
        child_names = {s.name for s in child_spans}
        assert child_names == {"data.fetch", "data.parse", "data.validate"}

    def test_exception_handling(self, tracer_provider):
        """Test exception handling in context manager."""
        from ktrdr.monitoring.service_telemetry import create_service_span

        provider, exporter = tracer_provider

        with pytest.raises(RuntimeError, match="Test error"):
            with create_service_span("test.span"):
                raise RuntimeError("Test error")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR

        # Exception should be recorded
        events = span.events
        assert len(events) == 1
        assert events[0].name == "exception"


class TestAttributeMapping:
    """Tests for automatic attribute name mapping."""

    def test_maps_common_parameters(self, tracer_provider):
        """Test that common parameter names are mapped to OTEL attributes."""
        from ktrdr.monitoring.service_telemetry import create_service_span

        provider, exporter = tracer_provider

        with create_service_span(
            "service.method",
            symbol="AAPL",
            timeframe="1d",
            strategy="momentum",
            model_id="model_v1",
            operation_id="op_123",
        ):
            pass

        spans = exporter.get_finished_spans()
        span = spans[0]
        attrs = span.attributes

        # All parameters should be captured with appropriate prefixes
        assert attrs.get("data.symbol") == "AAPL"
        assert attrs.get("data.timeframe") == "1d"
        assert attrs.get("training.strategy") == "momentum"
        assert attrs.get("model.id") == "model_v1"
        assert attrs.get("operation.id") == "op_123"

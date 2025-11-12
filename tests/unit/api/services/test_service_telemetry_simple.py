"""Simplified tests for OpenTelemetry instrumentation of API services."""

import asyncio
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode


@pytest.fixture(autouse=True)
def reset_tracer():
    """Reset tracer provider before each test."""
    original_provider = trace.get_tracer_provider()
    yield
    trace._TRACER_PROVIDER = original_provider


@pytest.fixture
def tracer_setup(reset_tracer):
    """Setup in-memory span exporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace._TRACER_PROVIDER = None
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()


def test_trace_service_method_creates_span(tracer_setup):
    """Test that service method decorator creates a span."""
    from ktrdr.monitoring.service_telemetry import trace_service_method

    exporter = tracer_setup

    @trace_service_method("data.load")
    def load_data(symbol: str, timeframe: str):
        return {"data": "test"}

    result = load_data("AAPL", "1d")

    assert result == {"data": "test"}

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "data.load"
    assert spans[0].status.status_code == StatusCode.OK


def test_trace_service_method_captures_attributes(tracer_setup):
    """Test that business attributes are captured."""
    from ktrdr.monitoring.service_telemetry import trace_service_method

    exporter = tracer_setup

    @trace_service_method("data.load")
    def load_data(symbol="AAPL", timeframe="1d", operation_id="op_123"):
        return {"data": "test"}

    load_data()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    attrs = span.attributes
    assert attrs.get("service.method") == "data.load"
    assert attrs.get("data.symbol") == "AAPL"
    assert attrs.get("data.timeframe") == "1d"
    assert attrs.get("operation.id") == "op_123"


def test_trace_service_method_async(tracer_setup):
    """Test async method support."""
    from ktrdr.monitoring.service_telemetry import trace_service_method

    exporter = tracer_setup

    @trace_service_method("indicator.calculate")
    async def calculate(symbol="AAPL"):
        await asyncio.sleep(0.001)
        return {"result": "calculated"}

    result = asyncio.run(calculate())

    assert result == {"result": "calculated"}

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "indicator.calculate"


def test_trace_service_method_error_handling(tracer_setup):
    """Test exception handling."""
    from ktrdr.monitoring.service_telemetry import trace_service_method

    exporter = tracer_setup

    @trace_service_method("data.load")
    def load_data(symbol="INVALID"):
        raise ValueError("Invalid symbol")

    with pytest.raises(ValueError, match="Invalid symbol"):
        load_data()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    assert len(span.events) == 1
    assert span.events[0].name == "exception"


def test_create_service_span(tracer_setup):
    """Test context manager for creating spans."""
    from ktrdr.monitoring.service_telemetry import create_service_span

    exporter = tracer_setup

    with create_service_span("data.fetch", symbol="AAPL", timeframe="1d"):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    assert span.name == "data.fetch"
    assert span.attributes.get("data.symbol") == "AAPL"
    assert span.attributes.get("data.timeframe") == "1d"


def test_nested_spans(tracer_setup):
    """Test creating nested spans."""
    from ktrdr.monitoring.service_telemetry import create_service_span

    exporter = tracer_setup

    with create_service_span("data.download", symbol="AAPL"):
        with create_service_span("data.fetch"):
            pass
        with create_service_span("data.parse"):
            pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 3

    parent_span = [s for s in spans if s.name == "data.download"][0]
    child_spans = [s for s in spans if s.parent and s.parent.span_id == parent_span.context.span_id]

    assert len(child_spans) == 2
    child_names = {s.name for s in child_spans}
    assert child_names == {"data.fetch", "data.parse"}

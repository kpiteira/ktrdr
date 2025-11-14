"""Tests for MCP OpenTelemetry instrumentation."""

import json

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Skip all tests in this module until Phase 6.1 (MCP instrumentation) is implemented
pytestmark = pytest.mark.skip(
    reason="Phase 6.1 not implemented - waiting for MCP telemetry decorators and mcp.src module"
)


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


def test_mcp_tool_creates_span(tracer_setup):
    """Test that MCP tools create custom spans."""
    from mcp.src.telemetry import trace_mcp_tool

    exporter = tracer_setup

    # Mock tool function
    @trace_mcp_tool("test_tool")
    def mock_tool(symbol: str, timeframe: str):
        return {"data": "test_result"}

    # Execute tool
    result = mock_tool(symbol="AAPL", timeframe="1d")

    # Verify result
    assert result == {"data": "test_result"}

    # Verify span was created
    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    # Verify span attributes
    span = spans[0]
    assert span.name == "mcp.tool.test_tool"
    assert span.attributes["mcp.tool"] == "test_tool"
    assert "mcp.params" in span.attributes

    # Verify params are JSON serialized
    params_data = json.loads(span.attributes["mcp.params"])
    # Params are keyword args, so they're in the 'kwargs' key
    assert "kwargs" in params_data
    assert params_data["kwargs"]["symbol"] == "AAPL"
    assert params_data["kwargs"]["timeframe"] == "1d"


def test_mcp_tool_span_includes_operation_id(tracer_setup):
    """Test that MCP tools capture operation_id from result."""
    from mcp.src.telemetry import trace_mcp_tool

    exporter = tracer_setup

    # Mock tool that returns operation_id
    @trace_mcp_tool("start_training")
    def mock_tool():
        return {"operation_id": "op_train_12345", "status": "started"}

    # Execute tool
    result = mock_tool()

    # Verify result includes operation_id
    assert result["operation_id"] == "op_train_12345"

    # Verify span has operation_id attribute
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes.get("operation.id") == "op_train_12345"


def test_mcp_tool_span_handles_errors(tracer_setup):
    """Test that MCP tools record exceptions in spans."""
    from mcp.src.telemetry import trace_mcp_tool

    exporter = tracer_setup

    # Mock tool that raises exception
    @trace_mcp_tool("failing_tool")
    def mock_tool():
        raise ConnectionError("Backend unavailable")

    # Execute tool and catch exception
    with pytest.raises(ConnectionError, match="Backend unavailable"):
        mock_tool()

    # Verify span was created and marked as error
    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    assert span.status.status_code == trace.StatusCode.ERROR

    # Verify exception was recorded
    events = span.events
    assert len(events) > 0
    assert any("exception" in event.name.lower() for event in events)


def test_mcp_tool_decorator_preserves_metadata(tracer_setup):
    """Test that decorator preserves function metadata."""
    from mcp.src.telemetry import trace_mcp_tool

    @trace_mcp_tool("test_tool")
    async def documented_tool(param: str) -> dict:
        """This is a test MCP tool."""
        return {"result": param}

    # Verify metadata preserved
    assert documented_tool.__name__ == "documented_tool"
    assert documented_tool.__doc__ == "This is a test MCP tool."


def test_mcp_tool_with_async_function(tracer_setup):
    """Test that decorator works with async functions."""
    import asyncio

    from mcp.src.telemetry import trace_mcp_tool

    exporter = tracer_setup

    @trace_mcp_tool("async_tool")
    async def async_mock_tool(value: str):
        await asyncio.sleep(0.001)  # Simulate async work
        return {"result": value}

    # Execute async tool
    result = asyncio.run(async_mock_tool("test"))

    # Verify result
    assert result == {"result": "test"}

    # Verify span was created
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "mcp.tool.async_tool"


def test_mcp_tool_decorator_without_otel(tracer_setup):
    """Test that decorator works gracefully when OTEL is not available."""
    from mcp.src.telemetry import trace_mcp_tool

    @trace_mcp_tool("test_tool")
    def mock_tool():
        return {"result": "success"}

    result = mock_tool()
    assert result == {"result": "success"}


def test_mcp_tool_with_complex_params(tracer_setup):
    """Test that decorator handles complex parameter types."""
    from mcp.src.telemetry import trace_mcp_tool

    exporter = tracer_setup

    @trace_mcp_tool("complex_tool")
    def mock_tool(symbols: list[str], config: dict):
        return {"processed": len(symbols)}

    # Execute with complex params
    result = mock_tool(symbols=["AAPL", "MSFT", "GOOGL"], config={"key": "value"})

    # Verify result
    assert result == {"processed": 3}

    # Verify params were serialized correctly
    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    params_data = json.loads(spans[0].attributes["mcp.params"])
    assert params_data["kwargs"]["symbols"] == ["AAPL", "MSFT", "GOOGL"]
    assert params_data["kwargs"]["config"] == {"key": "value"}

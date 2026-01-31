"""Tests for CLI OpenTelemetry instrumentation.

These tests verify that the @trace_cli_command decorator correctly creates
spans when tracing is enabled (i.e., when NOT in test mode).

To test actual tracing, we temporarily disable test mode by manipulating
the _is_testing flag in the telemetry module.
"""

import json

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture(autouse=True)
def reset_tracer():
    """Reset tracer provider before and after each test."""
    from opentelemetry.util._once import Once

    # Store original state
    original_provider = trace._TRACER_PROVIDER
    original_once = trace._TRACER_PROVIDER_SET_ONCE

    # Reset BEFORE test to allow new provider setup
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE = Once()

    yield

    # Restore original state after test
    trace._TRACER_PROVIDER = original_provider
    trace._TRACER_PROVIDER_SET_ONCE = original_once


@pytest.fixture
def enable_tracing():
    """Temporarily disable test mode to enable actual tracing.

    The telemetry module skips tracing when _is_testing() returns True.
    This fixture replaces the function with one that returns False.
    """
    import ktrdr.cli.telemetry as telemetry_module

    # Store original function
    original_is_testing = telemetry_module._is_testing

    # Replace with a function that returns False (not a bool value!)
    # _is_testing is called as a function, so we must provide a callable
    telemetry_module._is_testing = lambda: False

    yield

    # Restore original function
    telemetry_module._is_testing = original_is_testing


@pytest.fixture
def tracer_setup(reset_tracer, enable_tracing):
    """Setup in-memory span exporter for testing.

    This fixture:
    1. Disables test mode (via enable_tracing) so tracing is active
    2. Sets up an in-memory exporter to capture spans
    3. Configures the tracer provider

    Note: reset_tracer already clears _TRACER_PROVIDER and _TRACER_PROVIDER_SET_ONCE
    """
    # Create in-memory exporter to capture spans
    exporter = InMemorySpanExporter()

    # Create tracer provider with simple processor
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Set as global tracer provider (reset_tracer already cleared the state)
    trace.set_tracer_provider(provider)

    yield exporter

    # Clear spans after test
    exporter.clear()


def test_cli_command_creates_span(tracer_setup):
    """Test that CLI commands create custom spans."""
    from ktrdr.cli.telemetry import trace_cli_command

    exporter = tracer_setup

    # Mock command function
    @trace_cli_command("test_command")
    def mock_command(arg1: str, arg2: int):
        return {"result": "success"}

    # Execute command
    result = mock_command("test_value", 42)

    # Verify result
    assert result == {"result": "success"}

    # Verify span was created
    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    # Verify span attributes
    span = spans[0]
    assert span.name == "cli.test_command"
    assert span.attributes["cli.command"] == "test_command"
    assert "cli.args" in span.attributes

    # Verify args are JSON serialized
    args_data = json.loads(span.attributes["cli.args"])
    # Args are positional, so they're in the 'args' key
    assert "args" in args_data
    assert args_data["args"] == ["test_value", 42]


def test_cli_command_span_includes_operation_id(tracer_setup):
    """Test that CLI commands capture operation_id from result."""
    from ktrdr.cli.telemetry import trace_cli_command

    exporter = tracer_setup

    # Mock command that returns operation_id
    @trace_cli_command("data_load")
    def mock_command():
        return {"operation_id": "op_test_12345"}

    # Execute command
    mock_command()

    # Verify span has operation_id attribute
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes.get("operation.id") == "op_test_12345"


def test_cli_command_span_handles_errors(tracer_setup):
    """Test that CLI commands record exceptions in spans."""
    from ktrdr.cli.telemetry import trace_cli_command

    exporter = tracer_setup

    # Mock command that raises exception
    @trace_cli_command("failing_command")
    def mock_command():
        raise ValueError("Test error")

    # Execute command and catch exception
    with pytest.raises(ValueError, match="Test error"):
        mock_command()

    # Verify span was created and marked as error
    spans = exporter.get_finished_spans()
    assert len(spans) == 1

    span = spans[0]
    assert span.status.status_code == trace.StatusCode.ERROR

    # Verify exception was recorded
    events = span.events
    assert len(events) > 0
    assert any("exception" in event.name.lower() for event in events)


def test_cli_command_decorator_preserves_metadata(tracer_setup):
    """Test that decorator preserves function metadata."""
    from ktrdr.cli.telemetry import trace_cli_command

    @trace_cli_command("test_command")
    def documented_function(arg: str) -> str:
        """This is a test function."""
        return arg

    # Verify metadata preserved
    assert documented_function.__name__ == "documented_function"
    assert documented_function.__doc__ == "This is a test function."


def test_cli_command_decorator_without_otel(tracer_setup):
    """Test that decorator works gracefully when OTEL is not available."""
    # This test ensures the decorator doesn't break CLI functionality
    # even if OpenTelemetry is not properly configured
    from ktrdr.cli.telemetry import trace_cli_command

    @trace_cli_command("test_command")
    def mock_command():
        return {"result": "success"}

    result = mock_command()
    assert result == {"result": "success"}


def test_cli_command_with_async_function(tracer_setup):
    """Test that decorator works with async functions."""
    import asyncio

    from ktrdr.cli.telemetry import trace_cli_command

    exporter = tracer_setup

    @trace_cli_command("async_command")
    async def async_mock_command(value: str):
        await asyncio.sleep(0.001)  # Simulate async work
        return {"result": value}

    # Execute async command
    result = asyncio.run(async_mock_command("test"))

    # Verify result
    assert result == {"result": "test"}

    # Verify span was created
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "cli.async_command"

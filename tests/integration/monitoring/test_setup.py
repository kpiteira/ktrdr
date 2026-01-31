"""Tests for OpenTelemetry setup."""

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.util._once import Once

import ktrdr.monitoring.setup as setup_module
from ktrdr.monitoring.setup import instrument_app, setup_monitoring


@pytest.fixture
def enable_monitoring():
    """Bypass _is_testing() check and reset tracer state.

    The setup_monitoring() function skips telemetry when _is_testing() returns True.
    This fixture replaces _is_testing with a lambda returning False and resets
    OpenTelemetry global state so we can test the actual instrumentation behavior.

    Note: We can't just clear PYTEST_CURRENT_TEST because pytest sets it again
    after the fixture runs but before the test body executes.
    """

    # Store and replace _is_testing function
    original_is_testing = setup_module._is_testing
    setup_module._is_testing = lambda: False

    # Store and reset tracer provider state to allow fresh setup
    original_provider = trace._TRACER_PROVIDER
    original_once = trace._TRACER_PROVIDER_SET_ONCE
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE = Once()

    yield

    # Restore tracer provider state
    trace._TRACER_PROVIDER = original_provider
    trace._TRACER_PROVIDER_SET_ONCE = original_once

    # Restore _is_testing function
    setup_module._is_testing = original_is_testing


def test_setup_monitoring_console_only(enable_monitoring):
    """Test setup with console output only."""
    provider = setup_monitoring(service_name="test-service", console_output=True)

    assert isinstance(provider, TracerProvider)
    # Note: The global tracer provider may have been set by importing the API module,
    # so we just verify it's a TracerProvider instance
    assert isinstance(trace.get_tracer_provider(), TracerProvider)


def test_setup_monitoring_with_otlp(enable_monitoring):
    """Test setup with OTLP endpoint."""
    with patch(
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
    ) as mock_exporter:
        provider = setup_monitoring(
            service_name="test-service", otlp_endpoint="http://jaeger:4317"
        )

        assert isinstance(provider, TracerProvider)
        mock_exporter.assert_called_once()


def test_instrument_app():
    """Test FastAPI app instrumentation."""
    mock_app = MagicMock()

    with (
        patch("ktrdr.monitoring.setup.FastAPIInstrumentor"),
        patch("ktrdr.monitoring.setup.HTTPXClientInstrumentor"),
        patch("ktrdr.monitoring.setup.LoggingInstrumentor"),
    ):
        instrument_app(mock_app)
        # Should not raise


def test_setup_monitoring_includes_service_name(enable_monitoring):
    """Test that service name is included in resource."""
    provider = setup_monitoring(service_name="my-test-service", console_output=True)

    resource = provider.resource
    assert resource.attributes.get("service.name") == "my-test-service"

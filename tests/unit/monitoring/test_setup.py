"""Tests for OpenTelemetry setup."""

from unittest.mock import MagicMock, patch

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from ktrdr.monitoring.setup import instrument_app, setup_monitoring


def test_setup_monitoring_console_only():
    """Test setup with console output only."""
    provider = setup_monitoring(service_name="test-service", console_output=True)

    assert isinstance(provider, TracerProvider)
    # Note: The global tracer provider may have been set by importing the API module,
    # so we just verify it's a TracerProvider instance
    assert isinstance(trace.get_tracer_provider(), TracerProvider)


def test_setup_monitoring_with_otlp():
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


def test_setup_monitoring_includes_service_name():
    """Test that service name is included in resource."""
    provider = setup_monitoring(service_name="my-test-service", console_output=True)

    resource = provider.resource
    assert resource.attributes.get("service.name") == "my-test-service"

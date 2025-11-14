"""Tests for Prometheus metrics setup."""

from unittest.mock import MagicMock, patch

from opentelemetry.sdk.metrics import MeterProvider

from ktrdr.monitoring.setup import setup_metrics


def test_setup_metrics_creates_meter_provider():
    """Test that setup_metrics creates and returns a MeterProvider."""
    provider = setup_metrics(service_name="test-service")

    assert isinstance(provider, MeterProvider)


def test_setup_metrics_includes_service_name():
    """Test that service name is included in resource."""
    provider = setup_metrics(service_name="test-metrics-service")

    resource = provider._sdk_config.resource
    assert resource.attributes.get("service.name") == "test-metrics-service"


@patch("ktrdr.monitoring.setup.PrometheusMetricReader")
def test_setup_metrics_configures_prometheus_reader(mock_prometheus_reader):
    """Test that Prometheus metric reader is configured."""
    mock_reader = MagicMock()
    mock_prometheus_reader.return_value = mock_reader

    setup_metrics(service_name="test-service")

    # PrometheusMetricReader should be called
    mock_prometheus_reader.assert_called_once()


def test_get_metrics_app_returns_asgi_app():
    """Test that get_metrics_app returns a valid ASGI application."""
    from ktrdr.monitoring.setup import get_metrics_app

    # Setup metrics first
    setup_metrics(service_name="test-service")

    # Get metrics app
    metrics_app = get_metrics_app()

    # Should return an ASGI app (callable)
    assert callable(metrics_app)

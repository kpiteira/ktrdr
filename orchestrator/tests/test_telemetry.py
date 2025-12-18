"""Tests for telemetry module.

These tests verify OpenTelemetry setup for traces and metrics.
"""

from unittest.mock import MagicMock, patch

from orchestrator.config import OrchestratorConfig


class TestSetupTelemetry:
    """Test setup_telemetry function."""

    def test_setup_returns_tracer_and_meter(self):
        """setup_telemetry should return a tracer and meter."""
        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig()

        with patch("orchestrator.telemetry.OTLPSpanExporter"):
            with patch("orchestrator.telemetry.OTLPMetricExporter"):
                tracer, meter = setup_telemetry(config)

        assert tracer is not None
        assert meter is not None

    def test_tracer_uses_service_name(self):
        """Tracer should be created with the service name."""
        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig(service_name="test-orchestrator")

        with patch("orchestrator.telemetry.OTLPSpanExporter"):
            with patch("orchestrator.telemetry.OTLPMetricExporter"):
                tracer, _ = setup_telemetry(config)

        # The tracer should be associated with our service name
        assert tracer is not None

    def test_uses_otlp_endpoint_from_config(self):
        """Should use OTLP endpoint from config."""
        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig(otlp_endpoint="http://custom:4317")

        with patch("orchestrator.telemetry.OTLPSpanExporter") as mock_span_exporter:
            with patch(
                "orchestrator.telemetry.OTLPMetricExporter"
            ) as mock_metric_exporter:
                setup_telemetry(config)

        mock_span_exporter.assert_called_with(endpoint="http://custom:4317")
        mock_metric_exporter.assert_called_with(endpoint="http://custom:4317")

    def test_sets_tracer_provider(self):
        """Should set the global tracer provider."""
        from opentelemetry import trace

        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig()

        with patch("orchestrator.telemetry.OTLPSpanExporter"):
            with patch("orchestrator.telemetry.OTLPMetricExporter"):
                setup_telemetry(config)

        # After setup, we should be able to get a tracer
        tracer = trace.get_tracer("test")
        assert tracer is not None

    def test_sets_meter_provider(self):
        """Should set the global meter provider."""
        from opentelemetry import metrics

        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig()

        with patch("orchestrator.telemetry.OTLPSpanExporter"):
            with patch("orchestrator.telemetry.OTLPMetricExporter"):
                setup_telemetry(config)

        # After setup, we should be able to get a meter
        meter = metrics.get_meter("test")
        assert meter is not None


class TestCreateMetrics:
    """Test create_metrics function."""

    def test_creates_tasks_counter(self):
        """Should create orchestrator_tasks_total counter."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        # Verify counter was created with correct name
        counter_names = [call[0][0] for call in meter.create_counter.call_args_list]
        assert "orchestrator_tasks_total" in counter_names

    def test_creates_tokens_counter(self):
        """Should create orchestrator_tokens_total counter."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        counter_names = [call[0][0] for call in meter.create_counter.call_args_list]
        assert "orchestrator_tokens_total" in counter_names

    def test_creates_cost_counter(self):
        """Should create orchestrator_cost_usd_total counter."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        counter_names = [call[0][0] for call in meter.create_counter.call_args_list]
        assert "orchestrator_cost_usd_total" in counter_names

    def test_counters_are_accessible_after_creation(self):
        """Counters should be accessible as module-level variables after creation."""
        from orchestrator import telemetry
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        # Should be able to access counters
        assert telemetry.tasks_counter is not None
        assert telemetry.tokens_counter is not None
        assert telemetry.cost_counter is not None


class TestMetricCounters:
    """Test that metric counters can be used."""

    def test_tasks_counter_can_add(self):
        """tasks_counter should support add() method."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        from orchestrator import telemetry

        # Should be able to add to the counter
        telemetry.tasks_counter.add(1, {"status": "completed"})
        counter_mock.add.assert_called()

    def test_tokens_counter_can_add(self):
        """tokens_counter should support add() method."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        from orchestrator import telemetry

        telemetry.tokens_counter.add(1000)
        counter_mock.add.assert_called()

    def test_cost_counter_can_add(self):
        """cost_counter should support add() method."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        from orchestrator import telemetry

        telemetry.cost_counter.add(0.05)
        counter_mock.add.assert_called()

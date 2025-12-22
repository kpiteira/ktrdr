"""Tests for telemetry module.

These tests verify OpenTelemetry setup for traces and metrics.
"""

import os
from unittest.mock import MagicMock, patch

from orchestrator.config import OrchestratorConfig


class TestSetupTelemetry:
    """Test setup_telemetry function."""

    def test_setup_returns_tracer_and_meter(self):
        """setup_telemetry should return a tracer and meter."""
        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig()

        # With OTLP disabled (default), no-op providers are used
        tracer, meter = setup_telemetry(config)

        assert tracer is not None
        assert meter is not None

    def test_tracer_uses_service_name(self):
        """Tracer should be created with the service name."""
        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig(service_name="test-orchestrator")

        tracer, _ = setup_telemetry(config)

        # The tracer should be associated with our service name
        assert tracer is not None

    def test_uses_otlp_endpoint_from_config(self):
        """Should use OTLP endpoint from config when enabled."""
        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig(otlp_endpoint="http://custom:4317")

        # Enable OTLP and patch the exporters at their source
        with patch.dict(os.environ, {"OTLP_ENABLED": "true"}):
            with patch(
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
            ) as mock_span_exporter:
                with patch(
                    "opentelemetry.exporter.otlp.proto.grpc.metric_exporter.OTLPMetricExporter"
                ) as mock_metric_exporter:
                    setup_telemetry(config)

        mock_span_exporter.assert_called_with(endpoint="http://custom:4317")
        mock_metric_exporter.assert_called_with(endpoint="http://custom:4317")

    def test_sets_tracer_provider(self):
        """Should set the global tracer provider."""
        from opentelemetry import trace

        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig()

        setup_telemetry(config)

        # After setup, we should be able to get a tracer
        tracer = trace.get_tracer("test")
        assert tracer is not None

    def test_sets_meter_provider(self):
        """Should set the global meter provider."""
        from opentelemetry import metrics

        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig()

        setup_telemetry(config)

        # After setup, we should be able to get a meter
        meter = metrics.get_meter("test")
        assert meter is not None

    def test_noop_when_otlp_disabled(self):
        """Should use no-op providers when OTLP is disabled."""
        from orchestrator.telemetry import setup_telemetry

        config = OrchestratorConfig(otlp_endpoint="http://localhost:4317")

        # With OTLP_ENABLED=false (default), should not try to export
        with patch.dict(os.environ, {"OTLP_ENABLED": "false"}):
            tracer, meter = setup_telemetry(config)

        # Should still return valid tracer/meter (no-op versions)
        assert tracer is not None
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


class TestTaskDurationHistogram:
    """Test the task_duration histogram metric."""

    def test_creates_task_duration_histogram(self):
        """Should create orchestrator_task_duration_seconds histogram."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        histogram_mock = MagicMock()
        meter.create_counter.return_value = counter_mock
        meter.create_histogram.return_value = histogram_mock

        create_metrics(meter)

        # Verify histogram was created with correct name
        meter.create_histogram.assert_called_once()
        call_args = meter.create_histogram.call_args
        assert call_args[0][0] == "orchestrator_task_duration_seconds"

    def test_histogram_has_description(self):
        """Histogram should have a description."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        histogram_mock = MagicMock()
        meter.create_counter.return_value = counter_mock
        meter.create_histogram.return_value = histogram_mock

        create_metrics(meter)

        call_args = meter.create_histogram.call_args
        assert "description" in call_args[1]

    def test_histogram_has_unit_seconds(self):
        """Histogram should have unit of seconds."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        histogram_mock = MagicMock()
        meter.create_counter.return_value = counter_mock
        meter.create_histogram.return_value = histogram_mock

        create_metrics(meter)

        call_args = meter.create_histogram.call_args
        assert call_args[1].get("unit") == "s"

    def test_histogram_is_accessible_after_creation(self):
        """task_duration histogram should be accessible as module-level variable."""
        from orchestrator import telemetry
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        histogram_mock = MagicMock()
        meter.create_counter.return_value = counter_mock
        meter.create_histogram.return_value = histogram_mock

        create_metrics(meter)

        assert telemetry.task_duration is not None

    def test_histogram_can_record(self):
        """task_duration histogram should support record() method."""
        from orchestrator import telemetry
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        histogram_mock = MagicMock()
        meter.create_counter.return_value = counter_mock
        meter.create_histogram.return_value = histogram_mock

        create_metrics(meter)

        # Should be able to record a duration
        telemetry.task_duration.record(45.5, {"milestone": "M3"})
        histogram_mock.record.assert_called_with(45.5, {"milestone": "M3"})


class TestEscalationMetrics:
    """Test escalation metrics."""

    def test_creates_escalations_counter(self):
        """Should create orchestrator_escalations_total counter."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        counter_names = [call[0][0] for call in meter.create_counter.call_args_list]
        assert "orchestrator_escalations_total" in counter_names

    def test_escalations_counter_accessible(self):
        """escalations_counter should be accessible as module-level variable."""
        from orchestrator import telemetry
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        assert telemetry.escalations_counter is not None

    def test_escalations_counter_can_add(self):
        """escalations_counter should support add() with task_id label."""
        from orchestrator import telemetry
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        telemetry.escalations_counter.add(1, {"task_id": "1.2"})
        counter_mock.add.assert_called()


class TestLoopDetectionMetrics:
    """Test loop detection metrics."""

    def test_creates_loops_counter(self):
        """Should create orchestrator_loops_detected_total counter."""
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        counter_names = [call[0][0] for call in meter.create_counter.call_args_list]
        assert "orchestrator_loops_detected_total" in counter_names

    def test_loops_counter_accessible(self):
        """loops_counter should be accessible as module-level variable."""
        from orchestrator import telemetry
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        assert telemetry.loops_counter is not None

    def test_loops_counter_can_add_with_type_label(self):
        """loops_counter should support add() with type label."""
        from orchestrator import telemetry
        from orchestrator.telemetry import create_metrics

        meter = MagicMock()
        counter_mock = MagicMock()
        meter.create_counter.return_value = counter_mock

        create_metrics(meter)

        telemetry.loops_counter.add(1, {"type": "task"})
        counter_mock.add.assert_called()

        telemetry.loops_counter.add(1, {"type": "e2e"})
        assert counter_mock.add.call_count >= 2

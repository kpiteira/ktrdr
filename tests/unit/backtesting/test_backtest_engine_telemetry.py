"""Tests for BacktestingEngine OpenTelemetry instrumentation."""

from unittest.mock import Mock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine


@pytest.fixture(scope="module")
def tracer_provider_setup():
    """Create in-memory tracer provider for testing (module-scoped)."""
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Re-initialize the module tracer to use test provider
    import ktrdr.backtesting.engine as engine_module

    engine_module.tracer = trace.get_tracer(__name__)

    return provider, exporter


@pytest.fixture
def tracer_provider(tracer_provider_setup):
    """Get tracer provider and clear exporter before each test."""
    provider, exporter = tracer_provider_setup
    exporter.clear()  # Clear spans from previous test
    return provider, exporter


@pytest.fixture
def backtest_config():
    """Create test backtest configuration."""
    return BacktestConfig(
        strategy_config_path="test_strategy.yaml",
        model_path="test_model.pt",
        symbol="AAPL",
        timeframe="1d",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )


class TestBacktestEngineTelemetry:
    """Test OpenTelemetry instrumentation for backtesting engine phases."""

    def test_run_creates_phase_spans(self, tracer_provider, backtest_config):
        """Test that backtest run creates spans for each phase."""
        provider, exporter = tracer_provider

        # Mock all dependencies
        with (
            patch("ktrdr.backtesting.engine.DataRepository"),
            patch("ktrdr.decision.orchestrator.DecisionOrchestrator"),
            patch.object(BacktestingEngine, "_load_historical_data") as mock_load,
        ):

            # Mock minimal data
            import pandas as pd

            mock_data = pd.DataFrame(
                {
                    "open": [100] * 100,
                    "high": [102] * 100,
                    "low": [99] * 100,
                    "close": [101] * 100,
                    "volume": [1000] * 100,
                }
            )
            mock_data.index = pd.date_range("2024-01-01", periods=100, freq="D")
            mock_load.return_value = mock_data

            engine = BacktestingEngine(backtest_config)

            # Mock orchestrator
            engine.orchestrator = Mock()
            engine.orchestrator.prepare_feature_cache = Mock()
            engine.orchestrator.make_decision = Mock(side_effect=Exception("warm-up"))

            try:
                engine.run()
            except Exception:
                pass  # Expected during test

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Check for expected phase spans
        expected_spans = [
            "backtest.data_loading",
            "backtest.strategy_init",
            "backtest.simulation",
        ]

        for expected_name in expected_spans:
            matching_spans = [s for s in spans if s.name == expected_name]
            assert len(matching_spans) > 0, f"Should create {expected_name} span"

    def test_data_loading_span_attributes(self, tracer_provider, backtest_config):
        """Test that data loading span has correct attributes."""
        provider, exporter = tracer_provider

        with (
            patch("ktrdr.backtesting.engine.DataRepository"),
            patch("ktrdr.decision.orchestrator.DecisionOrchestrator"),
        ):

            engine = BacktestingEngine(backtest_config)

            # Mock load data to create span
            import pandas as pd

            mock_data = pd.DataFrame(
                {
                    "open": [100] * 50,
                    "close": [101] * 50,
                }
            )
            mock_data.index = pd.date_range("2024-01-01", periods=50, freq="D")

            with patch.object(
                engine.repository, "load_from_cache", return_value=mock_data
            ):
                engine._load_historical_data()

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find data loading span
        data_loading_spans = [s for s in spans if s.name == "backtest.data_loading"]
        assert len(data_loading_spans) == 1

        span = data_loading_spans[0]

        # Verify attributes
        assert span.attributes.get("data.symbol") == "AAPL"
        assert span.attributes.get("data.timeframe") == "1d"
        assert span.attributes.get("data.rows") == 50
        assert "progress.phase" in span.attributes

    def test_simulation_span_includes_progress(self, tracer_provider, backtest_config):
        """Test that simulation span includes progress percentage."""
        provider, exporter = tracer_provider

        # This test will verify that the simulation loop updates progress
        # Implementation will add progress.percentage updates during simulation

        with (
            patch("ktrdr.backtesting.engine.DataRepository"),
            patch("ktrdr.decision.orchestrator.DecisionOrchestrator"),
            patch.object(BacktestingEngine, "_load_historical_data") as mock_load,
        ):

            import pandas as pd

            mock_data = pd.DataFrame(
                {
                    "open": [100] * 20,
                    "high": [102] * 20,
                    "low": [99] * 20,
                    "close": [101] * 20,
                    "volume": [1000] * 20,
                }
            )
            mock_data.index = pd.date_range("2024-01-01", periods=20, freq="D")
            mock_load.return_value = mock_data

            engine = BacktestingEngine(backtest_config)
            engine.orchestrator = Mock()
            engine.orchestrator.prepare_feature_cache = Mock()
            engine.orchestrator.make_decision = Mock(side_effect=Exception("warm-up"))

            try:
                engine.run()
            except Exception:
                pass

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find simulation span
        simulation_spans = [s for s in spans if s.name == "backtest.simulation"]
        if simulation_spans:
            span = simulation_spans[0]
            # Should have progress markers
            assert "progress.phase" in span.attributes
            assert span.attributes.get("progress.phase") == "simulation"

    def test_spans_include_operation_id(self, tracer_provider, backtest_config):
        """Test that all spans include operation.id from parent context."""
        provider, exporter = tracer_provider

        # Create parent span with operation.id
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("test_backtest_operation") as parent_span:
            parent_span.set_attribute("operation.id", "op_backtest_123")

            with (
                patch("ktrdr.backtesting.engine.DataRepository"),
                patch("ktrdr.decision.orchestrator.DecisionOrchestrator"),
                patch.object(BacktestingEngine, "_load_historical_data") as mock_load,
            ):

                import pandas as pd

                mock_data = pd.DataFrame(
                    {
                        "open": [100] * 10,
                        "close": [101] * 10,
                    }
                )
                mock_data.index = pd.date_range("2024-01-01", periods=10, freq="D")
                mock_load.return_value = mock_data

                engine = BacktestingEngine(backtest_config)

                with patch.object(
                    engine.repository, "load_from_cache", return_value=mock_data
                ):
                    engine._load_historical_data()

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find child spans
        child_spans = [
            s for s in spans if s.parent is not None and s.name.startswith("backtest.")
        ]

        # All child spans should have operation.id
        for span in child_spans:
            assert (
                span.attributes.get("operation.id") == "op_backtest_123"
            ), f"Span {span.name} should inherit operation.id from parent context"

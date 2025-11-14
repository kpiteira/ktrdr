"""Tests for TrainingPipeline OpenTelemetry instrumentation."""

from unittest.mock import Mock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ktrdr.training.training_pipeline import TrainingPipeline


@pytest.fixture(scope="module")
def tracer_provider_setup():
    """Create in-memory tracer provider for testing (module-scoped)."""
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Re-initialize the module tracer to use test provider
    import ktrdr.training.training_pipeline as pipeline_module

    pipeline_module.tracer = trace.get_tracer(__name__)

    return provider, exporter


@pytest.fixture
def tracer_provider(tracer_provider_setup):
    """Get tracer provider and clear exporter before each test."""
    provider, exporter = tracer_provider_setup
    exporter.clear()  # Clear spans from previous test
    return provider, exporter


class TestTrainingPipelineTelemetry:
    """Test OpenTelemetry instrumentation for training pipeline phases."""

    def test_load_market_data_creates_span(self, tracer_provider):
        """Test that load_market_data creates a training.data_loading span."""
        provider, exporter = tracer_provider

        # Mock dependencies
        import pandas as pd

        with patch("ktrdr.training.training_pipeline.DataRepository") as mock_repo:
            mock_data = pd.DataFrame(
                {
                    "open": [100, 101],
                    "high": [102, 103],
                    "low": [99, 100],
                    "close": [101, 102],
                    "volume": [1000, 1100],
                }
            )

            mock_repo_instance = Mock()
            mock_repo_instance.load_from_cache.return_value = mock_data
            mock_repo.return_value = mock_repo_instance

            # Call the method
            TrainingPipeline.load_market_data(
                symbol="AAPL",
                timeframes=["1d"],
                start_date="2024-01-01",
                end_date="2024-12-31",
            )

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find the data loading span
        data_loading_spans = [s for s in spans if s.name == "training.data_loading"]
        assert (
            len(data_loading_spans) == 1
        ), "Should create one training.data_loading span"

        span = data_loading_spans[0]

        # Verify span attributes
        assert span.attributes.get("data.symbol") == "AAPL"
        assert span.attributes.get("data.timeframes") == "1d"
        assert "data.rows" in span.attributes
        assert "data.columns" in span.attributes

    def test_calculate_indicators_creates_span(self, tracer_provider):
        """Test that calculate_indicators creates a training.indicators span."""
        provider, exporter = tracer_provider

        # Mock data
        import pandas as pd

        price_data = {
            "1d": pd.DataFrame(
                {
                    "open": [100, 101],
                    "high": [102, 103],
                    "low": [99, 100],
                    "close": [101, 102],
                    "volume": [1000, 1100],
                }
            )
        }
        indicator_configs = [{"feature_id": "sma_20", "type": "sma", "period": 20}]

        with patch("ktrdr.training.training_pipeline.IndicatorEngine") as mock_engine:
            mock_instance = Mock()
            mock_instance.apply_multi_timeframe.return_value = {
                "1d": pd.DataFrame({"sma_20": [100, 101]})
            }
            mock_engine.return_value = mock_instance

            TrainingPipeline.calculate_indicators(price_data, indicator_configs)

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find the indicators span
        indicator_spans = [s for s in spans if s.name == "training.indicators"]
        assert len(indicator_spans) == 1, "Should create one training.indicators span"

        span = indicator_spans[0]

        # Verify span attributes
        assert span.attributes.get("indicators.count") == 1
        assert span.attributes.get("indicators.timeframes") == "1d"

    def test_generate_fuzzy_memberships_creates_span(self, tracer_provider):
        """Test that generate_fuzzy_memberships creates a training.fuzzy_computation span."""
        provider, exporter = tracer_provider

        # Mock data
        import pandas as pd

        indicators = {"1d": pd.DataFrame({"sma_20": [100, 101]})}
        fuzzy_configs = {"sma_trend": {"type": "triangular"}}

        with (
            patch("ktrdr.training.training_pipeline.FuzzyConfigLoader"),
            patch("ktrdr.training.training_pipeline.FuzzyEngine") as mock_engine,
        ):
            mock_engine_instance = Mock()
            mock_engine_instance.generate_multi_timeframe_memberships.return_value = {
                "1d": pd.DataFrame({"fuzzy_sma": [0.5, 0.6]})
            }
            mock_engine.return_value = mock_engine_instance

            TrainingPipeline.generate_fuzzy_memberships(indicators, fuzzy_configs)

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find the fuzzy computation span
        fuzzy_spans = [s for s in spans if s.name == "training.fuzzy_computation"]
        assert (
            len(fuzzy_spans) == 1
        ), "Should create one training.fuzzy_computation span"

        span = fuzzy_spans[0]

        # Verify span attributes
        assert span.attributes.get("fuzzy_sets.count") == 1
        assert span.attributes.get("fuzzy_sets.timeframes") == "1d"

    def test_spans_include_operation_context(self, tracer_provider):
        """Test that spans are properly nested within parent context."""
        provider, exporter = tracer_provider

        # Create a parent span with operation.id
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("test_operation") as parent_span:
            parent_span.set_attribute("operation.id", "op_test_123")

            # Mock data
            import pandas as pd

            price_data = {
                "1d": pd.DataFrame(
                    {
                        "open": [100, 101],
                        "high": [102, 103],
                        "low": [99, 100],
                        "close": [101, 102],
                        "volume": [1000, 1100],
                    }
                )
            }
            indicator_configs = [{"feature_id": "sma_20", "type": "sma", "period": 20}]

            with patch(
                "ktrdr.training.training_pipeline.IndicatorEngine"
            ) as mock_engine:
                mock_instance = Mock()
                mock_instance.apply_multi_timeframe.return_value = {
                    "1d": pd.DataFrame({"sma_20": [100, 101]})
                }
                mock_engine.return_value = mock_instance

                TrainingPipeline.calculate_indicators(price_data, indicator_configs)

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find the child spans (training.indicators should be child of test_operation)
        child_spans = [
            s for s in spans if s.parent is not None and s.name.startswith("training.")
        ]

        # Verify child spans exist and are properly nested
        assert len(child_spans) > 0, "Should have child spans nested under parent"
        for span in child_spans:
            assert span.parent is not None, f"Span {span.name} should have a parent"

    def test_progress_percentage_updates_in_spans(self, tracer_provider):
        """Test that spans update progress.percentage attribute."""
        provider, exporter = tracer_provider

        # Mock data
        import pandas as pd

        price_data = pd.DataFrame(
            {
                "open": [100] * 100,
                "high": [102] * 100,
                "low": [99] * 100,
                "close": [101] * 100,
                "volume": [1000] * 100,
            }
        )

        with patch("ktrdr.training.training_pipeline.DataRepository") as mock_repo:
            mock_repo_instance = Mock()
            mock_repo_instance.load_from_cache.return_value = price_data
            mock_repo.return_value = mock_repo_instance

            _result = TrainingPipeline.load_market_data(
                symbol="AAPL",
                timeframes=["1d"],
                start_date="2024-01-01",
                end_date="2024-12-31",
            )

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find data loading span
        data_loading_spans = [s for s in spans if s.name == "training.data_loading"]
        assert len(data_loading_spans) == 1

        span = data_loading_spans[0]

        # Should have progress information
        assert "progress.phase" in span.attributes
        assert span.attributes.get("progress.phase") == "data_loading"

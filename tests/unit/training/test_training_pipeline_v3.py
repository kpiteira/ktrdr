"""Unit tests for TrainingPipeline v3 support.

Tests the v3-specific functionality in TrainingPipeline:
- Pipeline accepts v3 config
- Features computed for all timeframes
- Column order matches FeatureResolver output
- Multiple symbols handled correctly
- Missing timeframe data handled gracefully
"""

import pandas as pd
import pytest

from ktrdr.config.feature_resolver import FeatureResolver
from ktrdr.config.models import (
    FuzzySetDefinition,
    IndicatorDefinition,
    NNInputSpec,
    StrategyConfigurationV3,
    SymbolConfiguration,
    SymbolMode,
    TimeframeConfiguration,
    TimeframeMode,
    TrainingDataConfiguration,
)


@pytest.fixture
def v3_strategy_config() -> StrategyConfigurationV3:
    """Create a valid v3 strategy configuration for testing."""
    return StrategyConfigurationV3(
        name="test_v3_strategy",
        version="3.0",
        description="Test v3 strategy for pipeline testing",
        training_data=TrainingDataConfiguration(
            symbols=SymbolConfiguration(mode=SymbolMode.SINGLE, symbol="EURUSD"),
            timeframes=TimeframeConfiguration(
                mode=TimeframeMode.MULTI_TIMEFRAME,
                timeframes=["5m", "1h"],
                base_timeframe="1h",
            ),
            history_required=100,
        ),
        indicators={
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "ema_20": IndicatorDefinition(type="ema", period=20),
        },
        fuzzy_sets={
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                neutral=[30, 50, 70],
                overbought=[60, 75, 100],
            ),
        },
        nn_inputs=[
            NNInputSpec(fuzzy_set="rsi_fast", timeframes="all"),
        ],
        model={"type": "mlp", "architecture": {"hidden_layers": [64, 32]}},
        decisions={"output_format": "classification", "confidence_threshold": 0.6},
        training={"method": "supervised", "labels": {"source": "zigzag"}},
    )


@pytest.fixture
def sample_price_data() -> dict[str, pd.DataFrame]:
    """Create sample multi-timeframe price data."""
    # 5m timeframe data (more granular)
    dates_5m = pd.date_range("2024-01-01", periods=200, freq="5min")
    df_5m = pd.DataFrame(
        {
            "open": [100.0 + i * 0.1 for i in range(200)],
            "high": [101.0 + i * 0.1 for i in range(200)],
            "low": [99.0 + i * 0.1 for i in range(200)],
            "close": [100.5 + i * 0.1 for i in range(200)],
            "volume": [1000 + i * 10 for i in range(200)],
        },
        index=dates_5m,
    )

    # 1h timeframe data (less granular)
    dates_1h = pd.date_range("2024-01-01", periods=100, freq="1h")
    df_1h = pd.DataFrame(
        {
            "open": [100.0 + i * 0.5 for i in range(100)],
            "high": [102.0 + i * 0.5 for i in range(100)],
            "low": [98.0 + i * 0.5 for i in range(100)],
            "close": [101.0 + i * 0.5 for i in range(100)],
            "volume": [5000 + i * 50 for i in range(100)],
        },
        index=dates_1h,
    )

    return {"5m": df_5m, "1h": df_1h}


class TestTrainingPipelineV3Constructor:
    """Tests for TrainingPipelineV3 constructor accepting v3 config."""

    def test_pipeline_accepts_v3_config(self, v3_strategy_config):
        """Pipeline should accept v3 strategy configuration."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        assert pipeline.config == v3_strategy_config
        assert pipeline.feature_resolver is not None
        assert pipeline.indicator_engine is not None
        assert pipeline.fuzzy_engine is not None

    def test_pipeline_initializes_engines_with_v3_config(self, v3_strategy_config):
        """Pipeline should initialize engines with v3 config format."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        # IndicatorEngine should have v3 indicators
        assert len(pipeline.indicator_engine._indicators) == 2
        assert "rsi_14" in pipeline.indicator_engine._indicators

        # FuzzyEngine should be in v3 mode
        assert pipeline.fuzzy_engine._is_v3_mode is True
        assert "rsi_fast" in pipeline.fuzzy_engine._fuzzy_sets


class TestTrainingPipelineV3PrepareFeatures:
    """Tests for prepare_features() method with v3 configuration."""

    def test_features_computed_for_all_timeframes(
        self, v3_strategy_config, sample_price_data
    ):
        """Features should be computed for all timeframes in nn_inputs."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        # Mock data: {symbol: {timeframe: DataFrame}}
        data = {"EURUSD": sample_price_data}

        features = pipeline.prepare_features(data)

        # Should have features for both 5m and 1h timeframes
        assert isinstance(features, pd.DataFrame)

        # Check for expected feature columns (from FeatureResolver)
        # For "all" timeframes with rsi_fast: 5m and 1h × 3 memberships = 6 features
        expected_features = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_neutral",
            "5m_rsi_fast_overbought",
            "1h_rsi_fast_oversold",
            "1h_rsi_fast_neutral",
            "1h_rsi_fast_overbought",
        ]
        for feature in expected_features:
            assert feature in features.columns, f"Missing feature: {feature}"

    def test_column_order_matches_feature_resolver_output(
        self, v3_strategy_config, sample_price_data
    ):
        """Column order must match FeatureResolver output exactly."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        # Get expected order from FeatureResolver
        resolver = FeatureResolver()
        resolved = resolver.resolve(v3_strategy_config)
        expected_order = [f.feature_id for f in resolved]

        # Prepare features
        data = {"EURUSD": sample_price_data}
        features = pipeline.prepare_features(data)

        # Columns should be in exact expected order
        actual_columns = list(features.columns)
        assert actual_columns == expected_order, (
            f"Column order mismatch.\n"
            f"Expected: {expected_order}\n"
            f"Actual: {actual_columns}"
        )

    def test_multiple_symbols_handled_correctly(
        self, v3_strategy_config, sample_price_data
    ):
        """Multiple symbols should be concatenated correctly."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        # Create data for multiple symbols
        data = {
            "EURUSD": sample_price_data,
            "GBPUSD": sample_price_data,  # Same data structure for simplicity
        }

        features = pipeline.prepare_features(data)

        # Features from both symbols should be concatenated (rows)
        # Note: actual row count depends on alignment, but should be > single symbol
        assert isinstance(features, pd.DataFrame)
        assert len(features) > 0

    def test_missing_timeframe_handled_gracefully(self, v3_strategy_config):
        """Missing timeframe data should be handled gracefully."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        # Only provide 5m data, missing 1h
        partial_data = {
            "EURUSD": {
                "5m": pd.DataFrame(
                    {
                        "open": [100.0] * 100,
                        "high": [101.0] * 100,
                        "low": [99.0] * 100,
                        "close": [100.5] * 100,
                        "volume": [1000] * 100,
                    },
                    index=pd.date_range("2024-01-01", periods=100, freq="5min"),
                )
            }
        }

        # Should handle gracefully (either skip missing or raise clear error)
        # The expected behavior depends on implementation - test documents requirement
        features = pipeline.prepare_features(partial_data)
        assert isinstance(features, pd.DataFrame)
        # At minimum, 5m features should be present
        assert any("5m_" in col for col in features.columns)


class TestTrainingPipelineV3GroupRequirements:
    """Tests for _group_requirements_by_timeframe() helper method."""

    def test_groups_indicators_by_timeframe(self, v3_strategy_config):
        """Should group indicator requirements by timeframe."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        resolver = FeatureResolver()
        resolved = resolver.resolve(v3_strategy_config)

        requirements = pipeline._group_requirements_by_timeframe(resolved)

        # Should have entries for both timeframes
        assert "5m" in requirements
        assert "1h" in requirements

        # Each timeframe should list required indicators and fuzzy sets
        assert "indicators" in requirements["5m"]
        assert "fuzzy_sets" in requirements["5m"]

        # rsi_14 should be required (used by rsi_fast)
        assert "rsi_14" in requirements["5m"]["indicators"]
        assert "rsi_fast" in requirements["5m"]["fuzzy_sets"]


class TestTrainingPipelineV3WithWiring:
    """Integration tests for TrainingPipelineV3 wiring with v3 engines."""

    def test_pipeline_wired_correctly_with_v3_engines(
        self, v3_strategy_config, sample_price_data
    ):
        """Pipeline should be correctly wired with v3 engines."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        # Verify wiring by running through the pipeline
        data = {"EURUSD": sample_price_data}
        features = pipeline.prepare_features(data)

        # Features should be valid membership values (0-1 range)
        assert features.min().min() >= 0.0
        assert features.max().max() <= 1.0

    def test_indicator_engine_computes_for_timeframe(
        self, v3_strategy_config, sample_price_data
    ):
        """IndicatorEngine should compute indicators for specific timeframe."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        # Compute indicators for 5m timeframe
        df = sample_price_data["5m"]
        indicator_ids = {"rsi_14"}

        result = pipeline.indicator_engine.compute_for_timeframe(
            df, "5m", indicator_ids
        )

        # Should have rsi_14 indicator column
        assert "rsi_14" in result.columns or "5m_rsi_14" in result.columns

    def test_fuzzy_engine_fuzzifies_correctly(self, v3_strategy_config):
        """FuzzyEngine should fuzzify indicator values correctly."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        pipeline = TrainingPipelineV3(v3_strategy_config)

        # Create sample RSI values
        rsi_values = pd.Series([20.0, 50.0, 80.0], name="rsi_14")

        # Fuzzify using v3 method
        fuzzy_df = pipeline.fuzzy_engine.fuzzify("rsi_fast", rsi_values)

        # Should have columns for each membership
        assert "rsi_fast_oversold" in fuzzy_df.columns
        assert "rsi_fast_neutral" in fuzzy_df.columns
        assert "rsi_fast_overbought" in fuzzy_df.columns

        # Value 20 should be mostly oversold
        assert fuzzy_df.loc[0, "rsi_fast_oversold"] > 0.5
        # Value 80 should be mostly overbought
        assert fuzzy_df.loc[2, "rsi_fast_overbought"] > 0.5

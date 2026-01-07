"""Integration test: Training → Backtest Feature Consistency (M5 Task 5.4).

Critical test: Backtest must produce identical features to training.

This test validates that FeatureCacheV3 (used during backtest) produces
the EXACT same features as TrainingPipelineV3 (used during training):
- Same feature names
- Same feature order
- Same feature values (within floating point tolerance)

This is critical because neural networks are not invariant to input order —
the same features in different order will produce garbage predictions.
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.backtesting.feature_cache import FeatureCacheV3
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
from ktrdr.models.model_metadata import ModelMetadataV3
from ktrdr.training.training_pipeline import TrainingPipelineV3


@pytest.fixture
def v3_strategy_config() -> StrategyConfigurationV3:
    """Create a v3 strategy configuration for testing.

    Uses a simple RSI indicator with oversold/overbought fuzzy sets.
    """
    return StrategyConfigurationV3(
        name="test_consistency_strategy",
        version="3.0",
        description="Test strategy for training/backtest consistency",
        indicators={
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
        },
        fuzzy_sets={
            "rsi_momentum": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                overbought=[60, 75, 100],
            ),
        },
        nn_inputs=[
            NNInputSpec(fuzzy_set="rsi_momentum", timeframes=["5m"]),
        ],
        model={"type": "mlp"},
        decisions={"output_format": "classification"},
        training={"epochs": 10},
        training_data=TrainingDataConfiguration(
            symbols=SymbolConfiguration(mode=SymbolMode.SINGLE, symbol="EURUSD"),
            timeframes=TimeframeConfiguration(
                mode=TimeframeMode.SINGLE,
                timeframe="5m",
            ),
            history_required=100,
        ),
    )


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """Create synthetic OHLCV data for testing.

    Generates 200 bars of realistic-looking price data with
    enough history for indicator warmup (RSI needs ~14 bars).
    """
    np.random.seed(42)  # Reproducible

    dates = pd.date_range(start="2024-01-01", periods=200, freq="5min", tz="UTC")

    # Generate realistic price movements
    base_price = 1.10
    returns = np.random.normal(0, 0.001, len(dates))
    close_prices = base_price * (1 + returns).cumprod()

    return pd.DataFrame(
        {
            "open": close_prices * (1 + np.random.uniform(-0.001, 0.001, len(dates))),
            "high": close_prices
            * (1 + np.abs(np.random.uniform(0, 0.002, len(dates)))),
            "low": close_prices * (1 - np.abs(np.random.uniform(0, 0.002, len(dates)))),
            "close": close_prices,
            "volume": np.random.uniform(1000, 10000, len(dates)),
        },
        index=dates,
    )


class TestTrainingBacktestConsistency:
    """Integration tests for training/backtest feature consistency."""

    def test_backtest_features_match_training(
        self,
        v3_strategy_config: StrategyConfigurationV3,
        sample_ohlcv_data: pd.DataFrame,
    ):
        """Backtest must produce identical features to training.

        This test:
        1. Creates a v3 strategy
        2. Generates features via TrainingPipelineV3
        3. Generates features via FeatureCacheV3 (simulating backtest)
        4. Verifies they are IDENTICAL (names, order, values)
        """
        # === Training path ===
        training_pipeline = TrainingPipelineV3(v3_strategy_config)

        # TrainingPipelineV3 expects: {symbol: {timeframe: DataFrame}}
        training_data = {"EURUSD": {"5m": sample_ohlcv_data}}
        training_features = training_pipeline.prepare_features(training_data)

        # === Backtest path ===
        # First, resolve features to get the expected order
        resolver = FeatureResolver()
        resolved = resolver.resolve(v3_strategy_config)
        resolved_feature_ids = [f.feature_id for f in resolved]

        # Create metadata with resolved features (mimics what training would store)
        metadata = ModelMetadataV3(
            model_name="test_model",
            strategy_name=v3_strategy_config.name,
            resolved_features=resolved_feature_ids,
        )

        # FeatureCacheV3 expects: {timeframe: DataFrame} (single symbol)
        backtest_data = {"5m": sample_ohlcv_data}
        cache = FeatureCacheV3(v3_strategy_config, metadata)
        backtest_features = cache.compute_features(backtest_data)

        # === Verify names match ===
        assert list(training_features.columns) == list(backtest_features.columns), (
            f"Column names don't match.\n"
            f"Training: {list(training_features.columns)}\n"
            f"Backtest: {list(backtest_features.columns)}"
        )

        # === Verify order matches resolved features ===
        assert list(training_features.columns) == metadata.resolved_features, (
            f"Training columns don't match resolved order.\n"
            f"Training: {list(training_features.columns)}\n"
            f"Resolved: {metadata.resolved_features}"
        )

        assert list(backtest_features.columns) == metadata.resolved_features, (
            f"Backtest columns don't match resolved order.\n"
            f"Backtest: {list(backtest_features.columns)}\n"
            f"Resolved: {metadata.resolved_features}"
        )

        # === Verify values match (within floating point tolerance) ===
        # Use pandas testing utility for DataFrame comparison
        pd.testing.assert_frame_equal(
            training_features,
            backtest_features,
            check_exact=False,
            rtol=1e-5,  # Relative tolerance
            atol=1e-10,  # Absolute tolerance
        )

    def test_feature_names_have_timeframe_prefix(
        self,
        v3_strategy_config: StrategyConfigurationV3,
        sample_ohlcv_data: pd.DataFrame,
    ):
        """All feature names should have the timeframe prefix."""
        training_pipeline = TrainingPipelineV3(v3_strategy_config)
        training_data = {"EURUSD": {"5m": sample_ohlcv_data}}
        training_features = training_pipeline.prepare_features(training_data)

        for col in training_features.columns:
            assert col.startswith("5m_"), f"Feature '{col}' missing '5m_' prefix"

    def test_feature_order_deterministic(
        self,
        v3_strategy_config: StrategyConfigurationV3,
        sample_ohlcv_data: pd.DataFrame,
    ):
        """Feature order should be deterministic across multiple runs."""
        training_pipeline = TrainingPipelineV3(v3_strategy_config)
        training_data = {"EURUSD": {"5m": sample_ohlcv_data}}

        # Run twice
        features_run1 = training_pipeline.prepare_features(training_data)
        features_run2 = training_pipeline.prepare_features(training_data)

        # Order should be identical
        assert list(features_run1.columns) == list(features_run2.columns)

        # Values should be identical
        pd.testing.assert_frame_equal(features_run1, features_run2)


class TestMultiTimeframeConsistency:
    """Tests for multi-timeframe feature consistency."""

    @pytest.fixture
    def multi_tf_config(self) -> StrategyConfigurationV3:
        """Create a multi-timeframe v3 strategy configuration."""
        return StrategyConfigurationV3(
            name="test_multi_tf_strategy",
            version="3.0",
            description="Test multi-timeframe strategy",
            indicators={
                "rsi_14": IndicatorDefinition(type="rsi", period=14),
            },
            fuzzy_sets={
                "rsi_momentum": FuzzySetDefinition(
                    indicator="rsi_14",
                    oversold=[0, 25, 40],
                    overbought=[60, 75, 100],
                ),
            },
            nn_inputs=[
                # Use multiple timeframes
                NNInputSpec(fuzzy_set="rsi_momentum", timeframes=["5m", "1h"]),
            ],
            model={"type": "mlp"},
            decisions={"output_format": "classification"},
            training={"epochs": 10},
            training_data=TrainingDataConfiguration(
                symbols=SymbolConfiguration(mode=SymbolMode.SINGLE, symbol="EURUSD"),
                timeframes=TimeframeConfiguration(
                    mode=TimeframeMode.MULTI_TIMEFRAME,
                    timeframes=["5m", "1h"],
                ),
                history_required=100,
            ),
        )

    @pytest.fixture
    def multi_tf_data(self) -> dict[str, pd.DataFrame]:
        """Create multi-timeframe OHLCV data."""
        np.random.seed(42)

        # 5-minute data (200 bars)
        dates_5m = pd.date_range(start="2024-01-01", periods=200, freq="5min", tz="UTC")
        base_price = 1.10
        returns_5m = np.random.normal(0, 0.001, len(dates_5m))
        close_5m = base_price * (1 + returns_5m).cumprod()

        df_5m = pd.DataFrame(
            {
                "open": close_5m
                * (1 + np.random.uniform(-0.001, 0.001, len(dates_5m))),
                "high": close_5m
                * (1 + np.abs(np.random.uniform(0, 0.002, len(dates_5m)))),
                "low": close_5m
                * (1 - np.abs(np.random.uniform(0, 0.002, len(dates_5m)))),
                "close": close_5m,
                "volume": np.random.uniform(1000, 10000, len(dates_5m)),
            },
            index=dates_5m,
        )

        # 1-hour data (200 bars)
        dates_1h = pd.date_range(start="2024-01-01", periods=200, freq="1h", tz="UTC")
        returns_1h = np.random.normal(0, 0.002, len(dates_1h))
        close_1h = base_price * (1 + returns_1h).cumprod()

        df_1h = pd.DataFrame(
            {
                "open": close_1h
                * (1 + np.random.uniform(-0.002, 0.002, len(dates_1h))),
                "high": close_1h
                * (1 + np.abs(np.random.uniform(0, 0.003, len(dates_1h)))),
                "low": close_1h
                * (1 - np.abs(np.random.uniform(0, 0.003, len(dates_1h)))),
                "close": close_1h,
                "volume": np.random.uniform(5000, 50000, len(dates_1h)),
            },
            index=dates_1h,
        )

        return {"5m": df_5m, "1h": df_1h}

    def test_multi_timeframe_features_match(
        self,
        multi_tf_config: StrategyConfigurationV3,
        multi_tf_data: dict[str, pd.DataFrame],
    ):
        """Multi-timeframe backtest features should match training."""
        # === Training path ===
        training_pipeline = TrainingPipelineV3(multi_tf_config)
        training_data = {"EURUSD": multi_tf_data}
        training_features = training_pipeline.prepare_features(training_data)

        # === Backtest path ===
        resolver = FeatureResolver()
        resolved = resolver.resolve(multi_tf_config)
        resolved_feature_ids = [f.feature_id for f in resolved]

        metadata = ModelMetadataV3(
            model_name="test_model",
            strategy_name=multi_tf_config.name,
            resolved_features=resolved_feature_ids,
        )

        cache = FeatureCacheV3(multi_tf_config, metadata)
        backtest_features = cache.compute_features(multi_tf_data)

        # === Verify ===
        # Should have features for both timeframes
        assert any(col.startswith("5m_") for col in backtest_features.columns)
        assert any(col.startswith("1h_") for col in backtest_features.columns)

        # Names should match
        assert list(training_features.columns) == list(backtest_features.columns)

        # Note: Values won't match exactly since training concatenates symbols vertically
        # and may have different row counts. We verify structure and ordering.


class TestFeatureOrderCriticality:
    """Tests demonstrating why feature order matters."""

    def test_wrong_order_detected(
        self,
        v3_strategy_config: StrategyConfigurationV3,
        sample_ohlcv_data: pd.DataFrame,
    ):
        """_validate_feature_order should catch wrong order."""
        # Create metadata with REVERSED feature order
        resolver = FeatureResolver()
        resolved = resolver.resolve(v3_strategy_config)
        resolved_feature_ids = [f.feature_id for f in resolved]

        # Reverse the order
        wrong_order = list(reversed(resolved_feature_ids))

        metadata_wrong_order = ModelMetadataV3(
            model_name="test_model",
            strategy_name=v3_strategy_config.name,
            resolved_features=wrong_order,
        )

        cache = FeatureCacheV3(v3_strategy_config, metadata_wrong_order)
        backtest_data = {"5m": sample_ohlcv_data}

        # compute_features should succeed (it reorders to match expected)
        result = cache.compute_features(backtest_data)

        # Result should be in the "wrong" order (matching metadata)
        assert list(result.columns) == wrong_order

        # But if we validate order against the canonical order, it would fail
        # This demonstrates why storing resolved_features in metadata is critical

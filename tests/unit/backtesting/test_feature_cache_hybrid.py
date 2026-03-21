"""Tests for FeatureCache hybrid encoding (raw + fuzzy features)."""

import numpy as np
import pandas as pd
import pytest

from ktrdr.backtesting.feature_cache import FeatureCache
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


@pytest.fixture
def hybrid_strategy_config():
    """Create a v3 config with both fuzzy and raw nn_inputs."""
    return StrategyConfigurationV3(
        name="test_hybrid",
        version="3.0",
        indicators={
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
        },
        fuzzy_sets={
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                overbought=[60, 75, 100],
            ),
        },
        nn_inputs=[
            NNInputSpec(fuzzy_set="rsi_fast", timeframes=["5m"]),
            NNInputSpec(
                raw_indicator="rsi_14", timeframes=["5m"], normalization="minmax"
            ),
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
def hybrid_metadata():
    """Model metadata with both fuzzy and raw features."""
    return ModelMetadataV3(
        model_name="test_model",
        strategy_name="test_hybrid",
        resolved_features=[
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_overbought",
            "5m_rsi_14_raw",
        ],
        normalization_params={
            "5m_rsi_14_raw": {"method": "minmax", "min": 10.0, "max": 90.0},
        },
    )


@pytest.fixture
def sample_data_100():
    """Sample OHLCV data for testing (100 bars)."""
    dates = pd.date_range("2024-01-01", periods=100, freq="5min")
    return {
        "5m": pd.DataFrame(
            {
                "open": np.random.uniform(100, 101, 100),
                "high": np.random.uniform(101, 102, 100),
                "low": np.random.uniform(99, 100, 100),
                "close": np.random.uniform(100, 101, 100),
                "volume": np.random.uniform(1000, 2000, 100),
            },
            index=dates,
        )
    }


class TestFeatureCacheHybrid:
    """Test FeatureCache with hybrid (fuzzy + raw) features."""

    def test_compute_features_includes_raw(
        self, hybrid_strategy_config, hybrid_metadata, sample_data_100
    ):
        """compute_features should include raw indicator columns."""
        cache = FeatureCache(hybrid_strategy_config, hybrid_metadata)
        result = cache.compute_features(sample_data_100)

        assert "5m_rsi_14_raw" in result.columns

    def test_raw_features_have_correct_order(
        self, hybrid_strategy_config, hybrid_metadata, sample_data_100
    ):
        """Features should be in the expected order from metadata."""
        cache = FeatureCache(hybrid_strategy_config, hybrid_metadata)
        result = cache.compute_features(sample_data_100)

        assert list(result.columns) == [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_overbought",
            "5m_rsi_14_raw",
        ]

    def test_raw_feature_values_normalized(
        self, hybrid_strategy_config, hybrid_metadata, sample_data_100
    ):
        """Raw features should be normalized using stored params."""
        cache = FeatureCache(hybrid_strategy_config, hybrid_metadata)
        result = cache.compute_features(sample_data_100)

        # After minmax normalization with training params, values should
        # be approximately in [0, 1] range (may slightly exceed if backtest
        # data has values outside training range)
        raw_col = result["5m_rsi_14_raw"].dropna()
        # At least verify normalization was applied (values shouldn't be in 0-100 RSI range)
        assert raw_col.max() < 50  # RSI raw values are 0-100, normalized should be much smaller

    def test_per_bar_lookup_includes_raw(
        self, hybrid_strategy_config, hybrid_metadata, sample_data_100
    ):
        """get_features_for_timestamp should include raw features."""
        cache = FeatureCache(hybrid_strategy_config, hybrid_metadata)
        cache.compute_all_features(sample_data_100)

        # Get features for a timestamp after indicator warmup
        ts = sample_data_100["5m"].index[50]
        features = cache.get_features_for_timestamp(ts)

        assert features is not None
        assert "5m_rsi_14_raw" in features

    def test_backward_compat_fuzzy_only(self):
        """FeatureCache with only fuzzy features still works."""
        config = StrategyConfigurationV3(
            name="test_fuzzy_only",
            version="3.0",
            indicators={
                "rsi_14": IndicatorDefinition(type="rsi", period=14),
            },
            fuzzy_sets={
                "rsi_fast": FuzzySetDefinition(
                    indicator="rsi_14",
                    oversold=[0, 25, 40],
                    overbought=[60, 75, 100],
                ),
            },
            nn_inputs=[
                NNInputSpec(fuzzy_set="rsi_fast", timeframes=["5m"]),
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
        metadata = ModelMetadataV3(
            model_name="test_model",
            strategy_name="test_fuzzy_only",
            resolved_features=["5m_rsi_fast_oversold", "5m_rsi_fast_overbought"],
        )

        dates = pd.date_range("2024-01-01", periods=100, freq="5min")
        data = {
            "5m": pd.DataFrame(
                {
                    "open": np.random.uniform(100, 101, 100),
                    "high": np.random.uniform(101, 102, 100),
                    "low": np.random.uniform(99, 100, 100),
                    "close": np.random.uniform(100, 101, 100),
                    "volume": np.random.uniform(1000, 2000, 100),
                },
                index=dates,
            )
        }

        cache = FeatureCache(config, metadata)
        result = cache.compute_features(data)

        assert list(result.columns) == [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_overbought",
        ]

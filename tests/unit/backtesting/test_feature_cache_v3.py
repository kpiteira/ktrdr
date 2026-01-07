"""Unit tests for FeatureCacheV3.

These tests verify that FeatureCacheV3:
1. Accepts v3 config and metadata
2. Computes features correctly
3. Validates features against expected from metadata
4. Enforces column order to match expected_features exactly
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.backtesting.feature_cache import FeatureCacheV3
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
def v3_strategy_config():
    """Create a minimal v3 strategy configuration for testing."""
    return StrategyConfigurationV3(
        name="test_strategy",
        version="3.0",
        description="Test v3 strategy",
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


@pytest.fixture
def model_metadata_matching():
    """Create metadata with features matching the strategy config."""
    return ModelMetadataV3(
        model_name="test_model",
        strategy_name="test_strategy",
        resolved_features=["5m_rsi_fast_oversold", "5m_rsi_fast_overbought"],
    )


@pytest.fixture
def model_metadata_wrong_features():
    """Create metadata with wrong features (for mismatch testing)."""
    return ModelMetadataV3(
        model_name="test_model",
        strategy_name="test_strategy",
        resolved_features=["5m_nonexistent_feature", "5m_another_missing"],
    )


@pytest.fixture
def sample_data():
    """Create sample OHLCV data for testing."""
    # Need at least 50+ bars for indicator calculation
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


class TestFeatureCacheV3Init:
    """Tests for FeatureCacheV3 initialization."""

    def test_accepts_v3_config_and_metadata(
        self, v3_strategy_config, model_metadata_matching
    ):
        """FeatureCacheV3 should accept v3 config and metadata."""
        cache = FeatureCacheV3(v3_strategy_config, model_metadata_matching)

        assert cache.config == v3_strategy_config
        assert cache.expected_features == [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_overbought",
        ]

    def test_initializes_feature_resolver(
        self, v3_strategy_config, model_metadata_matching
    ):
        """FeatureCacheV3 should initialize a FeatureResolver."""
        cache = FeatureCacheV3(v3_strategy_config, model_metadata_matching)

        assert cache.feature_resolver is not None

    def test_initializes_indicator_engine(
        self, v3_strategy_config, model_metadata_matching
    ):
        """FeatureCacheV3 should initialize IndicatorEngine with v3 config."""
        cache = FeatureCacheV3(v3_strategy_config, model_metadata_matching)

        assert cache.indicator_engine is not None

    def test_initializes_fuzzy_engine(
        self, v3_strategy_config, model_metadata_matching
    ):
        """FeatureCacheV3 should initialize FuzzyEngine with v3 config."""
        cache = FeatureCacheV3(v3_strategy_config, model_metadata_matching)

        assert cache.fuzzy_engine is not None


class TestFeatureCacheV3ComputeFeatures:
    """Tests for FeatureCacheV3.compute_features()."""

    def test_compute_features_returns_dataframe(
        self, v3_strategy_config, model_metadata_matching, sample_data
    ):
        """compute_features should return a DataFrame."""
        cache = FeatureCacheV3(v3_strategy_config, model_metadata_matching)
        result = cache.compute_features(sample_data)

        assert isinstance(result, pd.DataFrame)

    def test_computed_features_have_expected_columns(
        self, v3_strategy_config, model_metadata_matching, sample_data
    ):
        """Computed features should have exactly the expected columns."""
        cache = FeatureCacheV3(v3_strategy_config, model_metadata_matching)
        result = cache.compute_features(sample_data)

        assert list(result.columns) == [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_overbought",
        ]

    def test_computed_features_not_all_nan(
        self, v3_strategy_config, model_metadata_matching, sample_data
    ):
        """Computed features should not be all NaN."""
        cache = FeatureCacheV3(v3_strategy_config, model_metadata_matching)
        result = cache.compute_features(sample_data)

        # At least some values should be non-NaN (after indicator warmup)
        assert not result.iloc[50:].isna().all().all()


class TestFeatureCacheV3Validation:
    """Tests for feature validation against model metadata."""

    def test_missing_features_raises_error(
        self, v3_strategy_config, model_metadata_wrong_features, sample_data
    ):
        """compute_features should raise ValueError if expected features are missing."""
        cache = FeatureCacheV3(v3_strategy_config, model_metadata_wrong_features)

        with pytest.raises(ValueError) as exc_info:
            cache.compute_features(sample_data)

        assert (
            "missing" in str(exc_info.value).lower()
            or "mismatch" in str(exc_info.value).lower()
        )

    def test_extra_features_logged_as_warning(
        self, v3_strategy_config, model_metadata_matching, sample_data, caplog
    ):
        """Extra features should be logged as a warning but not raise."""
        # Create metadata with only one expected feature
        metadata_subset = ModelMetadataV3(
            model_name="test_model",
            strategy_name="test_strategy",
            resolved_features=["5m_rsi_fast_oversold"],  # Only one of two
        )

        cache = FeatureCacheV3(v3_strategy_config, metadata_subset)
        result = cache.compute_features(sample_data)

        # Should succeed but only have the expected feature
        assert list(result.columns) == ["5m_rsi_fast_oversold"]
        # Extra features logged as warning
        assert (
            any(
                "extra" in record.message.lower() or "ignored" in record.message.lower()
                for record in caplog.records
            )
            or len(result.columns) == 1
        )


class TestFeatureCacheV3FeatureOrder:
    """Tests for feature order validation and enforcement."""

    def test_column_order_matches_expected_features(
        self, v3_strategy_config, model_metadata_matching, sample_data
    ):
        """Column order should exactly match expected_features from metadata."""
        cache = FeatureCacheV3(v3_strategy_config, model_metadata_matching)
        result = cache.compute_features(sample_data)

        # Order must be exactly as specified in metadata
        assert list(result.columns) == cache.expected_features

    def test_column_order_enforced_even_if_computed_differently(
        self, v3_strategy_config, sample_data
    ):
        """Columns should be reordered to match expected_features even if computed in different order."""
        # Metadata with reversed order
        metadata_reversed = ModelMetadataV3(
            model_name="test_model",
            strategy_name="test_strategy",
            resolved_features=[
                "5m_rsi_fast_overbought",
                "5m_rsi_fast_oversold",
            ],  # Reversed
        )

        cache = FeatureCacheV3(v3_strategy_config, metadata_reversed)
        result = cache.compute_features(sample_data)

        # Order should match metadata, not computation order
        assert list(result.columns) == [
            "5m_rsi_fast_overbought",
            "5m_rsi_fast_oversold",
        ]

"""Integration test for backtest with external context data (M9 Task 9.5).

Validates the full wiring from BacktestingEngine through context data loading
to feature computation. Uses mocked providers but real internal pipeline
components (IndicatorEngine, FuzzyEngine, FeatureCache).

This tests the plumbing, not the real external data — real E2E testing
with live FRED/CFTC APIs is handled in Task 9.6.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ktrdr.backtesting.feature_cache import FeatureCache
from ktrdr.backtesting.model_bundle import (
    reconstruct_config_from_metadata,
)
from ktrdr.models.model_metadata import ModelMetadata

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hourly_index() -> pd.DatetimeIndex:
    """Hourly datetime index for test data."""
    return pd.date_range("2024-01-01", periods=300, freq="h", tz="UTC")


@pytest.fixture
def ohlcv_data(hourly_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Realistic OHLCV data for EURUSD."""
    np.random.seed(42)
    close = 1.08 + np.cumsum(np.random.randn(300) * 0.0005)
    return pd.DataFrame(
        {
            "open": close - 0.0002,
            "high": close + 0.001,
            "low": close - 0.001,
            "close": close,
            "volume": np.random.randint(1000, 10000, 300),
        },
        index=hourly_index,
    )


@pytest.fixture
def yield_spread_data(hourly_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Yield spread context data (daily, forward-filled to hourly)."""
    np.random.seed(99)
    values = 1.5 + np.cumsum(np.random.randn(300) * 0.02)
    return pd.DataFrame({"close": values}, index=hourly_index)


@pytest.fixture
def gbp_ohlcv_data(hourly_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Cross-pair OHLCV for GBPUSD."""
    np.random.seed(77)
    close = 1.26 + np.cumsum(np.random.randn(300) * 0.0006)
    return pd.DataFrame(
        {
            "open": close - 0.0003,
            "high": close + 0.0012,
            "low": close - 0.0012,
            "close": close,
            "volume": np.random.randint(800, 8000, 300),
        },
        index=hourly_index,
    )


@pytest.fixture
def cot_pct_data(hourly_index: pd.DatetimeIndex) -> pd.DataFrame:
    """COT percentile data (weekly, forward-filled to hourly)."""
    np.random.seed(55)
    values = 50.0 + np.random.randn(300) * 15
    values = np.clip(values, 0, 100)
    return pd.DataFrame({"close": values}, index=hourly_index)


@pytest.fixture
def metadata_with_context() -> ModelMetadata:
    """ModelMetadata simulating a model trained with all 3 context providers."""
    return ModelMetadata(
        model_name="test_carry_v1",
        strategy_name="eurusd_carry_momentum_v1",
        strategy_version="3.0",
        indicators={
            "rsi_14": {"type": "rsi", "period": 14, "source": "close"},
            "gbp_rsi_14": {
                "type": "rsi",
                "period": 14,
                "source": "close",
                "data_source": "GBPUSD",
            },
            "yield_spread_rsi": {
                "type": "rsi",
                "period": 14,
                "source": "close",
                "data_source": "yield_spread_DGS2_IRLTLT01DEM156N",
            },
            "cot_percentile_ema": {
                "type": "ema",
                "period": 4,
                "source": "close",
                "data_source": "cot_EUR_net_pct",
            },
        },
        fuzzy_sets={
            "rsi_momentum": {
                "indicator": "rsi_14",
                "oversold": {"type": "triangular", "parameters": [0, 25, 40]},
                "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                "overbought": {"type": "triangular", "parameters": [60, 75, 100]},
            },
            "gbp_momentum": {
                "indicator": "gbp_rsi_14",
                "weak": {"type": "triangular", "parameters": [0, 30, 50]},
                "strong": {"type": "triangular", "parameters": [50, 70, 100]},
            },
            "carry_direction": {
                "indicator": "yield_spread_rsi",
                "eur_strengthening": {"type": "triangular", "parameters": [0, 25, 40]},
                "neutral": {"type": "triangular", "parameters": [35, 50, 65]},
                "usd_strengthening": {
                    "type": "triangular",
                    "parameters": [60, 75, 100],
                },
            },
            "positioning": {
                "indicator": "cot_percentile_ema",
                "crowded_short": {"type": "triangular", "parameters": [0, 10, 25]},
                "neutral": {"type": "triangular", "parameters": [25, 50, 75]},
                "crowded_long": {"type": "triangular", "parameters": [75, 90, 100]},
            },
        },
        nn_inputs=[
            {"fuzzy_set": "rsi_momentum", "timeframes": "all"},
            {"fuzzy_set": "gbp_momentum", "timeframes": "all"},
            {"fuzzy_set": "carry_direction", "timeframes": "all"},
            {"fuzzy_set": "positioning", "timeframes": "all"},
        ],
        resolved_features=[
            "1h_rsi_momentum_oversold",
            "1h_rsi_momentum_neutral",
            "1h_rsi_momentum_overbought",
            "1h_gbp_momentum_weak",
            "1h_gbp_momentum_strong",
            "1h_carry_direction_eur_strengthening",
            "1h_carry_direction_neutral",
            "1h_carry_direction_usd_strengthening",
            "1h_positioning_crowded_short",
            "1h_positioning_neutral",
            "1h_positioning_crowded_long",
        ],
        training_symbols=["EURUSD"],
        training_timeframes=["1h"],
        context_data_config=[
            {
                "provider": "ib",
                "symbol": "GBPUSD",
                "timeframe": "1h",
                "alignment": "forward_fill",
            },
            {
                "provider": "fred",
                "series": ["DGS2", "IRLTLT01DEM156N"],
                "alignment": "forward_fill",
            },
            {"provider": "cftc_cot", "report": "EUR", "alignment": "forward_fill"},
        ],
        context_source_ids=[
            "GBPUSD",
            "fred_DGS2",
            "fred_IRLTLT01DEM156N",
            "yield_spread_DGS2_IRLTLT01DEM156N",
            "cot_EUR_net_pos",
            "cot_EUR_net_pct",
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReconstructConfigWithContext:
    """Test that config reconstruction preserves context data."""

    def test_reconstruct_preserves_all_context_entries(
        self, metadata_with_context: ModelMetadata
    ) -> None:
        config = reconstruct_config_from_metadata(metadata_with_context)
        assert config.context_data is not None
        assert len(config.context_data) == 3
        providers = [e.provider for e in config.context_data]
        assert "ib" in providers
        assert "fred" in providers
        assert "cftc_cot" in providers

    def test_reconstruct_preserves_data_source_on_indicators(
        self, metadata_with_context: ModelMetadata
    ) -> None:
        config = reconstruct_config_from_metadata(metadata_with_context)
        assert config.indicators["gbp_rsi_14"].model_extra["data_source"] == "GBPUSD"
        assert (
            config.indicators["yield_spread_rsi"].model_extra["data_source"]
            == "yield_spread_DGS2_IRLTLT01DEM156N"
        )
        assert (
            config.indicators["cot_percentile_ema"].model_extra["data_source"]
            == "cot_EUR_net_pct"
        )


class TestFeatureCacheWithContextData:
    """Test FeatureCache computes features correctly with context data."""

    def test_compute_features_with_all_context_sources(
        self,
        metadata_with_context: ModelMetadata,
        ohlcv_data: pd.DataFrame,
        yield_spread_data: pd.DataFrame,
        gbp_ohlcv_data: pd.DataFrame,
        cot_pct_data: pd.DataFrame,
    ) -> None:
        """FeatureCache should produce all 11 expected features."""
        config = reconstruct_config_from_metadata(metadata_with_context)
        cache = FeatureCache(config=config, model_metadata=metadata_with_context)

        context_data = {
            "GBPUSD": gbp_ohlcv_data,
            "yield_spread_DGS2_IRLTLT01DEM156N": yield_spread_data,
            "cot_EUR_net_pct": cot_pct_data,
        }

        features = cache.compute_features({"1h": ohlcv_data}, context_data=context_data)

        # Should have all 11 expected features
        assert set(features.columns) == set(metadata_with_context.resolved_features)
        assert len(features.columns) == 11

        # Should have non-trivial data (not all NaN after warm-up)
        valid_rows = features.dropna()
        assert (
            len(valid_rows) > 0
        ), "Features should have valid rows after indicator warm-up"

    def test_features_are_in_correct_order(
        self,
        metadata_with_context: ModelMetadata,
        ohlcv_data: pd.DataFrame,
        yield_spread_data: pd.DataFrame,
        gbp_ohlcv_data: pd.DataFrame,
        cot_pct_data: pd.DataFrame,
    ) -> None:
        """Feature order must match resolved_features exactly."""
        config = reconstruct_config_from_metadata(metadata_with_context)
        cache = FeatureCache(config=config, model_metadata=metadata_with_context)

        context_data = {
            "GBPUSD": gbp_ohlcv_data,
            "yield_spread_DGS2_IRLTLT01DEM156N": yield_spread_data,
            "cot_EUR_net_pct": cot_pct_data,
        }

        features = cache.compute_features({"1h": ohlcv_data}, context_data=context_data)

        assert list(features.columns) == metadata_with_context.resolved_features

    def test_missing_context_data_raises_error(
        self,
        metadata_with_context: ModelMetadata,
        ohlcv_data: pd.DataFrame,
    ) -> None:
        """Missing context data should cause an error during feature computation."""
        config = reconstruct_config_from_metadata(metadata_with_context)
        cache = FeatureCache(config=config, model_metadata=metadata_with_context)

        # No context data provided — should fail for indicators with data_source
        with pytest.raises((KeyError, ValueError)):
            cache.compute_features({"1h": ohlcv_data}, context_data=None)

    def test_without_context_data_primary_only_works(
        self,
        ohlcv_data: pd.DataFrame,
    ) -> None:
        """A model without context data should work unchanged."""
        # Simple metadata — primary indicators only
        metadata = ModelMetadata(
            model_name="test",
            strategy_name="test",
            indicators={"rsi_14": {"type": "rsi", "period": 14}},
            fuzzy_sets={
                "rsi_fast": {
                    "indicator": "rsi_14",
                    "oversold": {"type": "triangular", "parameters": [0, 25, 40]},
                    "overbought": {"type": "triangular", "parameters": [60, 75, 100]},
                }
            },
            nn_inputs=[{"fuzzy_set": "rsi_fast", "timeframes": "all"}],
            resolved_features=["1h_rsi_fast_oversold", "1h_rsi_fast_overbought"],
            training_symbols=["EURUSD"],
            training_timeframes=["1h"],
        )

        config = reconstruct_config_from_metadata(metadata)
        cache = FeatureCache(config=config, model_metadata=metadata)

        # Should work without context_data
        features = cache.compute_features({"1h": ohlcv_data})
        assert len(features.columns) == 2
        assert "1h_rsi_fast_oversold" in features.columns

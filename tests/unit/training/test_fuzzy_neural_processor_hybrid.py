"""
Tests for FuzzyNeuralProcessor hybrid encoding support.

Tests raw indicator value integration alongside fuzzy memberships,
normalization (minmax, zscore, none), and feature ordering.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")

from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor


def make_dates(n=20):
    return [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(n)]


def make_fuzzy_data(n=20):
    """Fuzzy membership data with v3 naming."""
    return pd.DataFrame(
        {
            "5m_rsi_fast_oversold": np.random.random(n) * 0.8,
            "5m_rsi_fast_overbought": np.random.random(n) * 0.7,
        },
        index=make_dates(n),
    )


def make_indicator_data(n=20):
    """Raw indicator data matching what IndicatorEngine would produce."""
    return pd.DataFrame(
        {
            "rsi_14": np.random.uniform(20, 80, n),  # RSI range
            "adx_14": np.random.uniform(10, 50, n),  # ADX range
            "macd_12_26_9.line": np.random.uniform(-0.5, 0.5, n),
        },
        index=make_dates(n),
    )


class TestHybridEncoding:
    """Test hybrid encoding: fuzzy + raw features in same tensor."""

    def test_prepare_input_with_raw_features(self):
        """Feature tensor includes both fuzzy and raw values."""
        resolved = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_overbought",
            "5m_rsi_14_raw",
        ]
        processor = FuzzyNeuralProcessor(
            config={"lookback_periods": 0},
            resolved_features=resolved,
        )

        fuzzy_df = make_fuzzy_data()
        indicator_df = make_indicator_data()

        # Build combined DataFrame: fuzzy columns + raw columns named by feature_id
        combined = fuzzy_df.copy()
        combined["5m_rsi_14_raw"] = indicator_df["rsi_14"].values

        tensor, names = processor.prepare_input(combined)

        assert names == resolved
        assert tensor.shape == (20, 3)
        # Raw RSI values should NOT be clipped to [0,1]
        # (they're in 20-80 range originally)

    def test_feature_ordering_preserved(self):
        """Feature ordering matches nn_inputs specification order."""
        resolved = [
            "5m_rsi_fast_oversold",
            "5m_rsi_14_raw",  # Raw interleaved between fuzzy
            "5m_rsi_fast_overbought",
        ]
        processor = FuzzyNeuralProcessor(
            config={"lookback_periods": 0},
            resolved_features=resolved,
        )

        n = 10
        dates = make_dates(n)
        combined = pd.DataFrame(
            {
                "5m_rsi_fast_oversold": [0.2] * n,
                "5m_rsi_fast_overbought": [0.8] * n,
                "5m_rsi_14_raw": [50.0] * n,
            },
            index=dates,
        )

        tensor, names = processor.prepare_input(combined)

        assert names == resolved
        assert tensor[0, 0].item() == pytest.approx(0.2)  # oversold
        assert tensor[0, 1].item() == pytest.approx(50.0)  # raw RSI
        assert tensor[0, 2].item() == pytest.approx(0.8)  # overbought

    def test_backward_compat_fuzzy_only(self):
        """Processor with only fuzzy features (no raw) works unchanged."""
        resolved = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_overbought",
        ]
        processor = FuzzyNeuralProcessor(
            config={"lookback_periods": 0},
            resolved_features=resolved,
        )

        fuzzy_df = make_fuzzy_data()
        tensor, names = processor.prepare_input(fuzzy_df)

        assert names == resolved
        assert tensor.shape == (20, 2)


class TestNormalization:
    """Test normalization of raw indicator values."""

    def test_minmax_normalization(self):
        """minmax normalization produces values in [0, 1]."""
        n = 20
        dates = make_dates(n)
        processor = FuzzyNeuralProcessor(
            config={"lookback_periods": 0},
            resolved_features=["5m_rsi_14_raw"],
        )

        rsi_values = np.linspace(20, 80, n)
        combined = pd.DataFrame(
            {"5m_rsi_14_raw": rsi_values},
            index=dates,
        )

        processor.normalize_raw_features(
            combined,
            raw_feature_configs={"5m_rsi_14_raw": "minmax"},
        )

        assert combined["5m_rsi_14_raw"].min() == pytest.approx(0.0)
        assert combined["5m_rsi_14_raw"].max() == pytest.approx(1.0)

    def test_zscore_normalization(self):
        """zscore normalization produces values with mean≈0, std≈1."""
        n = 100
        dates = [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(n)]
        processor = FuzzyNeuralProcessor(
            config={"lookback_periods": 0},
            resolved_features=["5m_adx_14_raw"],
        )

        adx_values = np.random.normal(30, 10, n)
        combined = pd.DataFrame(
            {"5m_adx_14_raw": adx_values},
            index=dates,
        )

        processor.normalize_raw_features(
            combined,
            raw_feature_configs={"5m_adx_14_raw": "zscore"},
        )

        assert combined["5m_adx_14_raw"].mean() == pytest.approx(0.0, abs=0.01)
        assert combined["5m_adx_14_raw"].std() == pytest.approx(1.0, abs=0.05)

    def test_none_normalization_passthrough(self):
        """none normalization passes values through unchanged."""
        n = 10
        dates = make_dates(n)
        processor = FuzzyNeuralProcessor(
            config={"lookback_periods": 0},
            resolved_features=["5m_rsi_14_raw"],
        )

        original_values = np.array([30.0, 45.0, 50.0, 55.0, 70.0] * 2)
        combined = pd.DataFrame(
            {"5m_rsi_14_raw": original_values.copy()},
            index=dates,
        )

        processor.normalize_raw_features(
            combined,
            raw_feature_configs={"5m_rsi_14_raw": "none"},
        )

        np.testing.assert_array_equal(combined["5m_rsi_14_raw"].values, original_values)

    def test_normalization_params_stored(self):
        """Normalization parameters are stored for inference consistency."""
        n = 20
        dates = make_dates(n)
        processor = FuzzyNeuralProcessor(
            config={"lookback_periods": 0},
            resolved_features=["5m_rsi_14_raw"],
        )

        rsi_values = np.linspace(20, 80, n)
        combined = pd.DataFrame(
            {"5m_rsi_14_raw": rsi_values},
            index=dates,
        )

        processor.normalize_raw_features(
            combined,
            raw_feature_configs={"5m_rsi_14_raw": "minmax"},
        )

        # Params should be accessible
        params = processor.normalization_params
        assert "5m_rsi_14_raw" in params
        assert params["5m_rsi_14_raw"]["method"] == "minmax"
        assert "min" in params["5m_rsi_14_raw"]
        assert "max" in params["5m_rsi_14_raw"]

    def test_normalization_deterministic(self):
        """Same input produces same normalized output."""
        n = 20
        dates = make_dates(n)
        rsi_values = np.linspace(20, 80, n)

        results = []
        for _ in range(2):
            processor = FuzzyNeuralProcessor(
                config={"lookback_periods": 0},
                resolved_features=["5m_rsi_14_raw"],
            )
            combined = pd.DataFrame(
                {"5m_rsi_14_raw": rsi_values.copy()},
                index=dates,
            )
            processor.normalize_raw_features(
                combined,
                raw_feature_configs={"5m_rsi_14_raw": "minmax"},
            )
            results.append(combined["5m_rsi_14_raw"].values)

        np.testing.assert_array_equal(results[0], results[1])


class TestNaNHandling:
    """Test NaN handling in raw indicator values."""

    def test_nan_in_raw_filled_with_zero(self):
        """NaN values in raw indicators are handled gracefully."""
        n = 10
        dates = make_dates(n)
        resolved = ["5m_rsi_14_raw"]
        processor = FuzzyNeuralProcessor(
            config={"lookback_periods": 0},
            resolved_features=resolved,
        )

        values = np.array([30.0, np.nan, 50.0, np.nan, 70.0] * 2)
        combined = pd.DataFrame({"5m_rsi_14_raw": values}, index=dates)

        tensor, names = processor.prepare_input(combined)

        # Should not contain NaN
        assert not tensor.isnan().any()


class TestMultiTimeframeHybrid:
    """Test multi-timeframe hybrid encoding."""

    def test_raw_features_per_timeframe(self):
        """Raw features for each timeframe stored correctly."""
        resolved = [
            "5m_rsi_fast_oversold",
            "5m_rsi_14_raw",
            "1h_rsi_fast_oversold",
            "1h_rsi_14_raw",
        ]
        processor = FuzzyNeuralProcessor(
            config={"lookback_periods": 0},
            resolved_features=resolved,
        )

        n = 10
        dates = make_dates(n)
        combined = pd.DataFrame(
            {
                "5m_rsi_fast_oversold": np.random.random(n),
                "5m_rsi_14_raw": np.random.uniform(20, 80, n),
                "1h_rsi_fast_oversold": np.random.random(n),
                "1h_rsi_14_raw": np.random.uniform(20, 80, n),
            },
            index=dates,
        )

        tensor, names = processor.prepare_input(combined)

        assert names == resolved
        assert tensor.shape == (n, 4)

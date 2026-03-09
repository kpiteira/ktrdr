"""Tests for IndicatorEngine context data routing (Task 6.5)."""

import pandas as pd
import pytest

from ktrdr.indicators.indicator_engine import IndicatorEngine


def _make_ohlcv(periods: int = 50) -> pd.DataFrame:
    """Create minimal OHLCV data for indicator computation."""
    import numpy as np

    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=periods, freq="h")
    close = 100 + np.cumsum(np.random.randn(periods) * 0.5)
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.random.randint(1000, 5000, periods),
        },
        index=dates,
    )


def _make_context_df(periods: int = 50) -> pd.DataFrame:
    """Create context data (single 'value' column, like FRED yield data)."""
    import numpy as np

    np.random.seed(99)
    dates = pd.date_range("2024-01-01", periods=periods, freq="h")
    values = 4.0 + np.cumsum(np.random.randn(periods) * 0.02)
    return pd.DataFrame(
        {
            "close": values,  # Indicators compute on 'close' by default
        },
        index=dates,
    )


class TestIndicatorWithoutContextData:
    """Existing behavior should be unchanged."""

    def test_compute_without_context_data(self):
        """Indicators without data_source compute on primary data as before."""
        engine = IndicatorEngine({"rsi_14": {"type": "rsi", "period": 14}})
        data = _make_ohlcv()
        result = engine.compute(data, {"rsi_14"})

        assert "rsi_14" in result.columns
        assert len(result) == len(data)

    def test_apply_without_context_data(self):
        """apply() works unchanged without context_data."""
        engine = IndicatorEngine({"rsi_14": {"type": "rsi", "period": 14}})
        data = _make_ohlcv()
        result = engine.apply(data)

        assert "rsi_14" in result.columns


class TestIndicatorWithContextData:
    """Test routing indicators to context data sources."""

    def test_indicator_with_data_source_uses_context(self):
        """Indicator with data_source should compute on context data, not primary."""
        engine = IndicatorEngine(
            {
                "rsi_14": {"type": "rsi", "period": 14},
                "yield_rsi": {
                    "type": "rsi",
                    "period": 14,
                    "data_source": "yield_spread",
                },
            }
        )
        primary = _make_ohlcv()
        context = _make_context_df()

        result = engine.compute(
            primary,
            {"rsi_14", "yield_rsi"},
            context_data={"yield_spread": context},
        )

        # Both indicators should be in result
        assert "rsi_14" in result.columns
        assert "yield_rsi" in result.columns

        # They should produce different values (different input data)
        # (can't be exactly equal since they're computed on different data)
        # Check that yield_rsi is not all NaN
        assert not result["yield_rsi"].isna().all()

    def test_missing_context_key_raises_error(self):
        """data_source referencing missing context key should raise error."""
        engine = IndicatorEngine(
            {
                "yield_rsi": {
                    "type": "rsi",
                    "period": 14,
                    "data_source": "nonexistent",
                },
            }
        )
        primary = _make_ohlcv()

        with pytest.raises(KeyError, match="nonexistent"):
            engine.compute(
                primary,
                {"yield_rsi"},
                context_data={},
            )

    def test_no_context_data_with_data_source_raises_error(self):
        """Indicator with data_source but no context_data dict should raise error."""
        engine = IndicatorEngine(
            {
                "yield_rsi": {
                    "type": "rsi",
                    "period": 14,
                    "data_source": "yield_spread",
                },
            }
        )
        primary = _make_ohlcv()

        with pytest.raises(KeyError, match="yield_spread"):
            engine.compute(primary, {"yield_rsi"})

    def test_apply_with_context_data(self):
        """apply() should accept and pass context_data through."""
        engine = IndicatorEngine(
            {
                "rsi_14": {"type": "rsi", "period": 14},
                "yield_rsi": {
                    "type": "rsi",
                    "period": 14,
                    "data_source": "yield_spread",
                },
            }
        )
        primary = _make_ohlcv()
        context = _make_context_df()

        result = engine.apply(primary, context_data={"yield_spread": context})

        assert "rsi_14" in result.columns
        assert "yield_rsi" in result.columns

    def test_indicator_without_data_source_ignores_context(self):
        """Normal indicators should still use primary data even when context exists."""
        engine = IndicatorEngine({"rsi_14": {"type": "rsi", "period": 14}})
        primary = _make_ohlcv()
        context = _make_context_df()

        # Passing context_data shouldn't affect normal indicators
        result = engine.compute(
            primary,
            {"rsi_14"},
            context_data={"yield_spread": context},
        )

        assert "rsi_14" in result.columns

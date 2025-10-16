"""
Unit tests for fuzzy engine input transform application.

Tests that the fuzzy engine correctly applies input transforms before fuzzification.
"""

import pandas as pd
import pytest

from ktrdr.errors import ProcessingError
from ktrdr.fuzzy.config import FuzzyConfig, FuzzySetConfigModel
from ktrdr.fuzzy.engine import FuzzyEngine


class TestFuzzyEngineWithTransforms:
    """Test FuzzyEngine transform application."""

    def test_fuzzify_with_identity_transform(self):
        """Test that identity transform returns values unchanged."""
        # Create config with identity transform (explicit)
        config = FuzzyConfig(
            {
                "rsi_14": FuzzySetConfigModel(
                    **{  # type: ignore[arg-type]
                        "input_transform": {"type": "identity"},
                        "oversold": {"type": "triangular", "parameters": [0, 20, 40]},
                        "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                    }
                )
            }
        )

        engine = FuzzyEngine(config)

        # Test with scalar
        rsi_value = 35.0
        result = engine.fuzzify("rsi_14", rsi_value)
        assert isinstance(result, dict)
        assert "rsi_14_oversold" in result
        assert "rsi_14_neutral" in result

        # Test with series
        rsi_series = pd.Series([20, 50, 70])
        result_df = engine.fuzzify("rsi_14", rsi_series)
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) == 3

    def test_fuzzify_with_no_transform_defaults_to_identity(self):
        """Test that missing transform defaults to identity (no transformation)."""
        # Create config WITHOUT input_transform (should default to identity)
        config = FuzzyConfig(
            {
                "rsi_14": FuzzySetConfigModel(
                    **{  # type: ignore[arg-type]
                        "oversold": {"type": "triangular", "parameters": [0, 20, 40]},
                        "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                    }
                )
            }
        )

        engine = FuzzyEngine(config)

        # Test that it works without transform
        rsi_value = 35.0
        result = engine.fuzzify("rsi_14", rsi_value)
        assert isinstance(result, dict)

    def test_fuzzify_with_price_ratio_transform_scalar(self):
        """Test price ratio transform with scalar values."""
        # Create config with price_ratio transform for SMA
        config = FuzzyConfig(
            {
                "sma_20": FuzzySetConfigModel(
                    **{  # type: ignore[arg-type]
                        "input_transform": {
                            "type": "price_ratio",
                            "reference": "close",
                        },
                        "below": {
                            "type": "triangular",
                            "parameters": [0.93, 0.97, 1.00],
                        },
                        "at_ma": {
                            "type": "triangular",
                            "parameters": [0.98, 1.00, 1.02],
                        },
                        "above": {
                            "type": "triangular",
                            "parameters": [1.00, 1.03, 1.07],
                        },
                    }
                )
            }
        )

        engine = FuzzyEngine(config)

        # SMA value: 100, Close price: 105 -> ratio = 105/100 = 1.05
        sma_value = 100.0
        context_data = pd.DataFrame({"close": [105.0]})

        result = engine.fuzzify("sma_20", sma_value, context_data=context_data)

        # The transform should convert 100 -> 1.05, which should have membership in "above"
        assert isinstance(result, dict)
        assert "sma_20_below" in result
        assert "sma_20_at_ma" in result
        assert "sma_20_above" in result

        # Ratio 1.05 is in "above" region (1.00-1.07)
        assert result["sma_20_above"] > 0.0

    def test_fuzzify_with_price_ratio_transform_series(self):
        """Test price ratio transform with series values."""
        # Create config with price_ratio transform for SMA
        config = FuzzyConfig(
            {
                "sma_20": FuzzySetConfigModel(
                    **{  # type: ignore[arg-type]
                        "input_transform": {
                            "type": "price_ratio",
                            "reference": "close",
                        },
                        "below": {
                            "type": "triangular",
                            "parameters": [0.93, 0.97, 1.00],
                        },
                        "at_ma": {
                            "type": "triangular",
                            "parameters": [0.98, 1.00, 1.02],
                        },
                        "above": {
                            "type": "triangular",
                            "parameters": [1.00, 1.03, 1.07],
                        },
                    }
                )
            }
        )

        engine = FuzzyEngine(config)

        # Test with series: SMA=[100, 100, 100], Close=[95, 100, 105]
        # Expected ratios: [0.95, 1.00, 1.05]
        sma_series = pd.Series([100.0, 100.0, 100.0])
        context_data = pd.DataFrame({"close": [95.0, 100.0, 105.0]})

        result = engine.fuzzify("sma_20", sma_series, context_data=context_data)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert "sma_20_below" in result.columns
        assert "sma_20_at_ma" in result.columns
        assert "sma_20_above" in result.columns

        # Check that different ratios get different memberships
        # Ratio 0.95 should be in "below" region
        assert result.loc[0, "sma_20_below"] > 0.0
        # Ratio 1.00 should be in "at_ma" region
        assert result.loc[1, "sma_20_at_ma"] > 0.0
        # Ratio 1.05 should be in "above" region
        assert result.loc[2, "sma_20_above"] > 0.0

    def test_fuzzify_requires_context_data_for_price_ratio(self):
        """Test that price_ratio transform requires context_data."""
        config = FuzzyConfig(
            {
                "sma_20": FuzzySetConfigModel(
                    **{  # type: ignore[arg-type]
                        "input_transform": {
                            "type": "price_ratio",
                            "reference": "close",
                        },
                        "below": {
                            "type": "triangular",
                            "parameters": [0.93, 0.97, 1.00],
                        },
                    }
                )
            }
        )

        engine = FuzzyEngine(config)

        # Should raise error when context_data is missing
        with pytest.raises(ProcessingError) as exc_info:
            engine.fuzzify("sma_20", 100.0)  # No context_data

        error = exc_info.value
        assert "context_data" in str(error).lower()

    def test_fuzzify_requires_reference_column_in_context_data(self):
        """Test that price_ratio transform validates reference column exists."""
        config = FuzzyConfig(
            {
                "sma_20": FuzzySetConfigModel(
                    **{  # type: ignore[arg-type]
                        "input_transform": {
                            "type": "price_ratio",
                            "reference": "close",
                        },
                        "below": {
                            "type": "triangular",
                            "parameters": [0.93, 0.97, 1.00],
                        },
                    }
                )
            }
        )

        engine = FuzzyEngine(config)

        # Context data missing 'close' column
        context_data = pd.DataFrame({"open": [100.0]})

        with pytest.raises(ProcessingError) as exc_info:
            engine.fuzzify("sma_20", 100.0, context_data=context_data)

        error = exc_info.value
        assert "close" in str(error).lower()

    def test_fuzzify_with_price_ratio_different_references(self):
        """Test price ratio transform with different reference columns."""
        for ref in ["open", "high", "low", "close"]:
            config = FuzzyConfig(
                {
                    "sma_20": FuzzySetConfigModel(
                        **{  # type: ignore[arg-type]
                            "input_transform": {
                                "type": "price_ratio",
                                "reference": ref,
                            },
                            "at_ma": {
                                "type": "triangular",
                                "parameters": [0.98, 1.00, 1.02],
                            },
                        }
                    )
                }
            )

            engine = FuzzyEngine(config)
            context_data = pd.DataFrame({ref: [100.0]})

            result = engine.fuzzify("sma_20", 100.0, context_data=context_data)
            assert isinstance(result, dict)
            # When price == SMA, ratio should be 1.0 (at MA)
            assert result["sma_20_at_ma"] == 1.0

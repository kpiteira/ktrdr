"""
Unit tests for training pipeline input transform support.

Tests that the training pipeline correctly passes context_data to the fuzzy engine
to enable input transforms for indicators like SMA/EMA.
"""

import pandas as pd

from ktrdr.training.training_pipeline import TrainingPipeline


class TestTrainingPipelineTransforms:
    """Test training pipeline with input transforms."""

    def test_generate_fuzzy_memberships_passes_context_data(self):
        """Test that fuzzy membership generation passes context_data."""
        # Create combined DataFrame with both price data and indicators
        # This simulates the output from combine_indicators()
        combined_data = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [102.0, 103.0, 104.0],
                "low": [99.0, 100.0, 101.0],
                "close": [101.0, 102.0, 103.0],
                "volume": [1000, 1100, 1200],
                "sma_20": [100.0, 101.0, 102.0],  # Indicator column
                "rsi_14": [50.0, 55.0, 60.0],  # Indicator column
            }
        )

        indicators = {"1d": combined_data}

        # Fuzzy config with price_ratio transform for SMA
        fuzzy_configs = {
            "sma_20": {
                "input_transform": {"type": "price_ratio", "reference": "close"},
                "below": {"type": "triangular", "parameters": [0.93, 0.97, 1.00]},
                "at_ma": {"type": "triangular", "parameters": [0.98, 1.00, 1.02]},
                "above": {"type": "triangular", "parameters": [1.00, 1.03, 1.07]},
            },
            "rsi_14": {
                "oversold": {"type": "triangular", "parameters": [0, 20, 40]},
                "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                "overbought": {"type": "triangular", "parameters": [60, 80, 100]},
            },
        }

        # Should not raise error - context_data should be passed internally
        result = TrainingPipeline.generate_fuzzy_memberships(indicators, fuzzy_configs)

        assert isinstance(result, dict)
        assert "1d" in result
        assert isinstance(result["1d"], pd.DataFrame)

        # Check that fuzzy membership columns exist
        result_df = result["1d"]
        assert "sma_20_below" in result_df.columns
        assert "sma_20_at_ma" in result_df.columns
        assert "sma_20_above" in result_df.columns
        assert "rsi_14_oversold" in result_df.columns
        assert "rsi_14_neutral" in result_df.columns
        assert "rsi_14_overbought" in result_df.columns

        # Verify SMA transformed correctly (close/sma ratios)
        # Row 0: close=101, sma=100 -> ratio=1.01 -> should be "at_ma" or "above"
        # Row 1: close=102, sma=101 -> ratio=1.0099 -> should be "at_ma"
        # Row 2: close=103, sma=102 -> ratio=1.0098 -> should be "at_ma"
        assert (
            result_df.loc[0, "sma_20_at_ma"] > 0 or result_df.loc[0, "sma_20_above"] > 0
        )
        assert result_df.loc[1, "sma_20_at_ma"] > 0
        assert result_df.loc[2, "sma_20_at_ma"] > 0

    def test_generate_fuzzy_memberships_with_multi_timeframe(self):
        """Test fuzzy membership generation with multiple timeframes."""
        # Create multi-timeframe data
        indicators = {
            "1d": pd.DataFrame(
                {
                    "close": [100.0, 101.0],
                    "sma_20": [99.0, 100.0],
                    "rsi_14": [50.0, 55.0],
                }
            ),
            "1h": pd.DataFrame(
                {
                    "close": [100.5, 100.8],
                    "sma_20": [100.0, 100.2],
                    "rsi_14": [52.0, 54.0],
                }
            ),
        }

        fuzzy_configs = {
            "sma_20": {
                "input_transform": {"type": "price_ratio", "reference": "close"},
                "at_ma": {"type": "triangular", "parameters": [0.98, 1.00, 1.02]},
            },
            "rsi_14": {
                "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
            },
        }

        result = TrainingPipeline.generate_fuzzy_memberships(indicators, fuzzy_configs)

        assert isinstance(result, dict)
        assert "1d" in result or "1h" in result  # At least one timeframe processed
        # Note: Multi-timeframe path may use different engine method

    def test_generate_fuzzy_memberships_without_transform(self):
        """Test that indicators without transforms still work (identity/default)."""
        combined_data = pd.DataFrame(
            {
                "close": [100.0, 101.0, 102.0],
                "rsi_14": [30.0, 50.0, 70.0],
            }
        )

        indicators = {"1d": combined_data}

        fuzzy_configs = {
            "rsi_14": {
                # No input_transform - should default to identity
                "oversold": {"type": "triangular", "parameters": [0, 20, 40]},
                "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                "overbought": {"type": "triangular", "parameters": [60, 80, 100]},
            }
        }

        result = TrainingPipeline.generate_fuzzy_memberships(indicators, fuzzy_configs)

        assert isinstance(result, dict)
        assert "1d" in result
        result_df = result["1d"]

        # Verify RSI processed correctly (no transformation)
        assert "rsi_14_oversold" in result_df.columns
        assert "rsi_14_neutral" in result_df.columns
        assert "rsi_14_overbought" in result_df.columns

        # Row 0: RSI=30 -> oversold region
        assert result_df.loc[0, "rsi_14_oversold"] > 0
        # Row 1: RSI=50 -> neutral region (peak)
        assert result_df.loc[1, "rsi_14_neutral"] == 1.0
        # Row 2: RSI=70 -> overbought region
        assert result_df.loc[2, "rsi_14_overbought"] > 0

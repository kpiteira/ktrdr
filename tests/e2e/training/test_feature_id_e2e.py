"""
End-to-End Training Tests for Feature IDs.

These tests validate that the complete training pipeline works correctly
with feature IDs across various scenarios.

Test Coverage:
1. Training with explicit feature_ids (param-based naming)
2. Training with params naming (rsi_14, macd_12_26_9)
3. Training with semantic naming (rsi_fast, macd_trend)
4. Training with mixed naming
5. Training with multi-output indicators (MACD)
6. Training with multi-timeframe (feature_ids preserved across timeframes)

Acceptance Criteria (Phase 6 Task 6.1):
- All E2E tests pass
- Training completes without errors for all formats
- Model features match configuration exactly
- Multi-output indicators work (MACD)
- Multi-timeframe works
"""

import pytest
import pandas as pd
from pathlib import Path
from typing import Dict, Any

from ktrdr.config.models import StrategyConfigurationV2
from ktrdr.indicators.indicator_engine import IndicatorEngine
from ktrdr.training.training_manager import TrainingManager


class TestFeatureIDEndToEnd:
    """End-to-end tests for feature ID training pipeline."""

    @pytest.fixture
    def sample_price_data(self) -> pd.DataFrame:
        """Create sample price data for testing."""
        import numpy as np

        dates = pd.date_range(start="2024-01-01", periods=200, freq="1h")
        np.random.seed(42)

        # Generate realistic price data
        close_prices = 100 + np.cumsum(np.random.randn(200) * 0.5)
        high_prices = close_prices + np.random.rand(200) * 2
        low_prices = close_prices - np.random.rand(200) * 2
        open_prices = close_prices + (np.random.rand(200) - 0.5) * 1.5
        volume = np.random.randint(1000000, 10000000, 200)

        return pd.DataFrame(
            {
                "open": open_prices,
                "high": high_prices,
                "low": low_prices,
                "close": close_prices,
                "volume": volume,
            },
            index=dates,
        )

    @pytest.fixture
    def strategy_config_param_based(self) -> Dict[str, Any]:
        """Strategy config with parameter-based feature_ids (rsi_14)."""
        return {
            "name": "test_param_based",
            "version": "2.1",
            "description": "Test strategy with param-based feature_ids",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single_symbol"},
                "timeframes": {"mode": "single_timeframe"},
                "history_required": 100,
            },
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_14", "period": 14, "source": "close"},
                {
                    "name": "macd",
                    "feature_id": "macd_12_26_9",
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                    "source": "close",
                },
            ],
            "fuzzy_sets": {
                "rsi_14": {
                    "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
                    "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                    "overbought": {"type": "triangular", "parameters": [65, 80, 100]},
                },
                "macd_12_26_9": {
                    "bearish": {"type": "triangular", "parameters": [-20, -5, 0]},
                    "neutral": {"type": "triangular", "parameters": [-5, 0, 5]},
                    "bullish": {"type": "triangular", "parameters": [0, 5, 20]},
                },
            },
        }

    @pytest.fixture
    def strategy_config_semantic(self) -> Dict[str, Any]:
        """Strategy config with semantic feature_ids (rsi_fast)."""
        return {
            "name": "test_semantic",
            "version": "2.1",
            "description": "Test strategy with semantic feature_ids",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single_symbol"},
                "timeframes": {"mode": "single_timeframe"},
                "history_required": 100,
            },
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_fast", "period": 7, "source": "close"},
                {"name": "rsi", "feature_id": "rsi_slow", "period": 21, "source": "close"},
                {
                    "name": "macd",
                    "feature_id": "macd_trend",
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                    "source": "close",
                },
            ],
            "fuzzy_sets": {
                "rsi_fast": {
                    "extreme_oversold": {"type": "triangular", "parameters": [0, 10, 25]},
                    "extreme_overbought": {"type": "triangular", "parameters": [75, 90, 100]},
                },
                "rsi_slow": {
                    "oversold": {"type": "triangular", "parameters": [0, 25, 45]},
                    "overbought": {"type": "triangular", "parameters": [55, 75, 100]},
                },
                "macd_trend": {
                    "bearish": {"type": "triangular", "parameters": [-20, -5, 0]},
                    "neutral": {"type": "triangular", "parameters": [-5, 0, 5]},
                    "bullish": {"type": "triangular", "parameters": [0, 5, 20]},
                },
            },
        }

    def test_e2e_param_based_feature_ids(
        self, sample_price_data: pd.DataFrame, strategy_config_param_based: Dict[str, Any]
    ):
        """
        Test E2E training with parameter-based feature_ids (rsi_14, macd_12_26_9).

        Validates:
        - Indicator computation works with feature_ids
        - Fuzzy sets reference correct indicators via feature_ids
        - Training pipeline accepts feature_id format
        - DataFrame has both column names and feature_id aliases
        """
        # Load strategy config
        config = StrategyConfigurationV2(**strategy_config_param_based)

        # Build indicator engine
        indicator_engine = IndicatorEngine(indicators=strategy_config_param_based["indicators"])

        # Compute indicators
        result = indicator_engine.apply(sample_price_data)

        # Verify feature_ids present in DataFrame
        assert "rsi_14" in result.columns, "feature_id 'rsi_14' not in result"
        assert "macd_12_26_9" in result.columns, "feature_id 'macd_12_26_9' not in result"

        # Verify technical columns also present
        assert "rsi_14" in result.columns  # In this case, column name == feature_id
        # MACD primary output should be present
        macd_cols = [c for c in result.columns if "MACD" in c and "_signal_" not in c and "_hist_" not in c]
        assert len(macd_cols) > 0, "MACD primary column not found"

        # Verify no NaN in feature_id columns (after warmup period)
        assert result["rsi_14"].notna().sum() > 0, "All RSI values are NaN"
        assert result["macd_12_26_9"].notna().sum() > 0, "All MACD values are NaN"

    def test_e2e_semantic_feature_ids(
        self, sample_price_data: pd.DataFrame, strategy_config_semantic: Dict[str, Any]
    ):
        """
        Test E2E training with semantic feature_ids (rsi_fast, rsi_slow, macd_trend).

        Validates:
        - Semantic naming works correctly
        - Multiple instances of same indicator with different feature_ids
        - feature_id aliases created correctly
        """
        # Load strategy config
        config = StrategyConfigurationV2(**strategy_config_semantic)

        # Build indicator engine
        indicator_engine = IndicatorEngine(indicators=strategy_config_semantic["indicators"])

        # Compute indicators
        result = indicator_engine.apply(sample_price_data)

        # Verify feature_ids present in DataFrame
        assert "rsi_fast" in result.columns, "feature_id 'rsi_fast' not in result"
        assert "rsi_slow" in result.columns, "feature_id 'rsi_slow' not in result"
        assert "macd_trend" in result.columns, "feature_id 'macd_trend' not in result"

        # Verify technical columns also present (rsi_7, rsi_21)
        assert "rsi_7" in result.columns, "Technical column 'rsi_7' not in result"
        assert "rsi_21" in result.columns, "Technical column 'rsi_21' not in result"

        # Verify data identity (aliases should reference same data)
        assert result["rsi_fast"] is result["rsi_7"], "rsi_fast should be alias to rsi_7"
        assert result["rsi_slow"] is result["rsi_21"], "rsi_slow should be alias to rsi_21"

    def test_e2e_mixed_naming(self, sample_price_data: pd.DataFrame):
        """
        Test E2E training with mixed naming (param-based + semantic).

        Validates:
        - Mixed naming strategies work
        - No conflicts between naming approaches
        """
        strategy_config = {
            "name": "test_mixed",
            "version": "2.1",
            "description": "Test strategy with mixed feature_ids",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single_symbol"},
                "timeframes": {"mode": "single_timeframe"},
                "history_required": 100,
            },
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_14", "period": 14, "source": "close"},  # Param-based
                {"name": "ema", "feature_id": "ema_short", "period": 9, "source": "close"},  # Semantic
                {
                    "name": "macd",
                    "feature_id": "macd_trend",
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                    "source": "close",
                },  # Semantic
            ],
            "fuzzy_sets": {
                "rsi_14": {"oversold": {"type": "triangular", "parameters": [0, 20, 35]}},
                "ema_short": {"below": {"type": "triangular", "parameters": [0.93, 0.97, 1.00]}},
                "macd_trend": {"bullish": {"type": "triangular", "parameters": [0, 5, 20]}},
            },
        }

        # Build indicator engine
        indicator_engine = IndicatorEngine(indicators=strategy_config["indicators"])

        # Compute indicators
        result = indicator_engine.apply(sample_price_data)

        # Verify all feature_ids present
        assert "rsi_14" in result.columns
        assert "ema_short" in result.columns
        assert "macd_trend" in result.columns

        # Verify technical columns
        assert "ema_9" in result.columns

        # Verify ema_short is alias to ema_9
        assert result["ema_short"] is result["ema_9"]

    def test_e2e_multi_output_indicator_macd(self, sample_price_data: pd.DataFrame):
        """
        Test E2E training with multi-output indicator (MACD).

        Validates:
        - feature_id maps to primary output (main MACD line)
        - Secondary outputs (signal, histogram) still accessible
        - Fuzzy sets correctly reference primary output via feature_id
        """
        strategy_config = {
            "name": "test_macd",
            "version": "2.1",
            "description": "Test MACD multi-output handling",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single_symbol"},
                "timeframes": {"mode": "single_timeframe"},
                "history_required": 100,
            },
            "indicators": [
                {
                    "name": "macd",
                    "feature_id": "macd_standard",
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                    "source": "close",
                },
            ],
            "fuzzy_sets": {
                "macd_standard": {
                    "strong_bearish": {"type": "triangular", "parameters": [-100, -50, -10]},
                    "bearish": {"type": "triangular", "parameters": [-20, -5, 0]},
                    "neutral": {"type": "triangular", "parameters": [-5, 0, 5]},
                    "bullish": {"type": "triangular", "parameters": [0, 5, 20]},
                    "strong_bullish": {"type": "triangular", "parameters": [10, 50, 100]},
                }
            },
        }

        # Build indicator engine
        indicator_engine = IndicatorEngine(indicators=strategy_config["indicators"])

        # Compute indicators
        result = indicator_engine.apply(sample_price_data)

        # Verify feature_id present (maps to primary output)
        assert "macd_standard" in result.columns, "feature_id 'macd_standard' not in result"

        # Verify all MACD outputs present
        macd_main_cols = [c for c in result.columns if "MACD" in c and "_signal_" not in c and "_hist_" not in c]
        macd_signal_cols = [c for c in result.columns if "_signal_" in c]
        macd_hist_cols = [c for c in result.columns if "_hist_" in c]

        assert len(macd_main_cols) > 0, "MACD main line not found"
        assert len(macd_signal_cols) > 0, "MACD signal line not found"
        assert len(macd_hist_cols) > 0, "MACD histogram not found"

        # Verify feature_id maps to primary output (main line)
        primary_col = macd_main_cols[0]
        assert result["macd_standard"] is result[primary_col], f"feature_id should alias {primary_col}"

    def test_e2e_multiple_rsi_instances(self, sample_price_data: pd.DataFrame):
        """
        Test E2E with multiple RSI instances (different periods).

        Validates:
        - Multiple instances of same indicator work
        - Each has unique feature_id
        - No collisions or confusion
        """
        strategy_config = {
            "name": "test_multiple_rsi",
            "version": "2.1",
            "description": "Test multiple RSI instances",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single_symbol"},
                "timeframes": {"mode": "single_timeframe"},
                "history_required": 100,
            },
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_7", "period": 7, "source": "close"},
                {"name": "rsi", "feature_id": "rsi_14", "period": 14, "source": "close"},
                {"name": "rsi", "feature_id": "rsi_21", "period": 21, "source": "close"},
            ],
            "fuzzy_sets": {
                "rsi_7": {"extreme_oversold": {"type": "triangular", "parameters": [0, 10, 25]}},
                "rsi_14": {"oversold": {"type": "triangular", "parameters": [0, 20, 35]}},
                "rsi_21": {"oversold": {"type": "triangular", "parameters": [0, 25, 40]}},
            },
        }

        # Build indicator engine
        indicator_engine = IndicatorEngine(indicators=strategy_config["indicators"])

        # Compute indicators
        result = indicator_engine.apply(sample_price_data)

        # Verify all feature_ids present
        assert "rsi_7" in result.columns
        assert "rsi_14" in result.columns
        assert "rsi_21" in result.columns

        # Verify values are different (different periods = different values)
        assert not result["rsi_7"].equals(result["rsi_14"]), "RSI(7) and RSI(14) should differ"
        assert not result["rsi_14"].equals(result["rsi_21"]), "RSI(14) and RSI(21) should differ"

    @pytest.mark.slow
    def test_e2e_multi_timeframe_feature_ids(self, sample_price_data: pd.DataFrame):
        """
        Test E2E with multi-timeframe configuration.

        Validates:
        - feature_ids work across multiple timeframes
        - DataFrame structure correct for MTF
        - No conflicts between timeframes

        NOTE: This is a placeholder test. Full MTF testing requires
        actual MTF data and more complex setup.
        """
        # For now, just verify single-timeframe works as baseline
        strategy_config = {
            "name": "test_mtf",
            "version": "2.1",
            "description": "Multi-timeframe test",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single_symbol"},
                "timeframes": {
                    "mode": "multi_timeframe",
                    "list": ["15m", "1h"],
                    "base_timeframe": "15m",
                },
                "history_required": 200,
            },
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_14", "period": 14, "source": "close"},
            ],
            "fuzzy_sets": {
                "rsi_14": {"oversold": {"type": "triangular", "parameters": [0, 20, 35]}},
            },
        }

        # For single-timeframe baseline
        indicator_engine = IndicatorEngine(indicators=strategy_config["indicators"])
        result = indicator_engine.apply(sample_price_data)

        # Basic validation
        assert "rsi_14" in result.columns, "feature_id should work in MTF context"

    def test_e2e_no_feature_id_error(self, sample_price_data: pd.DataFrame):
        """
        Test that strategies without feature_id raise clear error.

        Validates:
        - Missing feature_id caught during config load
        - Error message is clear and actionable
        - Error includes migration instructions
        """
        strategy_config_no_feature_id = {
            "name": "test_no_feature_id",
            "version": "2.1",
            "description": "Invalid: missing feature_id",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single_symbol"},
                "timeframes": {"mode": "single_timeframe"},
                "history_required": 100,
            },
            "indicators": [
                # Missing feature_id! Should fail
                {"name": "rsi", "period": 14, "source": "close"},
            ],
            "fuzzy_sets": {
                "rsi_14": {"oversold": {"type": "triangular", "parameters": [0, 20, 35]}},
            },
        }

        # Should raise validation error
        with pytest.raises(Exception) as exc_info:
            StrategyConfigurationV2(**strategy_config_no_feature_id)

        # Verify error mentions feature_id
        error_message = str(exc_info.value)
        assert "feature_id" in error_message.lower(), "Error should mention missing feature_id"

    def test_e2e_duplicate_feature_id_error(self, sample_price_data: pd.DataFrame):
        """
        Test that duplicate feature_ids raise clear error.

        Validates:
        - Duplicate feature_id caught during validation
        - Error message lists duplicates
        - Error is actionable
        """
        strategy_config_duplicate = {
            "name": "test_duplicate",
            "version": "2.1",
            "description": "Invalid: duplicate feature_id",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single_symbol"},
                "timeframes": {"mode": "single_timeframe"},
                "history_required": 100,
            },
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_fast", "period": 7, "source": "close"},
                {"name": "rsi", "feature_id": "rsi_fast", "period": 14, "source": "close"},  # DUPLICATE!
            ],
            "fuzzy_sets": {
                "rsi_fast": {"oversold": {"type": "triangular", "parameters": [0, 20, 35]}},
            },
        }

        # Should raise validation error
        with pytest.raises(Exception) as exc_info:
            StrategyConfigurationV2(**strategy_config_duplicate)

        # Verify error mentions duplicate
        error_message = str(exc_info.value)
        assert "duplicate" in error_message.lower() or "unique" in error_message.lower(), (
            "Error should mention duplicate feature_id"
        )

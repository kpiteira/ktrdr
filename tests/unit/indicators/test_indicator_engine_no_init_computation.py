"""
Unit tests verifying IndicatorEngine does NOT compute indicators during initialization.

This module tests that Phase 7 eliminates ALL computation on sample data during
IndicatorEngine initialization by using class methods instead.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ktrdr.indicators.indicator_engine import IndicatorEngine


class TestNoInitComputation:
    """Test that IndicatorEngine initialization performs NO indicator computation."""

    def test_single_output_indicator_no_computation(self):
        """Test single-output indicator (RSI) - NO compute() during init."""
        configs = [{"name": "rsi", "feature_id": "rsi_14", "period": 14}]

        # Mock compute to track if it's called
        with patch("ktrdr.indicators.rsi_indicator.RSIIndicator.compute") as mock_compute:
            _engine = IndicatorEngine(indicators=configs)

            # compute() should NEVER be called during __init__
            mock_compute.assert_not_called()

    def test_multi_output_indicator_no_computation(self):
        """Test multi-output indicator (MACD) - NO compute() during init."""
        configs = [{"name": "macd", "feature_id": "macd_std"}]

        with patch("ktrdr.indicators.macd_indicator.MACDIndicator.compute") as mock_compute:
            _engine = IndicatorEngine(indicators=configs)

            # compute() should NEVER be called during __init__
            mock_compute.assert_not_called()

    def test_multiple_indicators_no_computation(self):
        """Test multiple indicators - NO compute() calls during init."""
        configs = [
            {"name": "rsi", "feature_id": "rsi_14", "period": 14},
            {"name": "macd", "feature_id": "macd_std"},
            {"name": "sma", "feature_id": "sma_20", "period": 20},
            {"name": "ema", "feature_id": "ema_10", "period": 10},
        ]

        # Mock all indicator compute methods
        with patch("ktrdr.indicators.rsi_indicator.RSIIndicator.compute") as mock_rsi, patch(
            "ktrdr.indicators.macd_indicator.MACDIndicator.compute"
        ) as mock_macd, patch(
            "ktrdr.indicators.ma_indicators.SimpleMovingAverage.compute"
        ) as mock_sma, patch(
            "ktrdr.indicators.ma_indicators.ExponentialMovingAverage.compute"
        ) as mock_ema:
            _engine = IndicatorEngine(indicators=configs)

            # NONE of the compute() methods should be called
            mock_rsi.assert_not_called()
            mock_macd.assert_not_called()
            mock_sma.assert_not_called()
            mock_ema.assert_not_called()

    def test_feature_id_map_built_correctly_without_computation(self):
        """Test feature_id_map is correctly built WITHOUT any computation."""
        configs = [
            {"name": "rsi", "feature_id": "rsi_14", "period": 14},
            {"name": "macd", "feature_id": "macd_std"},
        ]

        # Mock compute to ensure it's not called
        with patch("ktrdr.indicators.base_indicator.BaseIndicator.compute") as mock_compute:
            engine = IndicatorEngine(indicators=configs)

            # Verify feature_id_map is correctly built
            # RSI: single-output -> maps column name to feature_id
            assert "rsi_14" in engine.feature_id_map
            assert engine.feature_id_map["rsi_14"] == "rsi_14"

            # MACD: multi-output -> maps primary column to feature_id
            # Primary column should be "MACD_12_26" (uppercase, no suffix)
            assert "MACD_12_26" in engine.feature_id_map
            assert engine.feature_id_map["MACD_12_26"] == "macd_std"

            # Verify compute was NEVER called
            mock_compute.assert_not_called()

    def test_class_methods_used_not_computation(self):
        """Test that class methods are used instead of computation."""
        configs = [{"name": "macd", "feature_id": "macd_std"}]

        # Mock the class methods to track calls
        with patch(
            "ktrdr.indicators.macd_indicator.MACDIndicator.is_multi_output", return_value=True
        ) as mock_is_multi, patch(
            "ktrdr.indicators.macd_indicator.MACDIndicator.get_primary_output_suffix",
            return_value=None,
        ) as mock_get_suffix, patch(
            "ktrdr.indicators.macd_indicator.MACDIndicator.compute"
        ) as mock_compute:
            engine = IndicatorEngine(indicators=configs)

            # Class methods SHOULD be called
            assert mock_is_multi.called
            # Note: get_primary_output_suffix might be called depending on implementation

            # But compute() should NEVER be called
            mock_compute.assert_not_called()

            # Verify feature_id_map was still built correctly
            assert len(engine.feature_id_map) > 0

    def test_initialization_performance_without_computation(self):
        """Test that initialization is fast without computation."""
        import time

        # Strategy with 10 indicator instances
        configs = [
            {"name": "rsi", "feature_id": f"rsi_{i}", "period": 14} for i in range(10)
        ]

        # Measure initialization time
        start = time.time()
        _engine = IndicatorEngine(indicators=configs)
        elapsed = time.time() - start

        # Without computation, init should be very fast (< 0.1s even on slow systems)
        # This is a reasonable threshold - creating 10 indicator instances
        # and building feature_id_map should be near-instantaneous
        assert elapsed < 0.1, f"Initialization took {elapsed:.3f}s - too slow, likely computing!"

    def test_no_sample_dataframe_creation(self):
        """Test that NO sample DataFrames are created during init."""
        configs = [
            {"name": "rsi", "feature_id": "rsi_14", "period": 14},
            {"name": "macd", "feature_id": "macd_std"},
        ]

        # Mock DataFrame constructor to track calls
        original_dataframe_init = pd.DataFrame.__init__

        dataframe_calls = []

        def track_dataframe_init(self, *args, **kwargs):
            dataframe_calls.append((args, kwargs))
            return original_dataframe_init(self, *args, **kwargs)

        with patch.object(pd.DataFrame, "__init__", track_dataframe_init):
            _engine = IndicatorEngine(indicators=configs)

            # Check that no 100-row sample DataFrames were created
            # (the old code created DataFrames with 100 rows of sample data)
            for args, kwargs in dataframe_calls:
                if args and isinstance(args[0], dict):
                    # Check if this looks like sample OHLCV data
                    data_dict = args[0]
                    if "open" in data_dict and "close" in data_dict:
                        # Check if it's a 100-row sample (old behavior)
                        if isinstance(data_dict["open"], list) and len(data_dict["open"]) == 100:
                            pytest.fail(
                                "Found 100-row sample DataFrame creation during init! "
                                "This indicates computation is still happening."
                            )


class TestComputeStillWorks:
    """Verify that compute() still works correctly during apply()."""

    def test_compute_called_during_apply(self):
        """Test that compute() IS called during apply() (as it should be)."""
        configs = [{"name": "rsi", "feature_id": "rsi_14", "period": 14}]

        sample_data = pd.DataFrame(
            {
                "open": [100.0] * 100,
                "high": [101.0] * 100,
                "low": [99.0] * 100,
                "close": [100.0] * 100,
                "volume": [1000] * 100,
            }
        )

        engine = IndicatorEngine(indicators=configs)

        # Mock compute to track if it's called during apply()
        with patch("ktrdr.indicators.rsi_indicator.RSIIndicator.compute") as mock_compute:
            # Set up mock to return valid Series
            mock_compute.return_value = pd.Series([50.0] * 100, name="rsi_14")

            _result = engine.apply(sample_data)

            # compute() SHOULD be called during apply()
            mock_compute.assert_called_once()

    def test_indicators_work_correctly_after_init_changes(self):
        """Test that indicators produce correct output after Phase 7 changes."""
        configs = [
            {"name": "rsi", "feature_id": "rsi_14", "period": 14},
            {"name": "macd", "feature_id": "macd_std"},
        ]

        sample_data = pd.DataFrame(
            {
                "open": [100.0 + i for i in range(100)],
                "high": [101.0 + i for i in range(100)],
                "low": [99.0 + i for i in range(100)],
                "close": [100.0 + i for i in range(100)],
                "volume": [1000] * 100,
            }
        )

        engine = IndicatorEngine(indicators=configs)
        result = engine.apply(sample_data)

        # Verify RSI column exists (technical name)
        assert "rsi_14" in result.columns

        # Verify MACD technical columns exist
        assert "MACD_12_26" in result.columns
        assert "MACD_signal_12_26_9" in result.columns
        assert "MACD_hist_12_26_9" in result.columns

        # Verify feature_id alias exists for MACD
        assert "macd_std" in result.columns  # feature_id alias for primary column

        # Verify the alias has the same values as the technical column
        pd.testing.assert_series_equal(
            result["MACD_12_26"],
            result["macd_std"],
            check_names=False
        )

"""
Unit tests verifying IndicatorEngine does NOT compute indicators during initialization.

This module tests that Phase 7 eliminates ALL computation on sample data during
IndicatorEngine initialization by using class methods instead.

Updated for v3 format - uses dict-based indicator configs.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from ktrdr.config.models import IndicatorDefinition
from ktrdr.indicators.indicator_engine import IndicatorEngine


class TestNoInitComputation:
    """Test that IndicatorEngine initialization performs NO indicator computation."""

    def test_single_output_indicator_no_computation(self):
        """Test single-output indicator (RSI) - NO compute() during init."""
        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}

        # Mock compute to track if it's called
        with patch(
            "ktrdr.indicators.rsi_indicator.RSIIndicator.compute"
        ) as mock_compute:
            _engine = IndicatorEngine(indicators=indicators)

            # compute() should NEVER be called during __init__
            mock_compute.assert_not_called()

    def test_multi_output_indicator_no_computation(self):
        """Test multi-output indicator (MACD) - NO compute() during init."""
        indicators = {
            "macd_std": IndicatorDefinition(
                type="macd", fast_period=12, slow_period=26, signal_period=9
            )
        }

        with patch(
            "ktrdr.indicators.macd_indicator.MACDIndicator.compute"
        ) as mock_compute:
            _engine = IndicatorEngine(indicators=indicators)

            # compute() should NEVER be called during __init__
            mock_compute.assert_not_called()

    def test_multiple_indicators_no_computation(self):
        """Test multiple indicators - NO compute() calls during init."""
        indicators = {
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "macd_std": IndicatorDefinition(
                type="macd", fast_period=12, slow_period=26, signal_period=9
            ),
            "sma_20": IndicatorDefinition(type="sma", period=20),
            "ema_10": IndicatorDefinition(type="ema", period=10),
        }

        # Mock all indicator compute methods
        with (
            patch("ktrdr.indicators.rsi_indicator.RSIIndicator.compute") as mock_rsi,
            patch("ktrdr.indicators.macd_indicator.MACDIndicator.compute") as mock_macd,
            patch(
                "ktrdr.indicators.ma_indicators.SimpleMovingAverage.compute"
            ) as mock_sma,
            patch(
                "ktrdr.indicators.ma_indicators.ExponentialMovingAverage.compute"
            ) as mock_ema,
        ):
            _engine = IndicatorEngine(indicators=indicators)

            # NONE of the compute() methods should be called
            mock_rsi.assert_not_called()
            mock_macd.assert_not_called()
            mock_sma.assert_not_called()
            mock_ema.assert_not_called()

    def test_indicators_dict_built_without_computation(self):
        """Test _indicators dict is correctly built WITHOUT any computation."""
        indicators = {
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "macd_std": IndicatorDefinition(
                type="macd", fast_period=12, slow_period=26, signal_period=9
            ),
        }

        # Mock compute to ensure it's not called
        with patch(
            "ktrdr.indicators.base_indicator.BaseIndicator.compute"
        ) as mock_compute:
            engine = IndicatorEngine(indicators=indicators)

            # Verify _indicators dict is correctly built
            assert "rsi_14" in engine._indicators
            assert "macd_std" in engine._indicators

            # Verify compute was NEVER called
            mock_compute.assert_not_called()

    def test_indicator_instances_created_not_computation(self):
        """Test that indicator instances are created without computation."""
        from ktrdr.indicators.macd_indicator import MACDIndicator

        indicators = {
            "macd_std": IndicatorDefinition(
                type="macd", fast_period=12, slow_period=26, signal_period=9
            )
        }

        # Mock compute to track if it's called
        with patch(
            "ktrdr.indicators.macd_indicator.MACDIndicator.compute"
        ) as mock_compute:
            engine = IndicatorEngine(indicators=indicators)

            # compute() should NEVER be called during init
            mock_compute.assert_not_called()

            # Verify _indicators was built correctly with actual instance
            assert len(engine._indicators) > 0
            assert "macd_std" in engine._indicators
            assert isinstance(engine._indicators["macd_std"], MACDIndicator)

    def test_initialization_performance_without_computation(self):
        """Test that initialization is fast without computation."""
        import time

        # Strategy with 10 indicator instances
        indicators = {
            f"rsi_{i}": IndicatorDefinition(type="rsi", period=14) for i in range(10)
        }

        # Measure initialization time
        start = time.time()
        _engine = IndicatorEngine(indicators=indicators)
        elapsed = time.time() - start

        # Without computation, init should be very fast (< 0.1s even on slow systems)
        # This is a reasonable threshold - creating 10 indicator instances
        # should be near-instantaneous
        assert (
            elapsed < 0.1
        ), f"Initialization took {elapsed:.3f}s - too slow, likely computing!"

    def test_no_sample_dataframe_creation(self):
        """Test that NO sample DataFrames are created during init."""
        indicators = {
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "macd_std": IndicatorDefinition(
                type="macd", fast_period=12, slow_period=26, signal_period=9
            ),
        }

        # Mock DataFrame constructor to track calls
        original_dataframe_init = pd.DataFrame.__init__

        dataframe_calls = []

        def track_dataframe_init(self, *args, **kwargs):
            dataframe_calls.append((args, kwargs))
            return original_dataframe_init(self, *args, **kwargs)

        with patch.object(pd.DataFrame, "__init__", track_dataframe_init):
            _engine = IndicatorEngine(indicators=indicators)

            # Check that no 100-row sample DataFrames were created
            # (the old code created DataFrames with 100 rows of sample data)
            for args, _kwargs in dataframe_calls:
                if args and isinstance(args[0], dict):
                    # Check if this looks like sample OHLCV data
                    data_dict = args[0]
                    if "open" in data_dict and "close" in data_dict:
                        # Check if it's a 100-row sample (old behavior)
                        if (
                            isinstance(data_dict["open"], list)
                            and len(data_dict["open"]) == 100
                        ):
                            pytest.fail(
                                "Found 100-row sample DataFrame creation during init! "
                                "This indicates computation is still happening."
                            )


class TestComputeStillWorks:
    """Verify that compute() still works correctly during compute()/compute_for_timeframe()."""

    def test_compute_called_during_compute_method(self):
        """Test that indicator compute() IS called during engine.compute() (as it should be)."""
        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}

        sample_data = pd.DataFrame(
            {
                "open": [100.0] * 100,
                "high": [101.0] * 100,
                "low": [99.0] * 100,
                "close": [100.0] * 100,
                "volume": [1000] * 100,
            }
        )

        engine = IndicatorEngine(indicators=indicators)

        # Mock compute to track if it's called during engine.compute()
        with patch(
            "ktrdr.indicators.rsi_indicator.RSIIndicator.compute"
        ) as mock_compute:
            # Set up mock to return valid Series
            mock_compute.return_value = pd.Series([50.0] * 100, name="rsi_14")

            _result = engine.compute(sample_data, {"rsi_14"})

            # compute() SHOULD be called during engine.compute()
            mock_compute.assert_called_once()

    def test_indicators_work_correctly_after_init_changes(self):
        """Test that indicators produce correct output after Phase 7 changes."""
        indicators = {
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "macd_std": IndicatorDefinition(
                type="macd", fast_period=12, slow_period=26, signal_period=9
            ),
        }

        sample_data = pd.DataFrame(
            {
                "open": [100.0 + i for i in range(100)],
                "high": [101.0 + i for i in range(100)],
                "low": [99.0 + i for i in range(100)],
                "close": [100.0 + i for i in range(100)],
                "volume": [1000] * 100,
            }
        )

        engine = IndicatorEngine(indicators=indicators)
        result = engine.compute(sample_data, {"rsi_14", "macd_std"})

        # Verify RSI column exists
        assert "rsi_14" in result.columns

        # V3: Verify MACD semantic columns exist (engine-prefixed)
        assert "macd_std.line" in result.columns
        assert "macd_std.signal" in result.columns
        assert "macd_std.histogram" in result.columns

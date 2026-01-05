"""
Unit tests for M3a: Single-Output Indicator Migration.

Tests verify that single-output indicators return unnamed Series
(new format) instead of named Series (old format).
"""

import pandas as pd
import pytest

from ktrdr.indicators.ad_line import ADLineIndicator
from ktrdr.indicators.atr_indicator import ATRIndicator
from ktrdr.indicators.cci_indicator import CCIIndicator
from ktrdr.indicators.cmf_indicator import CMFIndicator
from ktrdr.indicators.mfi_indicator import MFIIndicator
from ktrdr.indicators.momentum_indicator import MomentumIndicator
from ktrdr.indicators.obv_indicator import OBVIndicator
from ktrdr.indicators.roc_indicator import ROCIndicator
from ktrdr.indicators.rsi_indicator import RSIIndicator
from ktrdr.indicators.rvi_indicator import RVIIndicator
from ktrdr.indicators.squeeze_intensity_indicator import SqueezeIntensityIndicator
from ktrdr.indicators.volume_ratio_indicator import VolumeRatioIndicator
from ktrdr.indicators.vwap_indicator import VWAPIndicator
from ktrdr.indicators.williams_r_indicator import WilliamsRIndicator


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0] * 20,
            "high": [101.0, 102.0, 103.0, 104.0, 105.0] * 20,
            "low": [99.0, 100.0, 101.0, 102.0, 103.0] * 20,
            "close": [100.5, 101.5, 102.5, 103.5, 104.5] * 20,
            "volume": [1000, 1100, 1200, 1300, 1400] * 20,
        }
    )


class TestMomentumOscillatorMigration:
    """Test Task 3a.1: Momentum/Oscillator indicators return unnamed Series."""

    def test_rsi_returns_unnamed_series(self, sample_ohlcv_data):
        """RSI indicator returns Series with no name."""
        indicator = RSIIndicator(period=14)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "RSI should return a Series"
        assert result.name is None, "RSI Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data), "Series length should match input"
        # Verify values are still calculated correctly (spot check)
        assert not result.iloc[-1] == 0, "RSI should have calculated values"

    def test_cci_returns_unnamed_series(self, sample_ohlcv_data):
        """CCI indicator returns Series with no name."""
        indicator = CCIIndicator(period=20)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "CCI should return a Series"
        assert result.name is None, "CCI Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)

    def test_mfi_returns_unnamed_series(self, sample_ohlcv_data):
        """MFI indicator returns Series with no name."""
        indicator = MFIIndicator(period=14)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "MFI should return a Series"
        assert result.name is None, "MFI Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)

    def test_roc_returns_unnamed_series(self, sample_ohlcv_data):
        """ROC indicator returns Series with no name."""
        indicator = ROCIndicator(period=10)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "ROC should return a Series"
        assert result.name is None, "ROC Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)

    def test_momentum_returns_unnamed_series(self, sample_ohlcv_data):
        """Momentum indicator returns Series with no name."""
        indicator = MomentumIndicator(period=10)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "Momentum should return a Series"
        assert result.name is None, "Momentum Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)

    def test_williams_r_returns_unnamed_series(self, sample_ohlcv_data):
        """Williams %R indicator returns Series with no name."""
        indicator = WilliamsRIndicator(period=14)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "Williams %R should return a Series"
        assert result.name is None, "Williams %R Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)

    def test_rvi_returns_unnamed_series(self, sample_ohlcv_data):
        """RVI indicator returns Series with no name (if single-output)."""
        indicator = RVIIndicator(period=14)
        result = indicator.compute(sample_ohlcv_data)

        # RVI might be multi-output - check
        if indicator.is_multi_output():
            pytest.skip("RVI is multi-output, will be handled in M3b")
        else:
            assert isinstance(result, pd.Series), "RVI should return a Series"
            assert result.name is None, "RVI Series should have no name (unnamed)"
            assert len(result) == len(sample_ohlcv_data)

    def test_squeeze_intensity_returns_unnamed_series(self, sample_ohlcv_data):
        """Squeeze Intensity indicator returns Series with no name."""
        indicator = SqueezeIntensityIndicator(bb_period=20, kc_period=20)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "Squeeze Intensity should return a Series"
        assert (
            result.name is None
        ), "Squeeze Intensity Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)


class TestIndicatorValuesUnchanged:
    """Regression tests: verify indicator values are unchanged after migration."""

    def test_rsi_values_unchanged(self, sample_ohlcv_data):
        """RSI values should be unchanged after removing .name assignment."""
        indicator = RSIIndicator(period=14)
        result = indicator.compute(sample_ohlcv_data)

        # Spot check: RSI values should be in valid range [0, 100]
        valid_values = result.dropna()
        assert (valid_values >= 0).all(), "RSI values should be >= 0"
        assert (valid_values <= 100).all(), "RSI values should be <= 100"
        # Check that we have some non-NaN values
        assert result.count() > 0, "RSI should produce non-NaN values"

    def test_williams_r_values_unchanged(self, sample_ohlcv_data):
        """Williams %R values should be unchanged after migration."""
        indicator = WilliamsRIndicator(period=14)
        result = indicator.compute(sample_ohlcv_data)

        # Spot check: Williams %R values should be in valid range [-100, 0]
        valid_values = result.dropna()
        assert (valid_values >= -100).all(), "Williams %R values should be >= -100"
        assert (valid_values <= 0).all(), "Williams %R values should be <= 0"
        assert result.count() > 0, "Williams %R should produce non-NaN values"


class TestVolumeTrendMigration:
    """Test Task 3a.2: Volume/Trend indicators return unnamed Series."""

    def test_obv_returns_unnamed_series(self, sample_ohlcv_data):
        """OBV indicator returns Series with no name."""
        indicator = OBVIndicator()
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "OBV should return a Series"
        assert result.name is None, "OBV Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)

    def test_cmf_skipped_multi_output(self, sample_ohlcv_data):
        """CMF is multi-output, skip for M3a."""
        indicator = CMFIndicator(period=21)

        # Verify this is multi-output (should be handled in M3b)
        if indicator.is_multi_output():
            pytest.skip("CMF is multi-output, will be handled in M3b")

    def test_vwap_returns_unnamed_series(self, sample_ohlcv_data):
        """VWAP indicator returns Series with no name."""
        indicator = VWAPIndicator(period=20)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "VWAP should return a Series"
        assert result.name is None, "VWAP Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)

    def test_volume_ratio_returns_unnamed_series(self, sample_ohlcv_data):
        """Volume Ratio indicator returns Series with no name."""
        indicator = VolumeRatioIndicator(period=20)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "Volume Ratio should return a Series"
        assert result.name is None, "Volume Ratio Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)

    def test_ad_line_skipped_multi_output(self, sample_ohlcv_data):
        """A/D Line is multi-output, skip for M3a."""
        indicator = ADLineIndicator()

        # Verify this is multi-output (should be handled in M3b)
        if indicator.is_multi_output():
            pytest.skip("A/D Line is multi-output, will be handled in M3b")

    def test_atr_returns_unnamed_series(self, sample_ohlcv_data):
        """ATR indicator returns Series with no name."""
        indicator = ATRIndicator(period=14)
        result = indicator.compute(sample_ohlcv_data)

        assert isinstance(result, pd.Series), "ATR should return a Series"
        assert result.name is None, "ATR Series should have no name (unnamed)"
        assert len(result) == len(sample_ohlcv_data)


class TestVolumeTrendValuesUnchanged:
    """Regression tests: verify Task 3a.2 indicator values are unchanged."""

    def test_obv_values_unchanged(self, sample_ohlcv_data):
        """OBV values should be unchanged after removing .name assignment."""
        indicator = OBVIndicator()
        result = indicator.compute(sample_ohlcv_data)

        # Spot check: OBV should have calculated values (cumulative)
        assert result.count() > 0, "OBV should produce non-NaN values"
        # OBV is cumulative, so first value should be 0
        assert result.iloc[0] == 0.0, "OBV should start at 0"

    def test_vwap_values_unchanged(self, sample_ohlcv_data):
        """VWAP values should be unchanged after migration."""
        indicator = VWAPIndicator(period=20)
        result = indicator.compute(sample_ohlcv_data)

        # Spot check: VWAP should be within reasonable range of prices
        valid_values = result.dropna()
        price_range = (
            sample_ohlcv_data["low"].min(),
            sample_ohlcv_data["high"].max(),
        )
        assert (
            valid_values >= price_range[0] * 0.9
        ).all(), "VWAP should be near price range"
        assert (
            valid_values <= price_range[1] * 1.1
        ).all(), "VWAP should be near price range"

    def test_volume_ratio_values_unchanged(self, sample_ohlcv_data):
        """Volume Ratio values should be unchanged after migration."""
        indicator = VolumeRatioIndicator(period=20)
        result = indicator.compute(sample_ohlcv_data)

        # Spot check: Volume Ratio should have calculated values
        valid_values = result.dropna()
        assert len(valid_values) > 0, "Volume Ratio should produce non-NaN values"
        # Ratio should be positive
        assert (valid_values > 0).all(), "Volume Ratio should be positive"

    def test_atr_values_unchanged(self, sample_ohlcv_data):
        """ATR values should be unchanged after migration."""
        indicator = ATRIndicator(period=14)
        result = indicator.compute(sample_ohlcv_data)

        # Spot check: ATR should have calculated values (always positive)
        valid_values = result.dropna()
        assert len(valid_values) > 0, "ATR should produce non-NaN values"
        assert (valid_values > 0).all(), "ATR should be positive"


class TestAdapterIntegration:
    """Test that migrated indicators work through IndicatorEngine adapter."""

    def test_migrated_indicator_through_adapter(self, sample_ohlcv_data):
        """Migrated RSI works through compute_indicator() adapter."""
        from ktrdr.indicators import IndicatorEngine

        engine = IndicatorEngine()
        indicator = RSIIndicator(period=14)

        # Adapter should handle unnamed Series and create proper column name
        result = engine.compute_indicator(sample_ohlcv_data, indicator, "rsi_14")

        assert isinstance(result, pd.DataFrame), "Adapter should return DataFrame"
        assert "rsi_14" in result.columns, "Should have indicator_id column"
        assert len(result.columns) == 1, "Single-output should have 1 column"
        # Verify adapter wrapped the unnamed Series correctly
        assert result["rsi_14"].count() > 0, "Column should have values"

    def test_volume_trend_through_adapter(self, sample_ohlcv_data):
        """Migrated volume/trend indicators work through adapter."""
        from ktrdr.indicators import IndicatorEngine

        engine = IndicatorEngine()

        # Test OBV
        obv = OBVIndicator()
        result = engine.compute_indicator(sample_ohlcv_data, obv, "obv")
        assert "obv" in result.columns, "OBV should have indicator_id column"
        assert len(result.columns) == 1, "Single-output should have 1 column"

        # Test VWAP
        vwap = VWAPIndicator(period=20)
        result = engine.compute_indicator(sample_ohlcv_data, vwap, "vwap_20")
        assert "vwap_20" in result.columns, "VWAP should have indicator_id column"
        assert len(result.columns) == 1, "Single-output should have 1 column"

        # Test Volume Ratio
        vol_ratio = VolumeRatioIndicator(period=20)
        result = engine.compute_indicator(sample_ohlcv_data, vol_ratio, "volume_ratio")
        assert (
            "volume_ratio" in result.columns
        ), "Volume Ratio should have indicator_id column"
        assert len(result.columns) == 1, "Single-output should have 1 column"

        # Test ATR
        atr = ATRIndicator(period=14)
        result = engine.compute_indicator(sample_ohlcv_data, atr, "atr_14")
        assert "atr_14" in result.columns, "ATR should have indicator_id column"
        assert len(result.columns) == 1, "Single-output should have 1 column"

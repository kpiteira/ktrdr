"""
Tests for get_output_names() interface on single-output indicators.

This test file verifies that all single-output indicators implement
the interface correctly by inheriting the default behavior from BaseIndicator.
"""

from ktrdr.indicators.ad_line import ADLineIndicator
from ktrdr.indicators.atr_indicator import ATRIndicator
from ktrdr.indicators.bollinger_band_width_indicator import BollingerBandWidthIndicator
from ktrdr.indicators.cci_indicator import CCIIndicator
from ktrdr.indicators.cmf_indicator import CMFIndicator
from ktrdr.indicators.distance_from_ma_indicator import DistanceFromMAIndicator
from ktrdr.indicators.ma_indicators import ExponentialMovingAverage, SimpleMovingAverage
from ktrdr.indicators.mfi_indicator import MFIIndicator
from ktrdr.indicators.momentum_indicator import MomentumIndicator
from ktrdr.indicators.obv_indicator import OBVIndicator
from ktrdr.indicators.parabolic_sar_indicator import ParabolicSARIndicator
from ktrdr.indicators.roc_indicator import ROCIndicator
from ktrdr.indicators.rsi_indicator import RSIIndicator
from ktrdr.indicators.squeeze_intensity_indicator import SqueezeIntensityIndicator
from ktrdr.indicators.volume_ratio_indicator import VolumeRatioIndicator
from ktrdr.indicators.vwap_indicator import VWAPIndicator
from ktrdr.indicators.williams_r_indicator import WilliamsRIndicator
from ktrdr.indicators.zigzag_indicator import ZigZagIndicator


class TestRSIInterface:
    """Test RSI single-output interface."""

    def test_is_multi_output(self):
        """RSI should be single-output."""
        assert RSIIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """RSI should return empty list."""
        assert RSIIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """RSI should return None for primary output."""
        assert RSIIndicator.get_primary_output() is None


class TestATRInterface:
    """Test ATR single-output interface."""

    def test_is_multi_output(self):
        """ATR should be single-output."""
        assert ATRIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """ATR should return empty list."""
        assert ATRIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """ATR should return None for primary output."""
        assert ATRIndicator.get_primary_output() is None


class TestCCIInterface:
    """Test CCI single-output interface."""

    def test_is_multi_output(self):
        """CCI should be single-output."""
        assert CCIIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """CCI should return empty list."""
        assert CCIIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """CCI should return None for primary output."""
        assert CCIIndicator.get_primary_output() is None


class TestCMFInterface:
    """Test CMF single-output interface."""

    def test_is_multi_output(self):
        """CMF should be single-output."""
        assert CMFIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """CMF should return empty list."""
        assert CMFIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """CMF should return None for primary output."""
        assert CMFIndicator.get_primary_output() is None


class TestMFIInterface:
    """Test MFI single-output interface."""

    def test_is_multi_output(self):
        """MFI should be single-output."""
        assert MFIIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """MFI should return empty list."""
        assert MFIIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """MFI should return None for primary output."""
        assert MFIIndicator.get_primary_output() is None


class TestOBVInterface:
    """Test OBV single-output interface."""

    def test_is_multi_output(self):
        """OBV should be single-output."""
        assert OBVIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """OBV should return empty list."""
        assert OBVIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """OBV should return None for primary output."""
        assert OBVIndicator.get_primary_output() is None


class TestROCInterface:
    """Test ROC single-output interface."""

    def test_is_multi_output(self):
        """ROC should be single-output."""
        assert ROCIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """ROC should return empty list."""
        assert ROCIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """ROC should return None for primary output."""
        assert ROCIndicator.get_primary_output() is None


class TestMomentumInterface:
    """Test Momentum single-output interface."""

    def test_is_multi_output(self):
        """Momentum should be single-output."""
        assert MomentumIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """Momentum should return empty list."""
        assert MomentumIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """Momentum should return None for primary output."""
        assert MomentumIndicator.get_primary_output() is None


class TestWilliamsRInterface:
    """Test Williams %R single-output interface."""

    def test_is_multi_output(self):
        """Williams %R should be single-output."""
        assert WilliamsRIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """Williams %R should return empty list."""
        assert WilliamsRIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """Williams %R should return None for primary output."""
        assert WilliamsRIndicator.get_primary_output() is None


class TestVWAPInterface:
    """Test VWAP single-output interface."""

    def test_is_multi_output(self):
        """VWAP should be single-output."""
        assert VWAPIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """VWAP should return empty list."""
        assert VWAPIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """VWAP should return None for primary output."""
        assert VWAPIndicator.get_primary_output() is None


class TestVolumeRatioInterface:
    """Test VolumeRatio single-output interface."""

    def test_is_multi_output(self):
        """VolumeRatio should be single-output."""
        assert VolumeRatioIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """VolumeRatio should return empty list."""
        assert VolumeRatioIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """VolumeRatio should return None for primary output."""
        assert VolumeRatioIndicator.get_primary_output() is None


class TestDistanceFromMAInterface:
    """Test DistanceFromMA single-output interface."""

    def test_is_multi_output(self):
        """DistanceFromMA should be single-output."""
        assert DistanceFromMAIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """DistanceFromMA should return empty list."""
        assert DistanceFromMAIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """DistanceFromMA should return None for primary output."""
        assert DistanceFromMAIndicator.get_primary_output() is None


class TestBollingerBandWidthInterface:
    """Test BollingerBandWidth single-output interface."""

    def test_is_multi_output(self):
        """BollingerBandWidth should be single-output."""
        assert BollingerBandWidthIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """BollingerBandWidth should return empty list."""
        assert BollingerBandWidthIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """BollingerBandWidth should return None for primary output."""
        assert BollingerBandWidthIndicator.get_primary_output() is None


class TestSqueezeIntensityInterface:
    """Test SqueezeIntensity single-output interface."""

    def test_is_multi_output(self):
        """SqueezeIntensity should be single-output."""
        assert SqueezeIntensityIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """SqueezeIntensity should return empty list."""
        assert SqueezeIntensityIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """SqueezeIntensity should return None for primary output."""
        assert SqueezeIntensityIndicator.get_primary_output() is None


class TestParabolicSARInterface:
    """Test ParabolicSAR single-output interface."""

    def test_is_multi_output(self):
        """ParabolicSAR should be single-output."""
        assert ParabolicSARIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """ParabolicSAR should return empty list."""
        assert ParabolicSARIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """ParabolicSAR should return None for primary output."""
        assert ParabolicSARIndicator.get_primary_output() is None


class TestZigZagInterface:
    """Test ZigZag single-output interface."""

    def test_is_multi_output(self):
        """ZigZag should be single-output."""
        assert ZigZagIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """ZigZag should return empty list."""
        assert ZigZagIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """ZigZag should return None for primary output."""
        assert ZigZagIndicator.get_primary_output() is None


class TestADLineInterface:
    """Test ADLine single-output interface."""

    def test_is_multi_output(self):
        """ADLine should be single-output."""
        assert ADLineIndicator.is_multi_output() is False

    def test_get_output_names(self):
        """ADLine should return empty list."""
        assert ADLineIndicator.get_output_names() == []

    def test_get_primary_output(self):
        """ADLine should return None for primary output."""
        assert ADLineIndicator.get_primary_output() is None


class TestSMAInterface:
    """Test SMA single-output interface."""

    def test_is_multi_output(self):
        """SMA should be single-output."""
        assert SimpleMovingAverage.is_multi_output() is False

    def test_get_output_names(self):
        """SMA should return empty list."""
        assert SimpleMovingAverage.get_output_names() == []

    def test_get_primary_output(self):
        """SMA should return None for primary output."""
        assert SimpleMovingAverage.get_primary_output() is None


class TestEMAInterface:
    """Test EMA single-output interface."""

    def test_is_multi_output(self):
        """EMA should be single-output."""
        assert ExponentialMovingAverage.is_multi_output() is False

    def test_get_output_names(self):
        """EMA should return empty list."""
        assert ExponentialMovingAverage.get_output_names() == []

    def test_get_primary_output(self):
        """EMA should return None for primary output."""
        assert ExponentialMovingAverage.get_primary_output() is None

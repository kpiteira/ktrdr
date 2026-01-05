"""
Tests for get_output_names() interface on multi-output indicators.

This test file verifies that all multi-output indicators implement
get_output_names() correctly according to the M1 interface standard.
"""

from ktrdr.indicators.ad_line import ADLineIndicator
from ktrdr.indicators.adx_indicator import ADXIndicator
from ktrdr.indicators.aroon_indicator import AroonIndicator
from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator
from ktrdr.indicators.cmf_indicator import CMFIndicator
from ktrdr.indicators.donchian_channels import DonchianChannelsIndicator
from ktrdr.indicators.fisher_transform import FisherTransformIndicator
from ktrdr.indicators.ichimoku_indicator import IchimokuIndicator
from ktrdr.indicators.keltner_channels import KeltnerChannelsIndicator
from ktrdr.indicators.macd_indicator import MACDIndicator
from ktrdr.indicators.rvi_indicator import RVIIndicator
from ktrdr.indicators.stochastic_indicator import StochasticIndicator
from ktrdr.indicators.supertrend_indicator import SuperTrendIndicator


class TestBollingerBandsInterface:
    """Test BollingerBands get_output_names() interface."""

    def test_get_output_names(self):
        """BollingerBands should return ['upper', 'middle', 'lower']."""
        assert BollingerBandsIndicator.get_output_names() == [
            "upper",
            "middle",
            "lower",
        ]

    def test_get_primary_output(self):
        """BollingerBands primary output should be 'upper'."""
        assert BollingerBandsIndicator.get_primary_output() == "upper"

    def test_is_multi_output(self):
        """BollingerBands should be multi-output."""
        assert BollingerBandsIndicator.is_multi_output() is True


class TestMACDInterface:
    """Test MACD get_output_names() interface."""

    def test_get_output_names(self):
        """MACD should return ['line', 'signal', 'histogram']."""
        assert MACDIndicator.get_output_names() == ["line", "signal", "histogram"]

    def test_get_primary_output(self):
        """MACD primary output should be 'line'."""
        assert MACDIndicator.get_primary_output() == "line"

    def test_is_multi_output(self):
        """MACD should be multi-output."""
        assert MACDIndicator.is_multi_output() is True


class TestStochasticInterface:
    """Test Stochastic get_output_names() interface."""

    def test_get_output_names(self):
        """Stochastic should return ['k', 'd']."""
        assert StochasticIndicator.get_output_names() == ["k", "d"]

    def test_get_primary_output(self):
        """Stochastic primary output should be 'k'."""
        assert StochasticIndicator.get_primary_output() == "k"

    def test_is_multi_output(self):
        """Stochastic should be multi-output."""
        assert StochasticIndicator.is_multi_output() is True


class TestADXInterface:
    """Test ADX get_output_names() interface."""

    def test_get_output_names(self):
        """ADX should return ['adx', 'plus_di', 'minus_di']."""
        assert ADXIndicator.get_output_names() == ["adx", "plus_di", "minus_di"]

    def test_get_primary_output(self):
        """ADX primary output should be 'adx'."""
        assert ADXIndicator.get_primary_output() == "adx"

    def test_is_multi_output(self):
        """ADX should be multi-output."""
        assert ADXIndicator.is_multi_output() is True


class TestAroonInterface:
    """Test Aroon get_output_names() interface."""

    def test_get_output_names(self):
        """Aroon should return ['up', 'down', 'oscillator']."""
        assert AroonIndicator.get_output_names() == ["up", "down", "oscillator"]

    def test_get_primary_output(self):
        """Aroon primary output should be 'up'."""
        assert AroonIndicator.get_primary_output() == "up"

    def test_is_multi_output(self):
        """Aroon should be multi-output."""
        assert AroonIndicator.is_multi_output() is True


class TestIchimokuInterface:
    """Test Ichimoku get_output_names() interface."""

    def test_get_output_names(self):
        """Ichimoku should return ['tenkan', 'kijun', 'senkou_a', 'senkou_b', 'chikou']."""
        assert IchimokuIndicator.get_output_names() == [
            "tenkan",
            "kijun",
            "senkou_a",
            "senkou_b",
            "chikou",
        ]

    def test_get_primary_output(self):
        """Ichimoku primary output should be 'tenkan'."""
        assert IchimokuIndicator.get_primary_output() == "tenkan"

    def test_is_multi_output(self):
        """Ichimoku should be multi-output."""
        assert IchimokuIndicator.is_multi_output() is True


class TestSupertrendInterface:
    """Test Supertrend get_output_names() interface."""

    def test_get_output_names(self):
        """Supertrend should return ['trend', 'direction']."""
        assert SuperTrendIndicator.get_output_names() == ["trend", "direction"]

    def test_get_primary_output(self):
        """Supertrend primary output should be 'trend'."""
        assert SuperTrendIndicator.get_primary_output() == "trend"

    def test_is_multi_output(self):
        """Supertrend should be multi-output."""
        assert SuperTrendIndicator.is_multi_output() is True


class TestDonchianChannelsInterface:
    """Test DonchianChannels get_output_names() interface."""

    def test_get_output_names(self):
        """DonchianChannels should return ['upper', 'middle', 'lower']."""
        assert DonchianChannelsIndicator.get_output_names() == [
            "upper",
            "middle",
            "lower",
        ]

    def test_get_primary_output(self):
        """DonchianChannels primary output should be 'upper'."""
        assert DonchianChannelsIndicator.get_primary_output() == "upper"

    def test_is_multi_output(self):
        """DonchianChannels should be multi-output."""
        assert DonchianChannelsIndicator.is_multi_output() is True


class TestKeltnerChannelsInterface:
    """Test KeltnerChannels get_output_names() interface."""

    def test_get_output_names(self):
        """KeltnerChannels should return ['upper', 'middle', 'lower']."""
        assert KeltnerChannelsIndicator.get_output_names() == [
            "upper",
            "middle",
            "lower",
        ]

    def test_get_primary_output(self):
        """KeltnerChannels primary output should be 'upper'."""
        assert KeltnerChannelsIndicator.get_primary_output() == "upper"

    def test_is_multi_output(self):
        """KeltnerChannels should be multi-output."""
        assert KeltnerChannelsIndicator.is_multi_output() is True


class TestFisherTransformInterface:
    """Test FisherTransform get_output_names() interface."""

    def test_get_output_names(self):
        """FisherTransform should return ['fisher', 'signal']."""
        assert FisherTransformIndicator.get_output_names() == ["fisher", "signal"]

    def test_get_primary_output(self):
        """FisherTransform primary output should be 'fisher'."""
        assert FisherTransformIndicator.get_primary_output() == "fisher"

    def test_is_multi_output(self):
        """FisherTransform should be multi-output."""
        assert FisherTransformIndicator.is_multi_output() is True


class TestRVIInterface:
    """Test RVI get_output_names() interface."""

    def test_get_output_names(self):
        """RVI should return ['rvi', 'signal']."""
        assert RVIIndicator.get_output_names() == ["rvi", "signal"]

    def test_get_primary_output(self):
        """RVI primary output should be 'rvi'."""
        assert RVIIndicator.get_primary_output() == "rvi"

    def test_is_multi_output(self):
        """RVI should be multi-output."""
        assert RVIIndicator.is_multi_output() is True


class TestADLineInterface:
    """Test ADLine get_output_names() interface."""

    def test_get_output_names(self):
        """ADLine should return correct output names."""
        assert ADLineIndicator.get_output_names() == [
            "line",
            "mf_multiplier",
            "mf_volume",
            "roc_10",
            "momentum_21",
            "relative_strength",
        ]

    def test_get_primary_output(self):
        """ADLine primary output should be 'line'."""
        assert ADLineIndicator.get_primary_output() == "line"

    def test_is_multi_output(self):
        """ADLine should be multi-output."""
        assert ADLineIndicator.is_multi_output() is True


class TestCMFInterface:
    """Test CMF get_output_names() interface."""

    def test_get_output_names(self):
        """CMF should return correct output names."""
        assert CMFIndicator.get_output_names() == [
            "cmf",
            "mf_multiplier",
            "mf_volume",
            "momentum",
            "signal",
            "histogram",
            "above_zero",
            "below_zero",
        ]

    def test_get_primary_output(self):
        """CMF primary output should be 'cmf'."""
        assert CMFIndicator.get_primary_output() == "cmf"

    def test_is_multi_output(self):
        """CMF should be multi-output."""
        assert CMFIndicator.is_multi_output() is True

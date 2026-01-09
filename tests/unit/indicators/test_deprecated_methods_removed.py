"""
Tests verifying deprecated methods are removed from BaseIndicator after M6.2.

These tests ensure that:
1. get_primary_output_suffix() is removed (use get_primary_output() instead)
2. Indicator subclasses no longer have get_primary_output_suffix() overrides
"""

from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator
from ktrdr.indicators.macd_indicator import MACDIndicator
from ktrdr.indicators.rvi_indicator import RVIIndicator
from ktrdr.indicators.stochastic_indicator import StochasticIndicator


class TestGetPrimaryOutputSuffixRemoved:
    """Verify get_primary_output_suffix() is removed."""

    def test_base_indicator_no_get_primary_output_suffix(self):
        """BaseIndicator should not have get_primary_output_suffix method."""
        # After M6.2, this method should be removed
        assert not hasattr(BaseIndicator, "get_primary_output_suffix"), (
            "get_primary_output_suffix() should be removed from BaseIndicator. "
            "Use get_primary_output() instead."
        )

    def test_bollinger_bands_no_get_primary_output_suffix(self):
        """BollingerBandsIndicator should not override get_primary_output_suffix."""
        # Check it doesn't have its own override (beyond what BaseIndicator provides)
        assert "get_primary_output_suffix" not in BollingerBandsIndicator.__dict__, (
            "BollingerBandsIndicator should not override get_primary_output_suffix(). "
            "Use get_output_names() instead."
        )

    def test_macd_no_get_primary_output_suffix(self):
        """MACDIndicator should not override get_primary_output_suffix."""
        assert "get_primary_output_suffix" not in MACDIndicator.__dict__, (
            "MACDIndicator should not override get_primary_output_suffix(). "
            "Use get_output_names() instead."
        )

    def test_rvi_no_get_primary_output_suffix(self):
        """RVIIndicator should not override get_primary_output_suffix."""
        assert "get_primary_output_suffix" not in RVIIndicator.__dict__, (
            "RVIIndicator should not override get_primary_output_suffix(). "
            "Use get_output_names() instead."
        )

    def test_stochastic_no_get_primary_output_suffix(self):
        """StochasticIndicator should not override get_primary_output_suffix."""
        assert "get_primary_output_suffix" not in StochasticIndicator.__dict__, (
            "StochasticIndicator should not override get_primary_output_suffix(). "
            "Use get_output_names() instead."
        )


class TestGetPrimaryOutputStillWorks:
    """Verify get_primary_output() works correctly after removing the suffix method."""

    def test_bollinger_bands_primary_output(self):
        """BollingerBands.get_primary_output() returns correct value."""
        assert BollingerBandsIndicator.get_primary_output() == "upper"

    def test_macd_primary_output(self):
        """MACD.get_primary_output() returns correct value."""
        assert MACDIndicator.get_primary_output() == "line"

    def test_rvi_primary_output(self):
        """RVI.get_primary_output() returns correct value."""
        assert RVIIndicator.get_primary_output() == "rvi"

    def test_stochastic_primary_output(self):
        """Stochastic.get_primary_output() returns correct value."""
        assert StochasticIndicator.get_primary_output() == "k"

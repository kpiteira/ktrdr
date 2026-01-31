"""
Tests for volatility indicators migration to Params pattern.

This test verifies that all 6 volatility indicators have been migrated to
the new Params-based validation pattern and are registered in INDICATOR_REGISTRY.

Volatility indicators: ATR, BollingerBands, BollingerBandWidth, KeltnerChannels,
                       DonchianChannels, SuperTrend
"""

import pytest
from pydantic import BaseModel

from ktrdr.errors import DataError
from ktrdr.indicators import INDICATOR_REGISTRY
from ktrdr.indicators.base_indicator import BaseIndicator


class TestVolatilityIndicatorsMigration:
    """Test that all volatility indicators have Params class and are registered."""

    VOLATILITY_INDICATORS = [
        ("atr", "ATRIndicator"),
        ("bollingerbands", "BollingerBandsIndicator"),
        ("bollingerbandwidth", "BollingerBandWidthIndicator"),
        ("keltnerchannels", "KeltnerChannelsIndicator"),
        ("donchianchannels", "DonchianChannelsIndicator"),
        ("supertrend", "SuperTrendIndicator"),
    ]

    @pytest.mark.parametrize("canonical,class_name", VOLATILITY_INDICATORS)
    def test_indicator_registered(self, canonical: str, class_name: str) -> None:
        """Test that indicator is registered in INDICATOR_REGISTRY."""
        cls = INDICATOR_REGISTRY.get(canonical)
        assert cls is not None, f"{canonical} not found in registry"
        assert cls.__name__ == class_name

    @pytest.mark.parametrize("canonical,class_name", VOLATILITY_INDICATORS)
    def test_indicator_has_params_class(self, canonical: str, class_name: str) -> None:
        """Test that indicator has a Params class inheriting from BaseModel."""
        cls = INDICATOR_REGISTRY.get(canonical)
        assert cls is not None, f"{canonical} not found in registry"

        # Check Params class exists and is not just inherited from BaseIndicator
        assert hasattr(cls, "Params"), f"{class_name} missing Params class"
        assert (
            cls.Params is not BaseIndicator.Params
        ), f"{class_name}.Params should override BaseIndicator.Params"
        assert issubclass(
            cls.Params, BaseModel
        ), f"{class_name}.Params should inherit from BaseModel"

    @pytest.mark.parametrize("canonical,class_name", VOLATILITY_INDICATORS)
    def test_indicator_params_schema_available(
        self, canonical: str, class_name: str
    ) -> None:
        """Test that Params schema is retrievable via registry."""
        schema = INDICATOR_REGISTRY.get_params_schema(canonical)
        assert schema is not None, f"No Params schema for {canonical}"
        assert issubclass(schema, BaseModel)

    @pytest.mark.parametrize("canonical,class_name", VOLATILITY_INDICATORS)
    def test_indicator_instantiates_with_defaults(
        self, canonical: str, class_name: str
    ) -> None:
        """Test that indicator can be instantiated with default parameters."""
        cls = INDICATOR_REGISTRY.get(canonical)
        assert cls is not None

        # Should work without any parameters
        indicator = cls()
        assert indicator is not None
        assert hasattr(indicator, "params")
        assert isinstance(indicator.params, dict)

    @pytest.mark.parametrize("canonical,class_name", VOLATILITY_INDICATORS)
    def test_case_insensitive_lookup(self, canonical: str, class_name: str) -> None:
        """Test case-insensitive lookup works."""
        cls1 = INDICATOR_REGISTRY.get(canonical)
        cls2 = INDICATOR_REGISTRY.get(canonical.upper())
        cls3 = INDICATOR_REGISTRY.get(class_name.lower())

        assert cls1 is cls2, f"Case-insensitive lookup failed for {canonical}"
        assert cls1 is cls3, f"Alias lookup failed for {class_name}"


class TestATRIndicatorParams:
    """Test ATR indicator Params validation."""

    def test_default_params(self) -> None:
        """Test ATR with default parameters."""
        from ktrdr.indicators.atr_indicator import ATRIndicator

        indicator = ATRIndicator()
        assert indicator.params["period"] == 14

    def test_custom_params(self) -> None:
        """Test ATR with custom parameters."""
        from ktrdr.indicators.atr_indicator import ATRIndicator

        indicator = ATRIndicator(period=20)
        assert indicator.params["period"] == 20

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.atr_indicator import ATRIndicator

        with pytest.raises(DataError) as exc_info:
            ATRIndicator(period=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_false(self) -> None:
        """Test ATR is displayed in separate panel (not overlay)."""
        from ktrdr.indicators.atr_indicator import ATRIndicator

        indicator = ATRIndicator()
        assert indicator.display_as_overlay is False


class TestBollingerBandsIndicatorParams:
    """Test BollingerBands indicator Params validation."""

    def test_default_params(self) -> None:
        """Test BollingerBands with default parameters."""
        from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator

        indicator = BollingerBandsIndicator()
        assert indicator.params["period"] == 20
        assert indicator.params["multiplier"] == 2.0
        assert indicator.params["source"] == "close"

    def test_custom_params(self) -> None:
        """Test BollingerBands with custom parameters."""
        from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator

        indicator = BollingerBandsIndicator(period=30, multiplier=2.5, source="high")
        assert indicator.params["period"] == 30
        assert indicator.params["multiplier"] == 2.5
        assert indicator.params["source"] == "high"

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator

        with pytest.raises(DataError) as exc_info:
            BollingerBandsIndicator(period=1)  # Must be >= 2
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_multiplier_raises_error(self) -> None:
        """Test that invalid multiplier raises DataError."""
        from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator

        with pytest.raises(DataError) as exc_info:
            BollingerBandsIndicator(multiplier=-1.0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_true(self) -> None:
        """Test BollingerBands is displayed as overlay."""
        from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator

        indicator = BollingerBandsIndicator()
        assert indicator.display_as_overlay is True


class TestBollingerBandWidthIndicatorParams:
    """Test BollingerBandWidth indicator Params validation."""

    def test_default_params(self) -> None:
        """Test BollingerBandWidth with default parameters."""
        from ktrdr.indicators.bollinger_band_width_indicator import (
            BollingerBandWidthIndicator,
        )

        indicator = BollingerBandWidthIndicator()
        assert indicator.params["period"] == 20
        assert indicator.params["multiplier"] == 2.0
        assert indicator.params["source"] == "close"

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.bollinger_band_width_indicator import (
            BollingerBandWidthIndicator,
        )

        with pytest.raises(DataError) as exc_info:
            BollingerBandWidthIndicator(period=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_false(self) -> None:
        """Test BollingerBandWidth is displayed in separate panel."""
        from ktrdr.indicators.bollinger_band_width_indicator import (
            BollingerBandWidthIndicator,
        )

        indicator = BollingerBandWidthIndicator()
        assert indicator.display_as_overlay is False


class TestKeltnerChannelsIndicatorParams:
    """Test KeltnerChannels indicator Params validation."""

    def test_default_params(self) -> None:
        """Test KeltnerChannels with default parameters."""
        from ktrdr.indicators.keltner_channels import KeltnerChannelsIndicator

        indicator = KeltnerChannelsIndicator()
        assert indicator.params["period"] == 20
        assert indicator.params["atr_period"] == 10
        assert indicator.params["multiplier"] == 2.0

    def test_custom_params(self) -> None:
        """Test KeltnerChannels with custom parameters."""
        from ktrdr.indicators.keltner_channels import KeltnerChannelsIndicator

        indicator = KeltnerChannelsIndicator(period=30, atr_period=14, multiplier=1.5)
        assert indicator.params["period"] == 30
        assert indicator.params["atr_period"] == 14
        assert indicator.params["multiplier"] == 1.5

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.keltner_channels import KeltnerChannelsIndicator

        with pytest.raises(DataError) as exc_info:
            KeltnerChannelsIndicator(period=1)  # Must be >= 2
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_atr_period_raises_error(self) -> None:
        """Test that invalid atr_period raises DataError."""
        from ktrdr.indicators.keltner_channels import KeltnerChannelsIndicator

        with pytest.raises(DataError) as exc_info:
            KeltnerChannelsIndicator(atr_period=1)  # Must be >= 2
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_true(self) -> None:
        """Test KeltnerChannels is displayed as overlay."""
        from ktrdr.indicators.keltner_channels import KeltnerChannelsIndicator

        indicator = KeltnerChannelsIndicator()
        assert indicator.display_as_overlay is True


class TestDonchianChannelsIndicatorParams:
    """Test DonchianChannels indicator Params validation."""

    def test_default_params(self) -> None:
        """Test DonchianChannels with default parameters."""
        from ktrdr.indicators.donchian_channels import DonchianChannelsIndicator

        indicator = DonchianChannelsIndicator()
        assert indicator.params["period"] == 20
        assert indicator.params["include_middle"] is True

    def test_custom_params(self) -> None:
        """Test DonchianChannels with custom parameters."""
        from ktrdr.indicators.donchian_channels import DonchianChannelsIndicator

        indicator = DonchianChannelsIndicator(period=14, include_middle=False)
        assert indicator.params["period"] == 14
        assert indicator.params["include_middle"] is False

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.donchian_channels import DonchianChannelsIndicator

        with pytest.raises(DataError) as exc_info:
            DonchianChannelsIndicator(period=1)  # Must be >= 2
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_true(self) -> None:
        """Test DonchianChannels is displayed as overlay."""
        from ktrdr.indicators.donchian_channels import DonchianChannelsIndicator

        indicator = DonchianChannelsIndicator()
        assert indicator.display_as_overlay is True


class TestSuperTrendIndicatorParams:
    """Test SuperTrend indicator Params validation."""

    def test_default_params(self) -> None:
        """Test SuperTrend with default parameters."""
        from ktrdr.indicators.supertrend_indicator import SuperTrendIndicator

        indicator = SuperTrendIndicator()
        assert indicator.params["period"] == 10
        assert indicator.params["multiplier"] == 3.0

    def test_custom_params(self) -> None:
        """Test SuperTrend with custom parameters."""
        from ktrdr.indicators.supertrend_indicator import SuperTrendIndicator

        indicator = SuperTrendIndicator(period=14, multiplier=2.0)
        assert indicator.params["period"] == 14
        assert indicator.params["multiplier"] == 2.0

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.supertrend_indicator import SuperTrendIndicator

        with pytest.raises(DataError) as exc_info:
            SuperTrendIndicator(period=1)  # Must be >= 2
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_multiplier_raises_error(self) -> None:
        """Test that invalid multiplier raises DataError."""
        from ktrdr.indicators.supertrend_indicator import SuperTrendIndicator

        with pytest.raises(DataError) as exc_info:
            SuperTrendIndicator(multiplier=0)  # Must be > 0
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_true(self) -> None:
        """Test SuperTrend is displayed as overlay."""
        from ktrdr.indicators.supertrend_indicator import SuperTrendIndicator

        indicator = SuperTrendIndicator()
        assert indicator.display_as_overlay is True

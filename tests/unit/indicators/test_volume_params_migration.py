"""
Tests for volume indicators migration to Params pattern.

This test verifies that all 5 volume indicators have been migrated to
the new Params-based validation pattern and are registered in INDICATOR_REGISTRY.

Volume indicators: OBV, VWAP, MFI, CMF, ADLine
"""

import pytest
from pydantic import BaseModel

from ktrdr.errors import DataError
from ktrdr.indicators import INDICATOR_REGISTRY
from ktrdr.indicators.base_indicator import BaseIndicator


class TestVolumeIndicatorsMigration:
    """Test that all volume indicators have Params class and are registered."""

    VOLUME_INDICATORS = [
        ("obv", "OBVIndicator"),
        ("vwap", "VWAPIndicator"),
        ("mfi", "MFIIndicator"),
        ("cmf", "CMFIndicator"),
        ("adline", "ADLineIndicator"),
    ]

    @pytest.mark.parametrize("canonical,class_name", VOLUME_INDICATORS)
    def test_indicator_registered(self, canonical: str, class_name: str) -> None:
        """Test that indicator is registered in INDICATOR_REGISTRY."""
        cls = INDICATOR_REGISTRY.get(canonical)
        assert cls is not None, f"{canonical} not found in registry"
        assert cls.__name__ == class_name

    @pytest.mark.parametrize("canonical,class_name", VOLUME_INDICATORS)
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

    @pytest.mark.parametrize("canonical,class_name", VOLUME_INDICATORS)
    def test_indicator_params_schema_available(
        self, canonical: str, class_name: str
    ) -> None:
        """Test that Params schema is retrievable via registry."""
        schema = INDICATOR_REGISTRY.get_params_schema(canonical)
        assert schema is not None, f"No Params schema for {canonical}"
        assert issubclass(schema, BaseModel)

    @pytest.mark.parametrize("canonical,class_name", VOLUME_INDICATORS)
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

    @pytest.mark.parametrize("canonical,class_name", VOLUME_INDICATORS)
    def test_case_insensitive_lookup(self, canonical: str, class_name: str) -> None:
        """Test case-insensitive lookup works."""
        cls1 = INDICATOR_REGISTRY.get(canonical)
        cls2 = INDICATOR_REGISTRY.get(canonical.upper())
        cls3 = INDICATOR_REGISTRY.get(class_name.lower())

        assert cls1 is cls2, f"Case-insensitive lookup failed for {canonical}"
        assert cls1 is cls3, f"Alias lookup failed for {class_name}"


class TestOBVIndicatorParams:
    """Test OBV indicator Params validation."""

    def test_default_params(self) -> None:
        """Test OBV with default parameters (OBV has no params)."""
        from ktrdr.indicators.obv_indicator import OBVIndicator

        indicator = OBVIndicator()
        # OBV has no configurable parameters
        assert indicator.params == {}

    def test_ignores_extra_params(self) -> None:
        """Test OBV ignores extra parameters."""
        from ktrdr.indicators.obv_indicator import OBVIndicator

        # Should not raise - extra params are ignored
        indicator = OBVIndicator(period=14)
        assert indicator.params == {}


class TestVWAPIndicatorParams:
    """Test VWAP indicator Params validation."""

    def test_default_params(self) -> None:
        """Test VWAP with default parameters."""
        from ktrdr.indicators.vwap_indicator import VWAPIndicator

        indicator = VWAPIndicator()
        assert indicator.params["period"] == 20
        assert indicator.params["use_typical_price"] is True

    def test_custom_params(self) -> None:
        """Test VWAP with custom parameters."""
        from ktrdr.indicators.vwap_indicator import VWAPIndicator

        indicator = VWAPIndicator(period=50, use_typical_price=False)
        assert indicator.params["period"] == 50
        assert indicator.params["use_typical_price"] is False

    def test_cumulative_vwap(self) -> None:
        """Test VWAP with period=0 for cumulative calculation."""
        from ktrdr.indicators.vwap_indicator import VWAPIndicator

        indicator = VWAPIndicator(period=0)
        assert indicator.params["period"] == 0

    def test_invalid_period_negative(self) -> None:
        """Test VWAP rejects negative period."""
        from ktrdr.indicators.vwap_indicator import VWAPIndicator

        with pytest.raises(DataError) as exc_info:
            VWAPIndicator(period=-1)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_period_too_large(self) -> None:
        """Test VWAP rejects period > 200."""
        from ktrdr.indicators.vwap_indicator import VWAPIndicator

        with pytest.raises(DataError) as exc_info:
            VWAPIndicator(period=201)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"


class TestMFIIndicatorParams:
    """Test MFI indicator Params validation."""

    def test_default_params(self) -> None:
        """Test MFI with default parameters."""
        from ktrdr.indicators.mfi_indicator import MFIIndicator

        indicator = MFIIndicator()
        assert indicator.params["period"] == 14

    def test_custom_params(self) -> None:
        """Test MFI with custom parameters."""
        from ktrdr.indicators.mfi_indicator import MFIIndicator

        indicator = MFIIndicator(period=21)
        assert indicator.params["period"] == 21

    def test_invalid_period_zero(self) -> None:
        """Test MFI rejects period < 1."""
        from ktrdr.indicators.mfi_indicator import MFIIndicator

        with pytest.raises(DataError) as exc_info:
            MFIIndicator(period=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_period_too_large(self) -> None:
        """Test MFI rejects period > 100."""
        from ktrdr.indicators.mfi_indicator import MFIIndicator

        with pytest.raises(DataError) as exc_info:
            MFIIndicator(period=101)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"


class TestCMFIndicatorParams:
    """Test CMF indicator Params validation."""

    def test_default_params(self) -> None:
        """Test CMF with default parameters."""
        from ktrdr.indicators.cmf_indicator import CMFIndicator

        indicator = CMFIndicator()
        assert indicator.params["period"] == 21

    def test_custom_params(self) -> None:
        """Test CMF with custom parameters."""
        from ktrdr.indicators.cmf_indicator import CMFIndicator

        indicator = CMFIndicator(period=14)
        assert indicator.params["period"] == 14

    def test_invalid_period_too_small(self) -> None:
        """Test CMF rejects period < 2."""
        from ktrdr.indicators.cmf_indicator import CMFIndicator

        with pytest.raises(DataError) as exc_info:
            CMFIndicator(period=1)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_period_too_large(self) -> None:
        """Test CMF rejects period > 500."""
        from ktrdr.indicators.cmf_indicator import CMFIndicator

        with pytest.raises(DataError) as exc_info:
            CMFIndicator(period=501)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"


class TestADLineIndicatorParams:
    """Test ADLine indicator Params validation."""

    def test_default_params(self) -> None:
        """Test ADLine with default parameters."""
        from ktrdr.indicators.ad_line import ADLineIndicator

        indicator = ADLineIndicator()
        assert indicator.params["use_sma_smoothing"] is False
        assert indicator.params["smoothing_period"] == 21

    def test_custom_params(self) -> None:
        """Test ADLine with custom parameters."""
        from ktrdr.indicators.ad_line import ADLineIndicator

        indicator = ADLineIndicator(use_sma_smoothing=True, smoothing_period=50)
        assert indicator.params["use_sma_smoothing"] is True
        assert indicator.params["smoothing_period"] == 50

    def test_invalid_smoothing_period_too_small(self) -> None:
        """Test ADLine rejects smoothing_period < 2."""
        from ktrdr.indicators.ad_line import ADLineIndicator

        with pytest.raises(DataError) as exc_info:
            ADLineIndicator(smoothing_period=1)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_smoothing_period_too_large(self) -> None:
        """Test ADLine rejects smoothing_period > 200."""
        from ktrdr.indicators.ad_line import ADLineIndicator

        with pytest.raises(DataError) as exc_info:
            ADLineIndicator(smoothing_period=201)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_non_boolean_smoothing_flag(self) -> None:
        """Test ADLine enforces boolean for use_sma_smoothing."""
        from ktrdr.indicators.ad_line import ADLineIndicator

        # With strict=True, non-booleans should be rejected
        with pytest.raises(DataError) as exc_info:
            ADLineIndicator(use_sma_smoothing="yes")
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

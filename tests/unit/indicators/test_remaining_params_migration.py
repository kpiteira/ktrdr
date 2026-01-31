"""
Tests for remaining indicators migration to Params pattern.

This test verifies that the remaining 4 indicators have been migrated to
the new Params-based validation pattern and are registered in INDICATOR_REGISTRY.

Remaining indicators: VolumeRatio, DistanceFromMA, SqueezeIntensity, ZigZag
"""

import pytest
from pydantic import BaseModel

from ktrdr.errors import DataError
from ktrdr.indicators import INDICATOR_REGISTRY
from ktrdr.indicators.base_indicator import BaseIndicator


class TestRemainingIndicatorsMigration:
    """Test that all remaining indicators have Params class and are registered."""

    REMAINING_INDICATORS = [
        ("volumeratio", "VolumeRatioIndicator"),
        ("distancefromma", "DistanceFromMAIndicator"),
        ("squeezeintensity", "SqueezeIntensityIndicator"),
        ("zigzag", "ZigZagIndicator"),
    ]

    @pytest.mark.parametrize("canonical,class_name", REMAINING_INDICATORS)
    def test_indicator_registered(self, canonical: str, class_name: str) -> None:
        """Test that indicator is registered in INDICATOR_REGISTRY."""
        cls = INDICATOR_REGISTRY.get(canonical)
        assert cls is not None, f"{canonical} not found in registry"
        assert cls.__name__ == class_name

    @pytest.mark.parametrize("canonical,class_name", REMAINING_INDICATORS)
    def test_indicator_has_own_params_class(
        self, canonical: str, class_name: str
    ) -> None:
        """Test that indicator has its OWN Params class (not just inherited)."""
        cls = INDICATOR_REGISTRY.get(canonical)
        assert cls is not None, f"{canonical} not found in registry"

        # Check Params class exists in the class's own __dict__ (not inherited)
        assert (
            "Params" in cls.__dict__
        ), f"{class_name} missing own Params class (may be using inherited)"
        assert issubclass(
            cls.Params, BaseModel
        ), f"{class_name}.Params should inherit from BaseModel"
        assert issubclass(
            cls.Params, BaseIndicator.Params
        ), f"{class_name}.Params should inherit from BaseIndicator.Params"

    @pytest.mark.parametrize("canonical,class_name", REMAINING_INDICATORS)
    def test_indicator_params_schema_available(
        self, canonical: str, class_name: str
    ) -> None:
        """Test that Params schema is retrievable via registry."""
        schema = INDICATOR_REGISTRY.get_params_schema(canonical)
        assert schema is not None, f"No Params schema for {canonical}"
        assert issubclass(schema, BaseModel)

    @pytest.mark.parametrize("canonical,class_name", REMAINING_INDICATORS)
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

    @pytest.mark.parametrize("canonical,class_name", REMAINING_INDICATORS)
    def test_case_insensitive_lookup(self, canonical: str, class_name: str) -> None:
        """Test case-insensitive lookup works."""
        cls1 = INDICATOR_REGISTRY.get(canonical)
        cls2 = INDICATOR_REGISTRY.get(canonical.upper())
        cls3 = INDICATOR_REGISTRY.get(class_name.lower())

        assert cls1 is cls2, f"Case-insensitive lookup failed for {canonical}"
        assert cls1 is cls3, f"Alias lookup failed for {class_name}"


class TestVolumeRatioIndicatorParams:
    """Test VolumeRatio indicator Params validation."""

    def test_default_params(self) -> None:
        """Test VolumeRatio with default parameters."""
        from ktrdr.indicators.volume_ratio_indicator import VolumeRatioIndicator

        indicator = VolumeRatioIndicator()
        assert indicator.params["period"] == 20

    def test_custom_params(self) -> None:
        """Test VolumeRatio with custom parameters."""
        from ktrdr.indicators.volume_ratio_indicator import VolumeRatioIndicator

        indicator = VolumeRatioIndicator(period=50)
        assert indicator.params["period"] == 50

    def test_invalid_period_too_small(self) -> None:
        """Test VolumeRatio rejects period < 2."""
        from ktrdr.indicators.volume_ratio_indicator import VolumeRatioIndicator

        with pytest.raises(DataError) as exc_info:
            VolumeRatioIndicator(period=1)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_period_too_large(self) -> None:
        """Test VolumeRatio rejects period > 100."""
        from ktrdr.indicators.volume_ratio_indicator import VolumeRatioIndicator

        with pytest.raises(DataError) as exc_info:
            VolumeRatioIndicator(period=101)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"


class TestDistanceFromMAIndicatorParams:
    """Test DistanceFromMA indicator Params validation."""

    def test_default_params(self) -> None:
        """Test DistanceFromMA with default parameters."""
        from ktrdr.indicators.distance_from_ma_indicator import DistanceFromMAIndicator

        indicator = DistanceFromMAIndicator()
        assert indicator.params["period"] == 20
        assert indicator.params["ma_type"] == "SMA"
        assert indicator.params["source"] == "close"

    def test_custom_params(self) -> None:
        """Test DistanceFromMA with custom parameters."""
        from ktrdr.indicators.distance_from_ma_indicator import DistanceFromMAIndicator

        indicator = DistanceFromMAIndicator(period=50, ma_type="EMA", source="open")
        assert indicator.params["period"] == 50
        assert indicator.params["ma_type"] == "EMA"
        assert indicator.params["source"] == "open"

    def test_invalid_period_too_small(self) -> None:
        """Test DistanceFromMA rejects period < 1."""
        from ktrdr.indicators.distance_from_ma_indicator import DistanceFromMAIndicator

        with pytest.raises(DataError) as exc_info:
            DistanceFromMAIndicator(period=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_period_too_large(self) -> None:
        """Test DistanceFromMA rejects period > 200."""
        from ktrdr.indicators.distance_from_ma_indicator import DistanceFromMAIndicator

        with pytest.raises(DataError) as exc_info:
            DistanceFromMAIndicator(period=201)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_ma_type(self) -> None:
        """Test DistanceFromMA rejects invalid ma_type."""
        from ktrdr.indicators.distance_from_ma_indicator import DistanceFromMAIndicator

        with pytest.raises(DataError) as exc_info:
            DistanceFromMAIndicator(ma_type="WMA")  # Only SMA/EMA supported
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"


class TestSqueezeIntensityIndicatorParams:
    """Test SqueezeIntensity indicator Params validation."""

    def test_default_params(self) -> None:
        """Test SqueezeIntensity with default parameters."""
        from ktrdr.indicators.squeeze_intensity_indicator import (
            SqueezeIntensityIndicator,
        )

        indicator = SqueezeIntensityIndicator()
        assert indicator.params["bb_period"] == 20
        assert indicator.params["bb_multiplier"] == 2.0
        assert indicator.params["kc_period"] == 20
        assert indicator.params["kc_multiplier"] == 2.0
        assert indicator.params["source"] == "close"

    def test_custom_params(self) -> None:
        """Test SqueezeIntensity with custom parameters."""
        from ktrdr.indicators.squeeze_intensity_indicator import (
            SqueezeIntensityIndicator,
        )

        indicator = SqueezeIntensityIndicator(
            bb_period=14, bb_multiplier=2.5, kc_period=20, kc_multiplier=1.5
        )
        assert indicator.params["bb_period"] == 14
        assert indicator.params["bb_multiplier"] == 2.5
        assert indicator.params["kc_period"] == 20
        assert indicator.params["kc_multiplier"] == 1.5

    def test_invalid_bb_period_too_small(self) -> None:
        """Test SqueezeIntensity rejects bb_period < 2."""
        from ktrdr.indicators.squeeze_intensity_indicator import (
            SqueezeIntensityIndicator,
        )

        with pytest.raises(DataError) as exc_info:
            SqueezeIntensityIndicator(bb_period=1)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_bb_period_too_large(self) -> None:
        """Test SqueezeIntensity rejects bb_period > 100."""
        from ktrdr.indicators.squeeze_intensity_indicator import (
            SqueezeIntensityIndicator,
        )

        with pytest.raises(DataError) as exc_info:
            SqueezeIntensityIndicator(bb_period=101)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_multiplier_too_small(self) -> None:
        """Test SqueezeIntensity rejects multiplier <= 0."""
        from ktrdr.indicators.squeeze_intensity_indicator import (
            SqueezeIntensityIndicator,
        )

        with pytest.raises(DataError) as exc_info:
            SqueezeIntensityIndicator(bb_multiplier=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_multiplier_too_large(self) -> None:
        """Test SqueezeIntensity rejects multiplier > 5."""
        from ktrdr.indicators.squeeze_intensity_indicator import (
            SqueezeIntensityIndicator,
        )

        with pytest.raises(DataError) as exc_info:
            SqueezeIntensityIndicator(bb_multiplier=5.1)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"


class TestZigZagIndicatorParams:
    """Test ZigZag indicator Params validation."""

    def test_default_params(self) -> None:
        """Test ZigZag with default parameters."""
        from ktrdr.indicators.zigzag_indicator import ZigZagIndicator

        indicator = ZigZagIndicator()
        assert indicator.params["threshold"] == 0.05
        assert indicator.params["source"] == "close"

    def test_custom_params(self) -> None:
        """Test ZigZag with custom parameters."""
        from ktrdr.indicators.zigzag_indicator import ZigZagIndicator

        indicator = ZigZagIndicator(threshold=0.10, source="high")
        assert indicator.params["threshold"] == 0.10
        assert indicator.params["source"] == "high"

    def test_invalid_threshold_too_small(self) -> None:
        """Test ZigZag rejects threshold <= 0."""
        from ktrdr.indicators.zigzag_indicator import ZigZagIndicator

        with pytest.raises(DataError) as exc_info:
            ZigZagIndicator(threshold=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_threshold_too_large(self) -> None:
        """Test ZigZag rejects threshold >= 1."""
        from ktrdr.indicators.zigzag_indicator import ZigZagIndicator

        with pytest.raises(DataError) as exc_info:
            ZigZagIndicator(threshold=1.0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_valid_threshold_near_boundaries(self) -> None:
        """Test ZigZag accepts threshold near boundaries."""
        from ktrdr.indicators.zigzag_indicator import ZigZagIndicator

        # Very small but valid
        indicator1 = ZigZagIndicator(threshold=0.001)
        assert indicator1.params["threshold"] == 0.001

        # Large but valid
        indicator2 = ZigZagIndicator(threshold=0.99)
        assert indicator2.params["threshold"] == 0.99

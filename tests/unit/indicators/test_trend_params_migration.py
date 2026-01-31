"""
Tests for trend indicators migration to Params pattern.

This test verifies that all 7 trend indicators have been migrated to
the new Params-based validation pattern and are registered in INDICATOR_REGISTRY.

Trend indicators: SMA, EMA, WMA, MACD, ADX, ParabolicSAR, Ichimoku
"""

import pytest
from pydantic import BaseModel

from ktrdr.errors import DataError
from ktrdr.indicators import INDICATOR_REGISTRY
from ktrdr.indicators.base_indicator import BaseIndicator


class TestTrendIndicatorsMigration:
    """Test that all trend indicators have Params class and are registered."""

    TREND_INDICATORS = [
        ("simplemovingaverage", "SimpleMovingAverage"),
        ("exponentialmovingaverage", "ExponentialMovingAverage"),
        ("weightedmovingaverage", "WeightedMovingAverage"),
        ("macd", "MACDIndicator"),
        ("adx", "ADXIndicator"),
        ("parabolicsar", "ParabolicSARIndicator"),
        ("ichimoku", "IchimokuIndicator"),
    ]

    @pytest.mark.parametrize("canonical,class_name", TREND_INDICATORS)
    def test_indicator_registered(self, canonical: str, class_name: str) -> None:
        """Test that indicator is registered in INDICATOR_REGISTRY."""
        cls = INDICATOR_REGISTRY.get(canonical)
        assert cls is not None, f"{canonical} not found in registry"
        assert cls.__name__ == class_name

    @pytest.mark.parametrize("canonical,class_name", TREND_INDICATORS)
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

    @pytest.mark.parametrize("canonical,class_name", TREND_INDICATORS)
    def test_indicator_params_schema_available(
        self, canonical: str, class_name: str
    ) -> None:
        """Test that Params schema is retrievable via registry."""
        schema = INDICATOR_REGISTRY.get_params_schema(canonical)
        assert schema is not None, f"No Params schema for {canonical}"
        assert issubclass(schema, BaseModel)

    @pytest.mark.parametrize("canonical,class_name", TREND_INDICATORS)
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

    @pytest.mark.parametrize("canonical,class_name", TREND_INDICATORS)
    def test_case_insensitive_lookup(self, canonical: str, class_name: str) -> None:
        """Test case-insensitive lookup works."""
        cls1 = INDICATOR_REGISTRY.get(canonical)
        cls2 = INDICATOR_REGISTRY.get(canonical.upper())
        cls3 = INDICATOR_REGISTRY.get(class_name.lower())

        assert cls1 is cls2, f"Case-insensitive lookup failed for {canonical}"
        assert cls1 is cls3, f"Alias lookup failed for {class_name}"


class TestSMAIndicatorParams:
    """Test SMA indicator Params validation."""

    def test_default_params(self) -> None:
        """Test SMA with default parameters."""
        from ktrdr.indicators.ma_indicators import SimpleMovingAverage

        indicator = SimpleMovingAverage()
        assert indicator.params["period"] == 20
        assert indicator.params["source"] == "close"

    def test_custom_params(self) -> None:
        """Test SMA with custom parameters."""
        from ktrdr.indicators.ma_indicators import SimpleMovingAverage

        indicator = SimpleMovingAverage(period=50, source="high")
        assert indicator.params["period"] == 50
        assert indicator.params["source"] == "high"

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.ma_indicators import SimpleMovingAverage

        with pytest.raises(DataError) as exc_info:
            SimpleMovingAverage(period=1)  # Must be >= 2
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_period_upper_bound(self) -> None:
        """Test period upper bound validation."""
        from ktrdr.indicators.ma_indicators import SimpleMovingAverage

        with pytest.raises(DataError) as exc_info:
            SimpleMovingAverage(period=501)  # Must be <= 500
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_true(self) -> None:
        """Test SMA is displayed as overlay."""
        from ktrdr.indicators.ma_indicators import SimpleMovingAverage

        indicator = SimpleMovingAverage()
        assert indicator.display_as_overlay is True


class TestEMAIndicatorParams:
    """Test EMA indicator Params validation."""

    def test_default_params(self) -> None:
        """Test EMA with default parameters."""
        from ktrdr.indicators.ma_indicators import ExponentialMovingAverage

        indicator = ExponentialMovingAverage()
        assert indicator.params["period"] == 20
        assert indicator.params["source"] == "close"
        assert indicator.params["adjust"] is True

    def test_custom_params(self) -> None:
        """Test EMA with custom parameters."""
        from ktrdr.indicators.ma_indicators import ExponentialMovingAverage

        indicator = ExponentialMovingAverage(period=12, source="high", adjust=False)
        assert indicator.params["period"] == 12
        assert indicator.params["source"] == "high"
        assert indicator.params["adjust"] is False

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.ma_indicators import ExponentialMovingAverage

        with pytest.raises(DataError) as exc_info:
            ExponentialMovingAverage(period=0)  # Must be >= 1
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_true(self) -> None:
        """Test EMA is displayed as overlay."""
        from ktrdr.indicators.ma_indicators import ExponentialMovingAverage

        indicator = ExponentialMovingAverage()
        assert indicator.display_as_overlay is True


class TestWMAIndicatorParams:
    """Test WMA indicator Params validation."""

    def test_default_params(self) -> None:
        """Test WMA with default parameters."""
        from ktrdr.indicators.ma_indicators import WeightedMovingAverage

        indicator = WeightedMovingAverage()
        assert indicator.params["period"] == 20
        assert indicator.params["source"] == "close"

    def test_custom_params(self) -> None:
        """Test WMA with custom parameters."""
        from ktrdr.indicators.ma_indicators import WeightedMovingAverage

        indicator = WeightedMovingAverage(period=10, source="low")
        assert indicator.params["period"] == 10
        assert indicator.params["source"] == "low"

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.ma_indicators import WeightedMovingAverage

        with pytest.raises(DataError) as exc_info:
            WeightedMovingAverage(period=1)  # Must be >= 2
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_true(self) -> None:
        """Test WMA is displayed as overlay."""
        from ktrdr.indicators.ma_indicators import WeightedMovingAverage

        indicator = WeightedMovingAverage()
        assert indicator.display_as_overlay is True


class TestMACDIndicatorParams:
    """Test MACD indicator Params validation."""

    def test_default_params(self) -> None:
        """Test MACD with default parameters."""
        from ktrdr.indicators.macd_indicator import MACDIndicator

        indicator = MACDIndicator()
        assert indicator.params["fast_period"] == 12
        assert indicator.params["slow_period"] == 26
        assert indicator.params["signal_period"] == 9
        assert indicator.params["source"] == "close"

    def test_custom_params(self) -> None:
        """Test MACD with custom parameters."""
        from ktrdr.indicators.macd_indicator import MACDIndicator

        indicator = MACDIndicator(
            fast_period=8, slow_period=21, signal_period=5, source="high"
        )
        assert indicator.params["fast_period"] == 8
        assert indicator.params["slow_period"] == 21
        assert indicator.params["signal_period"] == 5
        assert indicator.params["source"] == "high"

    def test_invalid_fast_period_raises_error(self) -> None:
        """Test that invalid fast_period raises DataError."""
        from ktrdr.indicators.macd_indicator import MACDIndicator

        with pytest.raises(DataError) as exc_info:
            MACDIndicator(fast_period=0)  # Must be >= 1
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_slow_period_raises_error(self) -> None:
        """Test that invalid slow_period raises DataError."""
        from ktrdr.indicators.macd_indicator import MACDIndicator

        with pytest.raises(DataError) as exc_info:
            MACDIndicator(slow_period=0)  # Must be >= 1
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_false(self) -> None:
        """Test MACD is displayed in separate panel."""
        from ktrdr.indicators.macd_indicator import MACDIndicator

        indicator = MACDIndicator()
        assert indicator.display_as_overlay is False


class TestADXIndicatorParams:
    """Test ADX indicator Params validation."""

    def test_default_params(self) -> None:
        """Test ADX with default parameters."""
        from ktrdr.indicators.adx_indicator import ADXIndicator

        indicator = ADXIndicator()
        assert indicator.params["period"] == 14

    def test_custom_params(self) -> None:
        """Test ADX with custom parameters."""
        from ktrdr.indicators.adx_indicator import ADXIndicator

        indicator = ADXIndicator(period=21)
        assert indicator.params["period"] == 21

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.adx_indicator import ADXIndicator

        with pytest.raises(DataError) as exc_info:
            ADXIndicator(period=1)  # Must be >= 2
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_period_upper_bound(self) -> None:
        """Test period upper bound validation."""
        from ktrdr.indicators.adx_indicator import ADXIndicator

        with pytest.raises(DataError) as exc_info:
            ADXIndicator(period=201)  # Must be <= 200
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_false(self) -> None:
        """Test ADX is displayed in separate panel."""
        from ktrdr.indicators.adx_indicator import ADXIndicator

        indicator = ADXIndicator()
        assert indicator.display_as_overlay is False


class TestParabolicSARIndicatorParams:
    """Test ParabolicSAR indicator Params validation."""

    def test_default_params(self) -> None:
        """Test ParabolicSAR with default parameters."""
        from ktrdr.indicators.parabolic_sar_indicator import ParabolicSARIndicator

        indicator = ParabolicSARIndicator()
        assert indicator.params["initial_af"] == 0.02
        assert indicator.params["step_af"] == 0.02
        assert indicator.params["max_af"] == 0.20

    def test_custom_params(self) -> None:
        """Test ParabolicSAR with custom parameters."""
        from ktrdr.indicators.parabolic_sar_indicator import ParabolicSARIndicator

        indicator = ParabolicSARIndicator(initial_af=0.01, step_af=0.01, max_af=0.10)
        assert indicator.params["initial_af"] == 0.01
        assert indicator.params["step_af"] == 0.01
        assert indicator.params["max_af"] == 0.10

    def test_invalid_initial_af_raises_error(self) -> None:
        """Test that invalid initial_af raises DataError."""
        from ktrdr.indicators.parabolic_sar_indicator import ParabolicSARIndicator

        with pytest.raises(DataError) as exc_info:
            ParabolicSARIndicator(initial_af=0.0005)  # Must be >= 0.001
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_max_af_raises_error(self) -> None:
        """Test that invalid max_af raises DataError."""
        from ktrdr.indicators.parabolic_sar_indicator import ParabolicSARIndicator

        with pytest.raises(DataError) as exc_info:
            ParabolicSARIndicator(max_af=1.5)  # Must be <= 1.0
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_true(self) -> None:
        """Test ParabolicSAR is displayed as overlay."""
        from ktrdr.indicators.parabolic_sar_indicator import ParabolicSARIndicator

        indicator = ParabolicSARIndicator()
        assert indicator.display_as_overlay is True


class TestIchimokuIndicatorParams:
    """Test Ichimoku indicator Params validation."""

    def test_default_params(self) -> None:
        """Test Ichimoku with default parameters."""
        from ktrdr.indicators.ichimoku_indicator import IchimokuIndicator

        indicator = IchimokuIndicator()
        assert indicator.params["tenkan_period"] == 9
        assert indicator.params["kijun_period"] == 26
        assert indicator.params["senkou_b_period"] == 52
        assert indicator.params["displacement"] == 26

    def test_custom_params(self) -> None:
        """Test Ichimoku with custom parameters."""
        from ktrdr.indicators.ichimoku_indicator import IchimokuIndicator

        indicator = IchimokuIndicator(
            tenkan_period=7, kijun_period=22, senkou_b_period=44, displacement=22
        )
        assert indicator.params["tenkan_period"] == 7
        assert indicator.params["kijun_period"] == 22
        assert indicator.params["senkou_b_period"] == 44
        assert indicator.params["displacement"] == 22

    def test_invalid_tenkan_period_raises_error(self) -> None:
        """Test that invalid tenkan_period raises DataError."""
        from ktrdr.indicators.ichimoku_indicator import IchimokuIndicator

        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(tenkan_period=0)  # Must be >= 1
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_invalid_displacement_raises_error(self) -> None:
        """Test that invalid displacement raises DataError."""
        from ktrdr.indicators.ichimoku_indicator import IchimokuIndicator

        with pytest.raises(DataError) as exc_info:
            IchimokuIndicator(displacement=0)  # Must be >= 1
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_display_as_overlay_is_true(self) -> None:
        """Test Ichimoku is displayed as overlay."""
        from ktrdr.indicators.ichimoku_indicator import IchimokuIndicator

        indicator = IchimokuIndicator()
        assert indicator.display_as_overlay is True

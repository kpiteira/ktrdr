"""
Tests for momentum indicators migration to Params pattern.

This test verifies that all 8 momentum indicators have been migrated to
the new Params-based validation pattern and are registered in INDICATOR_REGISTRY.

Momentum indicators: ROC, Momentum, CCI, Williams %R, Stochastic, RVI, Fisher Transform, Aroon
"""

import pytest
from pydantic import BaseModel

from ktrdr.errors import DataError
from ktrdr.indicators import INDICATOR_REGISTRY
from ktrdr.indicators.base_indicator import BaseIndicator


class TestMomentumIndicatorsMigration:
    """Test that all momentum indicators have Params class and are registered."""

    MOMENTUM_INDICATORS = [
        ("roc", "ROCIndicator"),
        ("momentum", "MomentumIndicator"),
        ("cci", "CCIIndicator"),
        ("williamsr", "WilliamsRIndicator"),
        ("stochastic", "StochasticIndicator"),
        ("rvi", "RVIIndicator"),
        ("fishertransform", "FisherTransformIndicator"),
        ("aroon", "AroonIndicator"),
    ]

    @pytest.mark.parametrize("canonical,class_name", MOMENTUM_INDICATORS)
    def test_indicator_registered(self, canonical: str, class_name: str) -> None:
        """Test that indicator is registered in INDICATOR_REGISTRY."""
        cls = INDICATOR_REGISTRY.get(canonical)
        assert cls is not None, f"{canonical} not found in registry"
        assert cls.__name__ == class_name

    @pytest.mark.parametrize("canonical,class_name", MOMENTUM_INDICATORS)
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

    @pytest.mark.parametrize("canonical,class_name", MOMENTUM_INDICATORS)
    def test_indicator_params_schema_available(
        self, canonical: str, class_name: str
    ) -> None:
        """Test that Params schema is retrievable via registry."""
        schema = INDICATOR_REGISTRY.get_params_schema(canonical)
        assert schema is not None, f"No Params schema for {canonical}"
        assert issubclass(schema, BaseModel)

    @pytest.mark.parametrize("canonical,class_name", MOMENTUM_INDICATORS)
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

    @pytest.mark.parametrize("canonical,class_name", MOMENTUM_INDICATORS)
    def test_case_insensitive_lookup(self, canonical: str, class_name: str) -> None:
        """Test case-insensitive lookup works."""
        cls1 = INDICATOR_REGISTRY.get(canonical)
        cls2 = INDICATOR_REGISTRY.get(canonical.upper())
        cls3 = INDICATOR_REGISTRY.get(class_name.lower())

        assert cls1 is cls2, f"Case-insensitive lookup failed for {canonical}"
        assert cls1 is cls3, f"Alias lookup failed for {class_name}"


class TestROCIndicatorParams:
    """Test ROC indicator Params validation."""

    def test_default_params(self) -> None:
        """Test ROC with default parameters."""
        from ktrdr.indicators.roc_indicator import ROCIndicator

        indicator = ROCIndicator()
        assert indicator.params["period"] == 10
        assert indicator.params["source"] == "close"

    def test_custom_params(self) -> None:
        """Test ROC with custom parameters."""
        from ktrdr.indicators.roc_indicator import ROCIndicator

        indicator = ROCIndicator(period=20, source="high")
        assert indicator.params["period"] == 20
        assert indicator.params["source"] == "high"

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.roc_indicator import ROCIndicator

        with pytest.raises(DataError) as exc_info:
            ROCIndicator(period=-1)
        assert "INDICATOR-InvalidParameters" in str(exc_info.value.error_code)


class TestMomentumIndicatorParams:
    """Test Momentum indicator Params validation."""

    def test_default_params(self) -> None:
        """Test Momentum with default parameters."""
        from ktrdr.indicators.momentum_indicator import MomentumIndicator

        indicator = MomentumIndicator()
        assert indicator.params["period"] == 10
        assert indicator.params["source"] == "close"

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.momentum_indicator import MomentumIndicator

        with pytest.raises(DataError) as exc_info:
            MomentumIndicator(period=0)
        assert "INDICATOR-InvalidParameters" in str(exc_info.value.error_code)


class TestCCIIndicatorParams:
    """Test CCI indicator Params validation."""

    def test_default_params(self) -> None:
        """Test CCI with default parameters."""
        from ktrdr.indicators.cci_indicator import CCIIndicator

        indicator = CCIIndicator()
        assert indicator.params["period"] == 20

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.cci_indicator import CCIIndicator

        with pytest.raises(DataError) as exc_info:
            CCIIndicator(period=1)  # CCI requires period >= 2
        assert "INDICATOR-InvalidParameters" in str(exc_info.value.error_code)


class TestWilliamsRIndicatorParams:
    """Test Williams %R indicator Params validation."""

    def test_default_params(self) -> None:
        """Test Williams %R with default parameters."""
        from ktrdr.indicators.williams_r_indicator import WilliamsRIndicator

        indicator = WilliamsRIndicator()
        assert indicator.params["period"] == 14

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.williams_r_indicator import WilliamsRIndicator

        with pytest.raises(DataError) as exc_info:
            WilliamsRIndicator(period=-1)
        assert "INDICATOR-InvalidParameters" in str(exc_info.value.error_code)


class TestStochasticIndicatorParams:
    """Test Stochastic indicator Params validation."""

    def test_default_params(self) -> None:
        """Test Stochastic with default parameters."""
        from ktrdr.indicators.stochastic_indicator import StochasticIndicator

        indicator = StochasticIndicator()
        assert indicator.params["k_period"] == 14
        assert indicator.params["d_period"] == 3
        assert indicator.params["smooth_k"] == 3

    def test_invalid_k_period_raises_error(self) -> None:
        """Test that invalid k_period raises DataError."""
        from ktrdr.indicators.stochastic_indicator import StochasticIndicator

        with pytest.raises(DataError) as exc_info:
            StochasticIndicator(k_period=0)
        assert "INDICATOR-InvalidParameters" in str(exc_info.value.error_code)


class TestRVIIndicatorParams:
    """Test RVI indicator Params validation."""

    def test_default_params(self) -> None:
        """Test RVI with default parameters."""
        from ktrdr.indicators.rvi_indicator import RVIIndicator

        indicator = RVIIndicator()
        assert indicator.params["period"] == 10
        assert indicator.params["signal_period"] == 4

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.rvi_indicator import RVIIndicator

        # RVI period must be >= 4
        with pytest.raises(DataError) as exc_info:
            RVIIndicator(period=2)
        assert "INDICATOR-InvalidParameters" in str(exc_info.value.error_code)


class TestFisherTransformIndicatorParams:
    """Test Fisher Transform indicator Params validation."""

    def test_default_params(self) -> None:
        """Test Fisher Transform with default parameters."""
        from ktrdr.indicators.fisher_transform import FisherTransformIndicator

        indicator = FisherTransformIndicator()
        assert indicator.params["period"] == 10
        assert indicator.params["smoothing"] == 3

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.fisher_transform import FisherTransformIndicator

        with pytest.raises(DataError) as exc_info:
            FisherTransformIndicator(period=1)  # period must be >= 2
        assert "INDICATOR-InvalidParameters" in str(exc_info.value.error_code)


class TestAroonIndicatorParams:
    """Test Aroon indicator Params validation."""

    def test_default_params(self) -> None:
        """Test Aroon with default parameters."""
        from ktrdr.indicators.aroon_indicator import AroonIndicator

        indicator = AroonIndicator()
        assert indicator.params["period"] == 14
        assert indicator.params["include_oscillator"] is False

    def test_invalid_period_raises_error(self) -> None:
        """Test that invalid period raises DataError."""
        from ktrdr.indicators.aroon_indicator import AroonIndicator

        with pytest.raises(DataError) as exc_info:
            AroonIndicator(period=0)
        assert "INDICATOR-InvalidParameters" in str(exc_info.value.error_code)

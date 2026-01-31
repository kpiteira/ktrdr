"""Tests for BaseIndicator auto-registration and Params validation.

These tests verify:
- INDICATOR_REGISTRY exists and is importable
- Concrete subclasses auto-register
- Abstract classes don't register
- Test classes don't register
- Invalid params raise DataError
"""

from abc import abstractmethod

import pandas as pd
import pytest
from pydantic import Field

from ktrdr.errors import DataError


class TestIndicatorRegistry:
    """Tests for INDICATOR_REGISTRY functionality."""

    def test_registry_exists_and_importable(self) -> None:
        """Test that INDICATOR_REGISTRY can be imported."""
        from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY

        assert INDICATOR_REGISTRY is not None
        assert hasattr(INDICATOR_REGISTRY, "get")
        assert hasattr(INDICATOR_REGISTRY, "list_types")
        assert hasattr(INDICATOR_REGISTRY, "get_params_schema")

    def test_concrete_subclass_registers(self) -> None:
        """Test that concrete indicator subclasses auto-register."""
        # RSI is a concrete indicator that should be registered
        from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY

        # RSI should be registered (it's a concrete subclass)
        assert "rsi" in INDICATOR_REGISTRY
        rsi_cls = INDICATOR_REGISTRY.get("rsi")
        assert rsi_cls is not None
        assert rsi_cls.__name__ == "RSIIndicator"

    def test_abstract_subclass_skipped(self) -> None:
        """Test that abstract subclasses don't register."""
        from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY, BaseIndicator

        # Create an abstract subclass
        class AbstractTestIndicator(BaseIndicator):
            @abstractmethod
            def some_abstract_method(self):
                pass

            def compute(self, df):
                pass  # Still abstract because some_abstract_method is abstract

        # Abstract class should not be registered
        assert "abstracttest" not in INDICATOR_REGISTRY
        assert "abstracttestindicator" not in INDICATOR_REGISTRY

    def test_test_class_skipped(self) -> None:
        """Test that classes defined in test modules don't register."""
        from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY, BaseIndicator

        # This class is defined in a test module, so should NOT register
        class TestModuleIndicator(BaseIndicator):
            def compute(self, df):
                return df["close"]

        # Test classes should not be registered
        assert "testmodule" not in INDICATOR_REGISTRY
        assert "testmoduleindicator" not in INDICATOR_REGISTRY


class TestCanonicalNameDerivation:
    """Tests for canonical name derivation from class names."""

    def test_indicator_suffix_stripped(self) -> None:
        """Test that 'Indicator' suffix is stripped from canonical name."""
        from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY

        # RSIIndicator should be registered as 'rsi'
        assert INDICATOR_REGISTRY.get("rsi") is not None
        assert INDICATOR_REGISTRY.get("RSI") is not None  # case-insensitive

    def test_class_name_alias_works(self) -> None:
        """Test that full class name also works as lookup."""
        from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY

        # Both 'rsi' and 'rsiindicator' should work
        rsi_by_short = INDICATOR_REGISTRY.get("rsi")
        rsi_by_full = INDICATOR_REGISTRY.get("rsiindicator")
        assert rsi_by_short is rsi_by_full


class TestParamsValidation:
    """Tests for Params-based validation in BaseIndicator.__init__."""

    def test_base_params_class_exists(self) -> None:
        """Test that BaseIndicator has a Params nested class."""
        from ktrdr.indicators.base_indicator import BaseIndicator

        assert hasattr(BaseIndicator, "Params")
        # Should be a Pydantic BaseModel
        from pydantic import BaseModel

        assert issubclass(BaseIndicator.Params, BaseModel)

    def test_init_validates_via_params(self) -> None:
        """Test that __init__ validates kwargs via Params class."""
        from ktrdr.indicators.base_indicator import BaseIndicator

        # Create a concrete indicator with custom Params
        class ValidatedIndicator(BaseIndicator):
            class Params(BaseIndicator.Params):
                period: int = Field(default=14, ge=2, le=100)
                source: str = Field(default="close")

            def compute(self, df: pd.DataFrame) -> pd.Series:
                return df[self.source]

        # Valid params should work
        indicator = ValidatedIndicator(period=20, source="high")
        assert indicator.period == 20
        assert indicator.source == "high"

    def test_init_sets_attributes(self) -> None:
        """Test that validated params are set as instance attributes."""
        from ktrdr.indicators.base_indicator import BaseIndicator

        class AttrIndicator(BaseIndicator):
            class Params(BaseIndicator.Params):
                fast_period: int = Field(default=5)
                slow_period: int = Field(default=20)

            def compute(self, df: pd.DataFrame) -> pd.Series:
                return df["close"]

        indicator = AttrIndicator(fast_period=10, slow_period=30)

        # Params should be set as attributes
        assert indicator.fast_period == 10
        assert indicator.slow_period == 30
        # Also available in params dict for backward compatibility
        assert indicator.params["fast_period"] == 10
        assert indicator.params["slow_period"] == 30

    def test_invalid_params_raise_data_error(self) -> None:
        """Test that invalid params raise DataError (not ValidationError)."""
        from ktrdr.indicators.base_indicator import BaseIndicator

        class StrictIndicator(BaseIndicator):
            class Params(BaseIndicator.Params):
                period: int = Field(ge=2, le=100)

            def compute(self, df: pd.DataFrame) -> pd.Series:
                return df["close"]

        # Invalid period should raise DataError
        with pytest.raises(DataError) as exc_info:
            StrictIndicator(period=-1)

        error = exc_info.value
        assert error.error_code == "INDICATOR-InvalidParameters"
        assert "validation_errors" in error.details

    def test_defaults_applied_when_no_args(self) -> None:
        """Test that default values from Params are applied."""
        from ktrdr.indicators.base_indicator import BaseIndicator

        class DefaultsIndicator(BaseIndicator):
            class Params(BaseIndicator.Params):
                period: int = Field(default=14)
                source: str = Field(default="close")

            def compute(self, df: pd.DataFrame) -> pd.Series:
                return df[self.source]

        indicator = DefaultsIndicator()
        assert indicator.period == 14
        assert indicator.source == "close"


class TestBackwardCompatibility:
    """Tests ensuring old-style indicators still work."""

    def test_old_style_init_still_works(self) -> None:
        """Test that old-style __init__ with name param still works."""
        from ktrdr.indicators.base_indicator import BaseIndicator

        class OldStyleIndicator(BaseIndicator):
            def __init__(self, period: int = 14):
                super().__init__(name="OldStyle", period=period)

            def compute(self, df: pd.DataFrame) -> pd.Series:
                return df["close"]

        indicator = OldStyleIndicator(period=20)
        assert indicator.name == "OldStyle"
        assert indicator.params["period"] == 20

    def test_existing_rsi_still_works(self) -> None:
        """Test that existing RSIIndicator still works correctly."""
        from ktrdr.indicators import RSIIndicator

        # Create RSI with custom params
        rsi = RSIIndicator(period=21, source="high")
        assert rsi.params["period"] == 21
        assert rsi.params["source"] == "high"

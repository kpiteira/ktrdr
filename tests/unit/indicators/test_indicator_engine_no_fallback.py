"""Unit tests for IndicatorEngine after BUILT_IN_INDICATORS removal.

Task 2.6: Verifies that IndicatorEngine uses INDICATOR_REGISTRY exclusively
without any fallback to BUILT_IN_INDICATORS.
"""

import ast
import inspect

import pandas as pd
import pytest

from ktrdr.config.models import IndicatorDefinition
from ktrdr.indicators import IndicatorEngine
from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY


class TestNoBuiltInIndicatorsFallback:
    """Tests verifying BUILT_IN_INDICATORS is no longer used."""

    def test_indicator_engine_has_no_built_in_indicators_import(self) -> None:
        """indicator_engine.py should not import BUILT_IN_INDICATORS."""
        import ktrdr.indicators.indicator_engine as ie_module

        source = inspect.getsource(ie_module)
        tree = ast.parse(source)

        # Check for any imports referencing BUILT_IN_INDICATORS
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert (
                        alias.name != "BUILT_IN_INDICATORS"
                    ), "indicator_engine.py should not import BUILT_IN_INDICATORS"

    def test_indicator_engine_has_no_built_in_indicators_reference(self) -> None:
        """indicator_engine.py should not reference BUILT_IN_INDICATORS anywhere."""
        import ktrdr.indicators.indicator_engine as ie_module

        source = inspect.getsource(ie_module)

        # Check source code for any reference to BUILT_IN_INDICATORS
        assert (
            "BUILT_IN_INDICATORS" not in source
        ), "indicator_engine.py should not reference BUILT_IN_INDICATORS"


class TestRegistryOnlyLookup:
    """Tests verifying all indicators are looked up via INDICATOR_REGISTRY."""

    def test_indicator_registry_has_types(self) -> None:
        """INDICATOR_REGISTRY should have registered indicator types."""
        # Import all indicator modules to trigger auto-registration
        # (in production code, ktrdr.indicators imports all modules)
        import ktrdr.indicators.adx_indicator  # noqa: F401
        import ktrdr.indicators.atr_indicator  # noqa: F401
        import ktrdr.indicators.bollinger_bands_indicator  # noqa: F401
        import ktrdr.indicators.stochastic_indicator  # noqa: F401

        types = INDICATOR_REGISTRY.list_types()
        # Should have at least the core indicators
        assert len(types) >= 5, f"Expected at least 5 types, got {len(types)}"
        assert "rsi" in types
        assert "bollingerbands" in types  # canonical name is class name lowercase

    def test_ema_created_via_registry(self) -> None:
        """EMA should be created via INDICATOR_REGISTRY (was previously fallback)."""
        from ktrdr.indicators.ma_indicators import ExponentialMovingAverage

        # EMA is now in the registry
        assert INDICATOR_REGISTRY.get("ema") is not None

        indicators = {"ema_20": IndicatorDefinition(type="ema", period=20)}
        engine = IndicatorEngine(indicators)

        assert "ema_20" in engine._indicators
        assert isinstance(engine._indicators["ema_20"], ExponentialMovingAverage)

    def test_all_common_indicators_via_registry(self) -> None:
        """Common indicators should all work via registry."""
        # Import indicators to trigger auto-registration
        import ktrdr.indicators.adx_indicator  # noqa: F401
        import ktrdr.indicators.atr_indicator  # noqa: F401
        import ktrdr.indicators.bollinger_bands_indicator  # noqa: F401
        import ktrdr.indicators.stochastic_indicator  # noqa: F401

        test_cases = [
            ("rsi", {"period": 14}),
            ("ema", {"period": 20}),
            ("sma", {"period": 20}),
            ("wma", {"period": 20}),
            ("macd", {"fast_period": 12, "slow_period": 26, "signal_period": 9}),
            ("atr", {"period": 14}),  # alias for atrindicator
            ("adx", {"period": 14}),  # alias for adxindicator
            ("bollingerbands", {"period": 20, "multiplier": 2.0}),
            ("stochastic", {"k_period": 14, "d_period": 3}),
        ]

        for indicator_type, params in test_cases:
            indicators = {
                f"test_{indicator_type}": IndicatorDefinition(
                    type=indicator_type, **params
                )
            }
            engine = IndicatorEngine(indicators)

            assert (
                f"test_{indicator_type}" in engine._indicators
            ), f"Indicator type '{indicator_type}' should be created via registry"


class TestErrorMessages:
    """Tests for improved error messages using get_or_raise."""

    def test_unknown_type_error_message(self) -> None:
        """Error for unknown type should list available types from registry."""
        indicators = {"bad_ind": IndicatorDefinition(type="nonexistent_type")}

        with pytest.raises(ValueError) as exc_info:
            IndicatorEngine(indicators)

        error_msg = str(exc_info.value)
        assert "Unknown" in error_msg
        assert "nonexistent_type" in error_msg
        assert "Available" in error_msg

    def test_unknown_type_lists_registry_types(self) -> None:
        """Error message should list canonical types from registry."""
        indicators = {"bad_ind": IndicatorDefinition(type="does_not_exist")}

        with pytest.raises(ValueError) as exc_info:
            IndicatorEngine(indicators)

        error_msg = str(exc_info.value)
        # Should include some known registry types
        assert "rsi" in error_msg.lower()


class TestComputeWithRegistryIndicators:
    """Tests for compute() using registry-resolved indicators."""

    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        """Create sample OHLCV data."""
        return pd.DataFrame(
            {
                "open": [100.0 + i for i in range(100)],
                "high": [102.0 + i for i in range(100)],
                "low": [98.0 + i for i in range(100)],
                "close": [101.0 + i for i in range(100)],
                "volume": [1000 + i * 10 for i in range(100)],
            }
        )

    def test_compute_rsi_via_registry(self, sample_data: pd.DataFrame) -> None:
        """RSI compute should work via registry."""
        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}
        engine = IndicatorEngine(indicators)
        result = engine.compute(sample_data, {"rsi_14"})

        assert "rsi_14" in result.columns
        valid_values = result["rsi_14"].dropna()
        assert len(valid_values) > 0
        assert (valid_values >= 0).all()
        assert (valid_values <= 100).all()

    def test_compute_ema_via_registry(self, sample_data: pd.DataFrame) -> None:
        """EMA compute should work via registry (formerly used fallback)."""
        indicators = {"ema_20": IndicatorDefinition(type="ema", period=20)}
        engine = IndicatorEngine(indicators)
        result = engine.compute(sample_data, {"ema_20"})

        assert "ema_20" in result.columns
        valid_values = result["ema_20"].dropna()
        assert len(valid_values) > 0

    def test_compute_multi_output_indicator(self, sample_data: pd.DataFrame) -> None:
        """Multi-output indicators should work via registry."""
        indicators = {
            "bb_20": IndicatorDefinition(
                type="bollingerbands", period=20, multiplier=2.0
            )
        }
        engine = IndicatorEngine(indicators)
        result = engine.compute(sample_data, {"bb_20"})

        # Should have prefixed columns for multi-output
        assert "bb_20.upper" in result.columns
        assert "bb_20.middle" in result.columns
        assert "bb_20.lower" in result.columns
        # And alias for primary output
        assert "bb_20" in result.columns

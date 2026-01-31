"""Unit tests for IndicatorEngine registry integration.

Tests the registry-only lookup pattern (M2 complete):
- All indicator lookups use INDICATOR_REGISTRY
- Error messages list available types from registry
"""

import pandas as pd
import pytest

from ktrdr.config.models import IndicatorDefinition
from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY
from ktrdr.indicators.indicator_engine import IndicatorEngine
from ktrdr.indicators.rsi_indicator import RSIIndicator


class TestIndicatorEngineRegistryLookup:
    """Tests for registry-based indicator lookup."""

    def test_rsi_created_via_registry(self) -> None:
        """RSI should be created via INDICATOR_REGISTRY."""
        assert "rsi" in INDICATOR_REGISTRY

        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}
        engine = IndicatorEngine(indicators)

        # Should have created RSI indicator
        assert "rsi_14" in engine._indicators
        assert isinstance(engine._indicators["rsi_14"], RSIIndicator)

    def test_registry_case_variants_work(self) -> None:
        """All case variants should work via registry lookup."""
        case_variants = ["rsi", "RSI", "rsiindicator", "RSIIndicator"]

        for variant in case_variants:
            indicators = {"test_ind": IndicatorDefinition(type=variant, period=14)}
            engine = IndicatorEngine(indicators)

            assert "test_ind" in engine._indicators
            assert isinstance(
                engine._indicators["test_ind"], RSIIndicator
            ), f"Case variant '{variant}' should resolve to RSIIndicator"

    def test_ema_created_via_registry(self) -> None:
        """EMA should be created via INDICATOR_REGISTRY."""
        from ktrdr.indicators.ma_indicators import ExponentialMovingAverage

        assert "ema" in INDICATOR_REGISTRY

        indicators = {"ema_20": IndicatorDefinition(type="ema", period=20)}
        engine = IndicatorEngine(indicators)

        assert "ema_20" in engine._indicators
        assert isinstance(engine._indicators["ema_20"], ExponentialMovingAverage)

    def test_compute_works_for_registry_indicator(self) -> None:
        """compute() should work for registry-resolved indicators."""
        data = pd.DataFrame(
            {
                "open": [100.0] * 50,
                "high": [101.0] * 50,
                "low": [99.0] * 50,
                "close": [100.0] * 50,
                "volume": [1000] * 50,
            }
        )

        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}
        engine = IndicatorEngine(indicators)
        result = engine.compute(data, {"rsi_14"})

        # Should produce valid RSI column
        assert "rsi_14" in result.columns
        # RSI values should be between 0 and 100
        valid_values = result["rsi_14"].dropna()
        assert len(valid_values) > 0
        assert (valid_values >= 0).all()
        assert (valid_values <= 100).all()


class TestIndicatorEngineErrorMessages:
    """Tests for error messages from registry-only lookup."""

    def test_unknown_type_lists_available_types(self) -> None:
        """Error for unknown type should list available types from registry."""
        indicators = {"bad_ind": IndicatorDefinition(type="nonexistent_type")}

        with pytest.raises(ValueError, match="Unknown indicator type"):
            IndicatorEngine(indicators)

    def test_error_message_includes_rsi(self) -> None:
        """Error message should include 'rsi' in available types."""
        indicators = {"bad_ind": IndicatorDefinition(type="nonexistent_type")}

        with pytest.raises(ValueError) as exc_info:
            IndicatorEngine(indicators)

        error_msg = str(exc_info.value)
        # 'rsi' should be listed (from registry)
        assert "rsi" in error_msg.lower()

    def test_error_message_includes_available_keyword(self) -> None:
        """Error message should include 'Available' with type list."""
        indicators = {"bad_ind": IndicatorDefinition(type="nonexistent_type")}

        with pytest.raises(ValueError) as exc_info:
            IndicatorEngine(indicators)

        error_msg = str(exc_info.value)
        assert "Available" in error_msg

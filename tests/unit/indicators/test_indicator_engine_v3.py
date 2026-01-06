"""Unit tests for IndicatorEngine v3 functionality."""

import pytest

from ktrdr.config.models import IndicatorDefinition
from ktrdr.indicators.indicator_engine import IndicatorEngine


class TestIndicatorEngineV3Constructor:
    """Tests for IndicatorEngine v3 constructor accepting dict of IndicatorDefinition."""

    def test_constructor_accepts_dict_of_indicator_definition(self):
        """Constructor should accept dict mapping indicator_id to IndicatorDefinition."""
        indicators = {
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "ema_20": IndicatorDefinition(type="ema", period=20),
        }

        engine = IndicatorEngine(indicators)

        # Should create internal indicators dict
        assert hasattr(engine, "_indicators")
        assert "rsi_14" in engine._indicators
        assert "ema_20" in engine._indicators

    def test_creates_correct_indicator_instances_from_definitions(self):
        """Should instantiate correct indicator classes based on definition.type."""
        from ktrdr.indicators.ma_indicators import ExponentialMovingAverage
        from ktrdr.indicators.rsi_indicator import RSIIndicator

        indicators = {
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "ema_20": IndicatorDefinition(type="ema", period=20),
        }

        engine = IndicatorEngine(indicators)

        # Check indicator types
        assert isinstance(engine._indicators["rsi_14"], RSIIndicator)
        assert isinstance(engine._indicators["ema_20"], ExponentialMovingAverage)

    def test_indicator_with_extra_params_created_correctly(self):
        """Should pass extra params (period, multiplier) to indicator constructor."""
        from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator

        indicators = {
            "bbands_20_2": IndicatorDefinition(
                type="bbands", period=20, multiplier=2.0
            ),
        }

        engine = IndicatorEngine(indicators)

        # Check instance type
        bbands = engine._indicators["bbands_20_2"]
        assert isinstance(bbands, BollingerBandsIndicator)

        # Check params were set correctly (indicators store params in self.params dict)
        assert bbands.params["period"] == 20
        assert bbands.params["multiplier"] == 2.0

    def test_unknown_indicator_type_raises_clear_error(self):
        """Should raise ValueError with clear message for unknown indicator type."""
        indicators = {
            "unknown_ind": IndicatorDefinition(type="nonexistent_indicator"),
        }

        with pytest.raises(ValueError, match="Unknown indicator type"):
            IndicatorEngine(indicators)

    def test_empty_dict_creates_empty_engine(self):
        """Empty indicators dict should create engine with no indicators."""
        engine = IndicatorEngine({})

        assert len(engine._indicators) == 0

    def test_multiple_indicators_all_created(self):
        """All indicators in dict should be instantiated."""
        indicators = {
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "macd_12_26_9": IndicatorDefinition(
                type="macd", fast_period=12, slow_period=26, signal_period=9
            ),
            "bbands_20_2": IndicatorDefinition(
                type="bbands", period=20, multiplier=2.0
            ),
        }

        engine = IndicatorEngine(indicators)

        assert len(engine._indicators) == 3
        assert "rsi_14" in engine._indicators
        assert "macd_12_26_9" in engine._indicators
        assert "bbands_20_2" in engine._indicators

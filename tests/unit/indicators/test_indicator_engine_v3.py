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


class TestIndicatorEngineV3Compute:
    """Tests for IndicatorEngine.compute() method with v3 indicators."""

    def test_single_output_produces_indicator_id_column(self):
        """Single-output indicator should produce column named {indicator_id}."""
        import pandas as pd

        # Create sample data
        data = pd.DataFrame(
            {
                "open": [100] * 50,
                "high": [101] * 50,
                "low": [99] * 50,
                "close": [100] * 50,
                "volume": [1000] * 50,
            }
        )

        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}

        engine = IndicatorEngine(indicators)
        result = engine.compute(data, {"rsi_14"})

        # Should have rsi_14 column
        assert "rsi_14" in result.columns
        # Original columns should remain
        assert "close" in result.columns

    def test_multi_output_produces_dotted_columns(self):
        """Multi-output indicator should produce {indicator_id}.{output} columns."""
        import pandas as pd

        # Create sample data
        data = pd.DataFrame(
            {
                "open": [100] * 50,
                "high": [101] * 50,
                "low": [99] * 50,
                "close": [100] * 50,
                "volume": [1000] * 50,
            }
        )

        indicators = {
            "bbands_20_2": IndicatorDefinition(type="bbands", period=20, multiplier=2.0)
        }

        engine = IndicatorEngine(indicators)
        result = engine.compute(data, {"bbands_20_2"})

        # Should have dotted columns
        assert "bbands_20_2.upper" in result.columns
        assert "bbands_20_2.middle" in result.columns
        assert "bbands_20_2.lower" in result.columns

    def test_unknown_indicator_id_raises_error(self):
        """compute() should raise ValueError for unknown indicator_id."""
        import pandas as pd

        data = pd.DataFrame(
            {
                "open": [100] * 50,
                "high": [101] * 50,
                "low": [99] * 50,
                "close": [100] * 50,
                "volume": [1000] * 50,
            }
        )

        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}

        engine = IndicatorEngine(indicators)

        with pytest.raises(ValueError, match="Unknown indicator"):
            engine.compute(data, {"nonexistent_indicator"})

    def test_multiple_indicators_computed_in_single_call(self):
        """Should compute multiple indicators when multiple IDs provided."""
        import pandas as pd

        data = pd.DataFrame(
            {
                "open": [100] * 50,
                "high": [101] * 50,
                "low": [99] * 50,
                "close": [100] * 50,
                "volume": [1000] * 50,
            }
        )

        indicators = {
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "ema_20": IndicatorDefinition(type="ema", period=20),
        }

        engine = IndicatorEngine(indicators)
        result = engine.compute(data, {"rsi_14", "ema_20"})

        # Both indicators computed
        assert "rsi_14" in result.columns
        assert "ema_20" in result.columns

    def test_no_timeframe_prefix_in_compute(self):
        """compute() should NOT add timeframe prefix (that's for compute_for_timeframe)."""
        import pandas as pd

        data = pd.DataFrame(
            {
                "open": [100] * 50,
                "high": [101] * 50,
                "low": [99] * 50,
                "close": [100] * 50,
                "volume": [1000] * 50,
            }
        )

        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}

        engine = IndicatorEngine(indicators)
        result = engine.compute(data, {"rsi_14"})

        # Should be "rsi_14", NOT "5m_rsi_14" or similar
        assert "rsi_14" in result.columns
        assert not any(col.startswith("5m_") for col in result.columns)
        assert not any(col.startswith("1h_") for col in result.columns)


class TestIndicatorEngineV3ComputeForTimeframe:
    """Tests for IndicatorEngine.compute_for_timeframe() method."""

    def test_timeframe_prefix_added_to_indicator_columns(self):
        """Should add timeframe prefix to indicator columns."""
        import pandas as pd

        data = pd.DataFrame(
            {
                "open": [100] * 30,
                "high": [101] * 30,
                "low": [99] * 30,
                "close": [100] * 30,
                "volume": [1000] * 30,
            }
        )

        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}

        engine = IndicatorEngine(indicators)
        result = engine.compute_for_timeframe(data, "5m", {"rsi_14"})

        # Should have prefixed column
        assert "5m_rsi_14" in result.columns

    def test_ohlcv_columns_not_prefixed(self):
        """OHLCV columns should remain unprefixed."""
        import pandas as pd

        data = pd.DataFrame(
            {
                "open": [100] * 30,
                "high": [101] * 30,
                "low": [99] * 30,
                "close": [100] * 30,
                "volume": [1000] * 30,
            }
        )

        indicators = {"rsi_14": IndicatorDefinition(type="rsi", period=14)}

        engine = IndicatorEngine(indicators)
        result = engine.compute_for_timeframe(data, "5m", {"rsi_14"})

        # OHLCV columns should remain unprefixed
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns
        assert "volume" in result.columns

        # No prefixed OHLCV columns
        assert "5m_open" not in result.columns
        assert "5m_close" not in result.columns

    def test_works_with_single_output_indicator(self):
        """Should work correctly with single-output indicators."""
        import pandas as pd

        data = pd.DataFrame(
            {
                "open": [100] * 30,
                "high": [101] * 30,
                "low": [99] * 30,
                "close": [100] * 30,
                "volume": [1000] * 30,
            }
        )

        indicators = {"ema_20": IndicatorDefinition(type="ema", period=20)}

        engine = IndicatorEngine(indicators)
        result = engine.compute_for_timeframe(data, "1h", {"ema_20"})

        assert "1h_ema_20" in result.columns

    def test_works_with_multi_output_indicator(self):
        """Should work correctly with multi-output indicators."""
        import pandas as pd

        data = pd.DataFrame(
            {
                "open": [100] * 30,
                "high": [101] * 30,
                "low": [99] * 30,
                "close": [100] * 30,
                "volume": [1000] * 30,
            }
        )

        indicators = {
            "bbands_20_2": IndicatorDefinition(type="bbands", period=20, multiplier=2.0)
        }

        engine = IndicatorEngine(indicators)
        result = engine.compute_for_timeframe(data, "15m", {"bbands_20_2"})

        # Should have prefixed dotted columns
        assert "15m_bbands_20_2.upper" in result.columns
        assert "15m_bbands_20_2.middle" in result.columns
        assert "15m_bbands_20_2.lower" in result.columns

    def test_multiple_indicators_all_prefixed(self):
        """Should prefix all indicators when multiple computed."""
        import pandas as pd

        data = pd.DataFrame(
            {
                "open": [100] * 30,
                "high": [101] * 30,
                "low": [99] * 30,
                "close": [100] * 30,
                "volume": [1000] * 30,
            }
        )

        indicators = {
            "rsi_14": IndicatorDefinition(type="rsi", period=14),
            "ema_20": IndicatorDefinition(type="ema", period=20),
        }

        engine = IndicatorEngine(indicators)
        result = engine.compute_for_timeframe(data, "5m", {"rsi_14", "ema_20"})

        # Both should be prefixed
        assert "5m_rsi_14" in result.columns
        assert "5m_ema_20" in result.columns

        # Unprefixed versions should NOT exist
        assert "rsi_14" not in result.columns
        assert "ema_20" not in result.columns

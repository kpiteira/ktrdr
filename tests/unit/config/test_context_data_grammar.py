"""Tests for context_data grammar extension (Task 6.4).

Tests ContextDataEntry model validation and strategy validation
of data_source references against context_data declarations.
"""

import pytest
from pydantic import ValidationError

from ktrdr.config.models import ContextDataEntry, StrategyConfigurationV3

# -- Helper to build minimal valid v3 strategy config --


def _make_strategy(**overrides) -> dict:
    """Build a minimal valid v3 strategy config dict."""
    base = {
        "name": "test_strategy",
        "version": "3.0",
        "training_data": {
            "symbols": {"mode": "single", "symbol": "EURUSD"},
            "timeframes": {"mode": "single", "timeframe": "1h"},
            "history_required": 200,
        },
        "indicators": {
            "rsi_14": {"type": "rsi", "period": 14},
        },
        "fuzzy_sets": {
            "rsi_momentum": {
                "indicator": "rsi_14",
                "oversold": [0, 25, 40],
                "neutral": [30, 50, 70],
                "overbought": [60, 75, 100],
            },
        },
        "nn_inputs": [{"fuzzy_set": "rsi_momentum", "timeframes": "all"}],
        "model": {"type": "mlp", "hidden_layers": [32, 16]},
        "decisions": {"mode": "classification", "output_format": "classification"},
        "training": {"epochs": 10, "batch_size": 32},
    }
    base.update(overrides)
    return base


class TestContextDataEntry:
    """Test ContextDataEntry Pydantic model."""

    def test_fred_provider_valid(self):
        """FRED provider with series validates."""
        entry = ContextDataEntry(
            provider="fred",
            series=["DGS2", "IRLTLT01DEM156N"],
            frequency="daily",
        )
        assert entry.provider == "fred"
        assert entry.series == ["DGS2", "IRLTLT01DEM156N"]
        assert entry.alignment == "forward_fill"  # default

    def test_ib_provider_valid(self):
        """IB provider with symbol/timeframe validates."""
        entry = ContextDataEntry(
            provider="ib",
            symbol="GBPUSD",
            timeframe="1h",
            instrument_type="FOREX",
        )
        assert entry.provider == "ib"
        assert entry.symbol == "GBPUSD"

    def test_provider_required(self):
        """Provider field is required."""
        with pytest.raises(ValidationError, match="provider"):
            ContextDataEntry()

    def test_alignment_defaults_to_forward_fill(self):
        """Alignment should default to forward_fill."""
        entry = ContextDataEntry(provider="fred", series="DGS2")
        assert entry.alignment == "forward_fill"

    def test_single_series_string(self):
        """Series can be a single string."""
        entry = ContextDataEntry(provider="fred", series="DGS2")
        assert entry.series == "DGS2"

    def test_series_list(self):
        """Series can be a list of strings."""
        entry = ContextDataEntry(
            provider="fred", series=["DGS2", "IRLTLT01DEM156N"]
        )
        assert entry.series == ["DGS2", "IRLTLT01DEM156N"]


class TestStrategyWithContextData:
    """Test StrategyConfigurationV3 with context_data field."""

    def test_strategy_without_context_data_still_valid(self):
        """Existing strategies without context_data should validate unchanged."""
        config = StrategyConfigurationV3(**_make_strategy())
        assert config.context_data is None

    def test_strategy_with_context_data(self):
        """Strategy with context_data section should parse."""
        data = _make_strategy(
            context_data=[
                {
                    "provider": "fred",
                    "series": ["DGS2", "IRLTLT01DEM156N"],
                    "frequency": "daily",
                },
            ]
        )
        config = StrategyConfigurationV3(**data)
        assert config.context_data is not None
        assert len(config.context_data) == 1
        assert config.context_data[0].provider == "fred"

    def test_data_source_on_indicator_passes_through(self):
        """data_source field on indicator should be accessible via model_extra."""
        data = _make_strategy(
            indicators={
                "rsi_14": {"type": "rsi", "period": 14},
                "yield_rsi": {
                    "type": "rsi",
                    "period": 14,
                    "data_source": "yield_spread_DGS2_IRLTLT01DEM156N",
                },
            },
        )
        config = StrategyConfigurationV3(**data)
        # data_source should be in model_extra
        yield_rsi = config.indicators["yield_rsi"]
        assert yield_rsi.model_extra.get("data_source") == "yield_spread_DGS2_IRLTLT01DEM156N"

    def test_data_source_and_source_coexist(self):
        """data_source and source (RSI column param) should not collide."""
        data = _make_strategy(
            indicators={
                "rsi_14": {
                    "type": "rsi",
                    "period": 14,
                    "source": "close",
                    "data_source": "fred_DGS2",
                },
            },
        )
        config = StrategyConfigurationV3(**data)
        ind = config.indicators["rsi_14"]
        assert ind.model_extra.get("source") == "close"
        assert ind.model_extra.get("data_source") == "fred_DGS2"


class TestContextDataValidation:
    """Test strategy validation of data_source references."""

    def test_valid_data_source_reference(self):
        """data_source matching a context_data source ID should validate."""
        from ktrdr.config.strategy_validator import validate_v3_strategy

        data = _make_strategy(
            context_data=[
                {
                    "provider": "fred",
                    "series": ["DGS2", "IRLTLT01DEM156N"],
                    "frequency": "daily",
                },
            ],
            indicators={
                "rsi_14": {"type": "rsi", "period": 14},
                "yield_rsi": {
                    "type": "rsi",
                    "period": 14,
                    "data_source": "yield_spread_DGS2_IRLTLT01DEM156N",
                },
            },
            fuzzy_sets={
                "rsi_momentum": {
                    "indicator": "rsi_14",
                    "oversold": [0, 25, 40],
                    "overbought": [60, 75, 100],
                },
                "carry_direction": {
                    "indicator": "yield_rsi",
                    "widening": [60, 75, 100],
                    "narrowing": [0, 25, 40],
                },
            },
            nn_inputs=[
                {"fuzzy_set": "rsi_momentum", "timeframes": "all"},
                {"fuzzy_set": "carry_direction", "timeframes": "all"},
            ],
        )
        config = StrategyConfigurationV3(**data)
        # Should not raise
        warnings = validate_v3_strategy(config)
        # May have warnings but no errors
        assert isinstance(warnings, list)

    def test_invalid_data_source_reference(self):
        """data_source referencing undeclared context data should fail validation."""
        from ktrdr.config.strategy_validator import (
            StrategyValidationError,
            validate_v3_strategy,
        )

        data = _make_strategy(
            indicators={
                "rsi_14": {"type": "rsi", "period": 14},
                "yield_rsi": {
                    "type": "rsi",
                    "period": 14,
                    "data_source": "nonexistent_source",
                },
            },
            fuzzy_sets={
                "rsi_momentum": {
                    "indicator": "rsi_14",
                    "oversold": [0, 25, 40],
                    "overbought": [60, 75, 100],
                },
                "carry": {
                    "indicator": "yield_rsi",
                    "up": [60, 75, 100],
                    "down": [0, 25, 40],
                },
            },
            nn_inputs=[
                {"fuzzy_set": "rsi_momentum", "timeframes": "all"},
                {"fuzzy_set": "carry", "timeframes": "all"},
            ],
        )
        config = StrategyConfigurationV3(**data)
        with pytest.raises(StrategyValidationError, match="data_source"):
            validate_v3_strategy(config)

    def test_unused_context_data_warns(self):
        """Declared but unused context_data should produce a warning."""
        from ktrdr.config.strategy_validator import validate_v3_strategy

        data = _make_strategy(
            context_data=[
                {
                    "provider": "fred",
                    "series": "DGS2",
                },
            ],
        )
        config = StrategyConfigurationV3(**data)
        warnings = validate_v3_strategy(config)
        warning_messages = [w.message for w in warnings]
        assert any("context_data" in m.lower() for m in warning_messages)

    def test_no_context_data_no_warnings(self):
        """Strategy without context_data should not produce context warnings."""
        from ktrdr.config.strategy_validator import validate_v3_strategy

        data = _make_strategy()
        config = StrategyConfigurationV3(**data)
        warnings = validate_v3_strategy(config)
        context_warnings = [w for w in warnings if "context_data" in w.message.lower()]
        assert len(context_warnings) == 0

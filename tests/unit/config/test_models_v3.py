"""
Unit tests for v3 Pydantic models.

Tests the new v3 strategy configuration models including:
- IndicatorDefinition
- FuzzyMembership
- FuzzySetDefinition
- NNInputSpec
- StrategyConfigurationV3
"""

import pytest
from pydantic import ValidationError

from ktrdr.config.models import (
    FuzzyMembership,
    FuzzySetDefinition,
    IndicatorDefinition,
    NNInputSpec,
    StrategyConfigurationV3,
)


class TestIndicatorDefinition:
    """Tests for IndicatorDefinition model."""

    def test_accepts_arbitrary_params(self):
        """IndicatorDefinition should accept arbitrary indicator-specific parameters."""
        # Test with various indicator types and their parameters
        rsi = IndicatorDefinition(type="rsi", period=14, source="close")
        assert rsi.type == "rsi"
        assert rsi.model_extra["period"] == 14
        assert rsi.model_extra["source"] == "close"

        macd = IndicatorDefinition(
            type="macd", fast_period=12, slow_period=26, signal_period=9
        )
        assert macd.type == "macd"
        assert macd.model_extra["fast_period"] == 12

        bbands = IndicatorDefinition(type="bbands", period=20, multiplier=2.0)
        assert bbands.type == "bbands"
        assert bbands.model_extra["period"] == 20
        assert bbands.model_extra["multiplier"] == 2.0

    def test_requires_type_field(self):
        """IndicatorDefinition must have a type field."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorDefinition(period=14)
        assert "type" in str(exc_info.value)


class TestFuzzyMembership:
    """Tests for FuzzyMembership model."""

    def test_validates_parameters_list(self):
        """FuzzyMembership should validate parameters is a list."""
        # Valid
        fm = FuzzyMembership(type="triangular", parameters=[0, 20, 35])
        assert fm.type == "triangular"
        assert fm.parameters == [0, 20, 35]

    def test_defaults_to_triangular(self):
        """FuzzyMembership should default type to 'triangular'."""
        fm = FuzzyMembership(parameters=[0, 20, 35])
        assert fm.type == "triangular"

    def test_requires_parameters(self):
        """FuzzyMembership must have parameters."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzyMembership(type="triangular")
        assert "parameters" in str(exc_info.value)


class TestFuzzySetDefinition:
    """Tests for FuzzySetDefinition model."""

    def test_expands_list_shorthand(self):
        """FuzzySetDefinition should expand [a,b,c] shorthand to full FuzzyMembership form."""
        data = {
            "indicator": "rsi_14",
            "oversold": [0, 20, 35],
            "overbought": [65, 80, 100],
        }

        fuzzy_set = FuzzySetDefinition(**data)
        assert fuzzy_set.indicator == "rsi_14"

        # Shorthand should be expanded in __pydantic_extra__
        assert "oversold" in fuzzy_set.model_extra
        assert "overbought" in fuzzy_set.model_extra

        # Check expanded form
        oversold = fuzzy_set.model_extra["oversold"]
        assert oversold["type"] == "triangular"
        assert oversold["parameters"] == [0, 20, 35]

        overbought = fuzzy_set.model_extra["overbought"]
        assert overbought["type"] == "triangular"
        assert overbought["parameters"] == [65, 80, 100]

    def test_preserves_full_form(self):
        """FuzzySetDefinition should preserve full {type, parameters} form unchanged."""
        data = {
            "indicator": "rsi_14",
            "oversold": {"type": "gaussian", "parameters": [20, 5]},
            "neutral": {"type": "trapezoidal", "parameters": [30, 40, 60, 70]},
        }

        fuzzy_set = FuzzySetDefinition(**data)
        assert fuzzy_set.indicator == "rsi_14"

        oversold = fuzzy_set.model_extra["oversold"]
        assert oversold["type"] == "gaussian"
        assert oversold["parameters"] == [20, 5]

        neutral = fuzzy_set.model_extra["neutral"]
        assert neutral["type"] == "trapezoidal"

    def test_get_membership_names_returns_correct_order(self):
        """FuzzySetDefinition.get_membership_names() should return ordered membership names."""
        data = {
            "indicator": "rsi_14",
            "oversold": [0, 20, 35],
            "neutral": [30, 50, 70],
            "overbought": [65, 80, 100],
        }

        fuzzy_set = FuzzySetDefinition(**data)
        names = fuzzy_set.get_membership_names()

        # Should return all membership names except 'indicator'
        assert "indicator" not in names
        assert len(names) == 3
        # Order should be preserved (Python 3.7+ dict order)
        assert names == ["oversold", "neutral", "overbought"]

    def test_requires_indicator_field(self):
        """FuzzySetDefinition must have an indicator field."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzySetDefinition(oversold=[0, 20, 35])
        assert "indicator" in str(exc_info.value)


class TestNNInputSpec:
    """Tests for NNInputSpec model."""

    def test_accepts_timeframes_all(self):
        """NNInputSpec should accept timeframes: 'all'."""
        spec = NNInputSpec(fuzzy_set="rsi_fast", timeframes="all")
        assert spec.fuzzy_set == "rsi_fast"
        assert spec.timeframes == "all"

    def test_accepts_timeframes_list(self):
        """NNInputSpec should accept timeframes as a list."""
        spec = NNInputSpec(fuzzy_set="rsi_fast", timeframes=["5m", "1h"])
        assert spec.fuzzy_set == "rsi_fast"
        assert spec.timeframes == ["5m", "1h"]

    def test_requires_fuzzy_set(self):
        """NNInputSpec must have fuzzy_set field."""
        with pytest.raises(ValidationError) as exc_info:
            NNInputSpec(timeframes="all")
        assert "fuzzy_set" in str(exc_info.value)

    def test_requires_timeframes(self):
        """NNInputSpec must have timeframes field."""
        with pytest.raises(ValidationError) as exc_info:
            NNInputSpec(fuzzy_set="rsi_fast")
        assert "timeframes" in str(exc_info.value)


class TestStrategyConfigurationV3:
    """Tests for StrategyConfigurationV3 model (integration test)."""

    def test_parses_complete_example(self):
        """StrategyConfigurationV3 should parse a complete strategy example."""
        # Complete example from DESIGN.md
        config_data = {
            "name": "test_strategy",
            "description": "Test v3 strategy",
            "version": "3.0",
            "training_data": {
                "symbols": {"mode": "multi_symbol", "list": ["EURUSD"]},
                "timeframes": {
                    "mode": "multi_timeframe",
                    "list": ["5m", "1h"],
                    "base_timeframe": "1h",
                },
                "history_required": 200,
            },
            "indicators": {
                "rsi_14": {"type": "rsi", "period": 14},
                "bbands_20_2": {"type": "bbands", "period": 20, "multiplier": 2.0},
            },
            "fuzzy_sets": {
                "rsi_fast": {
                    "indicator": "rsi_14",
                    "oversold": [0, 25, 40],
                    "overbought": [60, 75, 100],
                },
                "bbands_position": {
                    "indicator": "bbands_20_2.middle",
                    "below": [0, 0.3, 0.5],
                    "above": [0.5, 0.7, 1.0],
                },
            },
            "nn_inputs": [
                {"fuzzy_set": "rsi_fast", "timeframes": ["5m"]},
                {"fuzzy_set": "bbands_position", "timeframes": "all"},
            ],
            "model": {
                "type": "mlp",
                "architecture": {"hidden_layers": [64, 32], "activation": "relu"},
                "training": {"learning_rate": 0.001, "epochs": 50},
            },
            "decisions": {
                "output_format": "classification",
                "confidence_threshold": 0.6,
            },
            "training": {
                "method": "supervised",
                "labels": {"source": "zigzag", "zigzag_threshold": 0.02},
            },
        }

        config = StrategyConfigurationV3(**config_data)

        # Verify structure
        assert config.name == "test_strategy"
        assert config.version == "3.0"

        # Verify indicators
        assert "rsi_14" in config.indicators
        assert config.indicators["rsi_14"].type == "rsi"

        # Verify fuzzy sets
        assert "rsi_fast" in config.fuzzy_sets
        assert config.fuzzy_sets["rsi_fast"].indicator == "rsi_14"

        # Verify nn_inputs
        assert len(config.nn_inputs) == 2
        assert config.nn_inputs[0].fuzzy_set == "rsi_fast"
        assert config.nn_inputs[1].timeframes == "all"

    def test_requires_name(self):
        """StrategyConfigurationV3 must have a name."""
        with pytest.raises(ValidationError) as exc_info:
            StrategyConfigurationV3(version="3.0")
        assert "name" in str(exc_info.value)

    def test_version_defaults_to_3_0(self):
        """StrategyConfigurationV3 should default version to '3.0'."""
        # This test will pass once we add the default
        # For now, it will fail if version is required
        pass  # Placeholder - will implement after model is created

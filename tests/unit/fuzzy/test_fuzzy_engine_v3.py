"""
Unit tests for FuzzyEngine v3 constructor and methods.

Tests the v3 API where FuzzyEngine accepts dict[str, FuzzySetDefinition]
instead of FuzzyConfig.
"""

import pytest
from pydantic import ValidationError

from ktrdr.config.models import FuzzySetDefinition
from ktrdr.fuzzy.engine import FuzzyEngine


class TestFuzzyEngineV3Constructor:
    """Test FuzzyEngine v3 constructor."""

    def test_constructor_accepts_dict_of_fuzzy_set_definitions(self):
        """Constructor accepts dict[str, FuzzySetDefinition]."""
        fuzzy_sets = {
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                oversold={"type": "triangular", "parameters": [0, 25, 40]},
                overbought={"type": "triangular", "parameters": [60, 75, 100]},
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)

        assert engine is not None
        assert hasattr(engine, "_fuzzy_sets")
        assert hasattr(engine, "_indicator_map")

    def test_builds_membership_functions_correctly(self):
        """Builds membership functions from FuzzySetDefinition."""
        fuzzy_sets = {
            "rsi_momentum": FuzzySetDefinition(
                indicator="rsi_14",
                oversold={"type": "triangular", "parameters": [0, 20, 35]},
                neutral={"type": "triangular", "parameters": [30, 50, 70]},
                overbought={"type": "triangular", "parameters": [65, 80, 100]},
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)

        # Should have internal fuzzy_sets dict
        assert "rsi_momentum" in engine._fuzzy_sets
        fuzzy_set = engine._fuzzy_sets["rsi_momentum"]

        # Should have three membership functions
        assert len(fuzzy_set) == 3
        assert "oversold" in fuzzy_set
        assert "neutral" in fuzzy_set
        assert "overbought" in fuzzy_set

    def test_get_indicator_for_fuzzy_set_returns_correct_indicator(self):
        """get_indicator_for_fuzzy_set() returns correct indicator_id."""
        fuzzy_sets = {
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                overbought=[60, 75, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)

        assert engine.get_indicator_for_fuzzy_set("rsi_fast") == "rsi_14"

    def test_multiple_fuzzy_sets_referencing_same_indicator(self):
        """Multiple fuzzy sets can reference the same indicator."""
        fuzzy_sets = {
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                overbought=[60, 75, 100],
            ),
            "rsi_slow": FuzzySetDefinition(
                indicator="rsi_14",  # Same indicator, different interpretation
                oversold=[0, 15, 25],
                overbought=[75, 85, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)

        # Both fuzzy sets should reference the same indicator
        assert engine.get_indicator_for_fuzzy_set("rsi_fast") == "rsi_14"
        assert engine.get_indicator_for_fuzzy_set("rsi_slow") == "rsi_14"

        # But should have different membership functions
        assert "rsi_fast" in engine._fuzzy_sets
        assert "rsi_slow" in engine._fuzzy_sets
        assert engine._fuzzy_sets["rsi_fast"] != engine._fuzzy_sets["rsi_slow"]

    def test_dot_notation_indicator_reference_preserved(self):
        """Dot notation indicator references are preserved (e.g., bbands_20_2.upper)."""
        fuzzy_sets = {
            "bbands_upper": FuzzySetDefinition(
                indicator="bbands_20_2.upper",  # Multi-output indicator with dot notation
                near_price=[0.98, 1.0, 1.02],
                far_price=[1.05, 1.1, 1.2],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)

        # Should preserve full dot notation reference
        assert engine.get_indicator_for_fuzzy_set("bbands_upper") == "bbands_20_2.upper"

    def test_handles_both_shorthand_and_explicit_membership_format(self):
        """Handles both shorthand [a,b,c] and explicit {type, parameters} formats."""
        fuzzy_sets = {
            "rsi_mixed": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 20, 35],  # Shorthand
                overbought={
                    "type": "triangular",
                    "parameters": [65, 80, 100],
                },  # Explicit
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)

        # Both formats should create membership functions
        fuzzy_set = engine._fuzzy_sets["rsi_mixed"]
        assert "oversold" in fuzzy_set
        assert "overbought" in fuzzy_set

    def test_supports_trapezoidal_membership_functions(self):
        """Supports trapezoidal membership function type."""
        fuzzy_sets = {
            "rsi_trap": FuzzySetDefinition(
                indicator="rsi_14",
                oversold={"type": "trapezoidal", "parameters": [0, 10, 25, 35]},
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)

        fuzzy_set = engine._fuzzy_sets["rsi_trap"]
        assert "oversold" in fuzzy_set

    def test_empty_fuzzy_sets_dict_raises_error(self):
        """Empty fuzzy_sets dict raises appropriate error."""
        from ktrdr.errors import ConfigurationError

        with pytest.raises(ConfigurationError):
            FuzzyEngine({})

    def test_invalid_fuzzy_set_definition_raises_error(self):
        """Invalid FuzzySetDefinition raises error during construction."""
        # This should fail at Pydantic validation level
        with pytest.raises(ValidationError):
            fuzzy_sets = {
                "invalid": FuzzySetDefinition(
                    # Missing required 'indicator' field
                    oversold=[0, 20, 35],
                ),
            }
            FuzzyEngine(fuzzy_sets)

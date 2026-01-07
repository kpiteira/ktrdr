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


class TestFuzzyEngineV3Fuzzify:
    """Test FuzzyEngine v3 fuzzify() method."""

    def test_fuzzify_returns_dataframe_with_correct_columns(self):
        """fuzzify() returns DataFrame with {fuzzy_set_id}_{membership} columns."""
        import pandas as pd

        fuzzy_sets = {
            "rsi_momentum": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 20, 35],
                overbought=[65, 80, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        values = pd.Series([25, 50, 75])
        result = engine.fuzzify("rsi_momentum", values)

        # Should return DataFrame
        assert isinstance(result, pd.DataFrame)

        # Should have columns with fuzzy_set_id prefix (not indicator prefix)
        assert "rsi_momentum_oversold" in result.columns
        assert "rsi_momentum_overbought" in result.columns

    def test_column_names_follow_fuzzy_set_id_membership_pattern(self):
        """Column names follow {fuzzy_set_id}_{membership} pattern."""
        import pandas as pd

        fuzzy_sets = {
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                neutral=[35, 50, 65],
                overbought=[60, 75, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        values = pd.Series([30, 50, 70])
        result = engine.fuzzify("rsi_fast", values)

        # All columns should have fuzzy_set_id prefix
        expected_columns = [
            "rsi_fast_oversold",
            "rsi_fast_neutral",
            "rsi_fast_overbought",
        ]
        assert list(result.columns) == expected_columns

    def test_unknown_fuzzy_set_id_raises_valueerror(self):
        """Unknown fuzzy_set_id raises ValueError."""
        import pandas as pd

        fuzzy_sets = {
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                overbought=[60, 75, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        values = pd.Series([30, 50, 70])

        with pytest.raises(ValueError, match="Unknown fuzzy set"):
            engine.fuzzify("nonexistent_fuzzy_set", values)

    def test_membership_values_computed_correctly_triangular(self):
        """Membership values are computed correctly for triangular functions."""
        import pandas as pd

        fuzzy_sets = {
            "rsi_test": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],  # Triangular: peak at 25
                overbought=[60, 75, 100],  # Triangular: peak at 75
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        values = pd.Series([0, 25, 40, 60, 75, 100])
        result = engine.fuzzify("rsi_test", values)

        # At value 0: oversold should be 0.0 (at left edge), overbought should be 0.0
        assert result.loc[0, "rsi_test_oversold"] == pytest.approx(0.0)
        assert result.loc[0, "rsi_test_overbought"] == pytest.approx(0.0)

        # At value 25 (peak): oversold should be 1.0
        assert result.loc[1, "rsi_test_oversold"] == pytest.approx(1.0)

        # At value 75 (peak): overbought should be 1.0
        assert result.loc[4, "rsi_test_overbought"] == pytest.approx(1.0)

    def test_membership_values_computed_correctly_trapezoidal(self):
        """Membership values are computed correctly for trapezoidal functions."""
        import pandas as pd

        fuzzy_sets = {
            "rsi_trap": FuzzySetDefinition(
                indicator="rsi_14",
                oversold={"type": "trapezoidal", "parameters": [0, 10, 25, 35]},
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        values = pd.Series([0, 15, 30, 40])
        result = engine.fuzzify("rsi_trap", values)

        # At value 0: should be 0.0 (at left edge)
        assert result.loc[0, "rsi_trap_oversold"] == pytest.approx(0.0)

        # At value 15: should be 1.0 (in flat top between b=10 and c=25)
        assert result.loc[1, "rsi_trap_oversold"] == pytest.approx(1.0)

        # At value 30: should be between 0 and 1 (descending slope c < x < d)
        # Expected: (d - x) / (d - c) = (35 - 30) / (35 - 25) = 5/10 = 0.5
        assert result.loc[2, "rsi_trap_oversold"] == pytest.approx(0.5)

    def test_nan_handling_in_indicator_values(self):
        """NaN values in indicator_values are handled correctly."""
        import numpy as np
        import pandas as pd

        fuzzy_sets = {
            "rsi_test": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                overbought=[60, 75, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        values = pd.Series([25, np.nan, 75])
        result = engine.fuzzify("rsi_test", values)

        # First value should be computed
        assert not pd.isna(result.loc[0, "rsi_test_oversold"])

        # Second value should be NaN
        assert pd.isna(result.loc[1, "rsi_test_oversold"])

        # Third value should be computed
        assert not pd.isna(result.loc[2, "rsi_test_overbought"])

    def test_multiple_fuzzy_sets_same_indicator_different_columns(self):
        """Multiple fuzzy sets referencing same indicator produce different columns."""
        import pandas as pd

        fuzzy_sets = {
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                overbought=[60, 75, 100],
            ),
            "rsi_slow": FuzzySetDefinition(
                indicator="rsi_14",  # Same indicator
                oversold=[0, 15, 25],
                overbought=[75, 85, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        values = pd.Series([20, 50, 80])

        # Fuzzify with rsi_fast
        result_fast = engine.fuzzify("rsi_fast", values)
        assert "rsi_fast_oversold" in result_fast.columns
        assert "rsi_fast_overbought" in result_fast.columns

        # Fuzzify with rsi_slow
        result_slow = engine.fuzzify("rsi_slow", values)
        assert "rsi_slow_oversold" in result_slow.columns
        assert "rsi_slow_overbought" in result_slow.columns

        # The membership values should be different (different thresholds)
        assert (
            result_fast.loc[0, "rsi_fast_oversold"]
            != result_slow.loc[0, "rsi_slow_oversold"]
        )

    def test_no_timeframe_prefix_in_column_names(self):
        """Column names do NOT include timeframe prefix (caller responsibility)."""
        import pandas as pd

        fuzzy_sets = {
            "rsi_momentum": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 20, 35],
                overbought=[65, 80, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        values = pd.Series([30, 50, 70])
        result = engine.fuzzify("rsi_momentum", values)

        # Columns should NOT have timeframe prefix like "1h_" or "15m_"
        for col in result.columns:
            assert not col.startswith("1h_")
            assert not col.startswith("15m_")
            assert not col.startswith("4h_")

        # Columns should start with fuzzy_set_id
        for col in result.columns:
            assert col.startswith("rsi_momentum_")


class TestFuzzyEngineV3GetMembershipNames:
    """Test FuzzyEngine v3 get_membership_names() method."""

    def test_returns_correct_membership_names(self):
        """get_membership_names() returns correct membership names."""
        fuzzy_sets = {
            "rsi_momentum": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 20, 35],
                neutral=[30, 50, 70],
                overbought=[65, 80, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        names = engine.get_membership_names("rsi_momentum")

        assert "oversold" in names
        assert "neutral" in names
        assert "overbought" in names
        assert len(names) == 3

    def test_order_matches_definition_order(self):
        """Membership names are returned in definition order."""
        fuzzy_sets = {
            "rsi_ordered": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 20, 35],
                neutral=[30, 50, 70],
                overbought=[65, 80, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        names = engine.get_membership_names("rsi_ordered")

        # The order should match definition order
        expected = ["oversold", "neutral", "overbought"]
        assert names == expected

    def test_unknown_fuzzy_set_id_raises_valueerror(self):
        """Unknown fuzzy_set_id raises ValueError."""
        fuzzy_sets = {
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                overbought=[60, 75, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)

        with pytest.raises(ValueError, match="Unknown fuzzy set"):
            engine.get_membership_names("nonexistent_fuzzy_set")

    def test_v2_mode_raises_valueerror(self):
        """get_membership_names() raises ValueError in v2 mode."""
        from ktrdr.fuzzy.config import FuzzyConfigLoader

        # Create v2 FuzzyConfig
        v2_config_dict = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0, 30, 50]},
                "high": {"type": "triangular", "parameters": [50, 70, 100]},
            }
        }
        v2_config = FuzzyConfigLoader.load_from_dict(v2_config_dict)
        engine = FuzzyEngine(v2_config)

        with pytest.raises(ValueError, match="only available in v3 mode"):
            engine.get_membership_names("rsi")

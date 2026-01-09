"""
Unit tests for IndicatorEngine adapter layer (M2).

Tests the compute_indicator() method which handles both old-format
and new-format indicator outputs during the transition to v3.
"""

import pandas as pd
import pytest

from ktrdr.indicators import IndicatorEngine
from ktrdr.indicators.base_indicator import BaseIndicator


class MockSingleOutputIndicator(BaseIndicator):
    """Mock indicator returning single output (Series)."""

    @classmethod
    def is_multi_output(cls) -> bool:
        return False

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Single-output indicators return an empty list (no named outputs)."""
        return []

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Return Series (single output)."""
        return pd.Series([1.0, 2.0, 3.0], index=df.index)


class MockOldFormatIndicator(BaseIndicator):
    """Mock indicator returning old-format columns (params in names)."""

    @classmethod
    def is_multi_output(cls) -> bool:
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        return ["upper", "middle", "lower"]

    @classmethod
    def get_primary_output(cls) -> str:
        return "upper"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """OLD FORMAT: params in column names."""
        return pd.DataFrame(
            {
                "upper_20_2.0": [1.0, 1.0, 1.0],
                "middle_20_2.0": [0.5, 0.5, 0.5],
                "lower_20_2.0": [0.0, 0.0, 0.0],
            },
            index=df.index,
        )


class MockNewFormatIndicator(BaseIndicator):
    """Mock indicator returning new-format columns (semantic only)."""

    @classmethod
    def is_multi_output(cls) -> bool:
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        return ["upper", "middle", "lower"]

    @classmethod
    def get_primary_output(cls) -> str:
        return "upper"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """NEW FORMAT: semantic names only."""
        return pd.DataFrame(
            {
                "upper": [1.0, 1.0, 1.0],
                "middle": [0.5, 0.5, 0.5],
                "lower": [0.0, 0.0, 0.0],
            },
            index=df.index,
        )


@pytest.fixture
def sample_data():
    """Sample OHLCV data for testing."""
    return pd.DataFrame({"close": [100, 101, 102]})


class TestComputeIndicatorSingleOutput:
    """Tests for single-output indicators."""

    def test_single_output_returns_dataframe_with_indicator_id(self, sample_data):
        """Single-output indicator returns DataFrame with indicator_id column."""
        engine = IndicatorEngine()
        indicator = MockSingleOutputIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "rsi_14")

        # Should return DataFrame
        assert isinstance(result, pd.DataFrame)
        # Should have single column named indicator_id
        assert list(result.columns) == ["rsi_14"]
        # Should have correct values
        assert result["rsi_14"].tolist() == [1.0, 2.0, 3.0]

    def test_single_output_preserves_index(self, sample_data):
        """Single-output indicator preserves DataFrame index."""
        engine = IndicatorEngine()
        indicator = MockSingleOutputIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "rsi_14")

        # Index should match input
        pd.testing.assert_index_equal(result.index, sample_data.index)


class TestComputeIndicatorOldFormat:
    """Tests for old-format multi-output indicators.

    After M6 cleanup, old-format indicators (those returning columns with
    params embedded in names like 'upper_20_2.0') are no longer supported
    and should raise ValueError.
    """

    def test_old_format_raises_value_error(self, sample_data):
        """Old-format columns should raise ValueError after v3 cleanup."""
        engine = IndicatorEngine()
        indicator = MockOldFormatIndicator(name="test")

        with pytest.raises(ValueError) as exc_info:
            engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        # Error message should be helpful
        assert "output mismatch" in str(exc_info.value).lower()

    def test_old_format_error_shows_expected_columns(self, sample_data):
        """Error message should list expected column names."""
        engine = IndicatorEngine()
        indicator = MockOldFormatIndicator(name="test")

        with pytest.raises(ValueError) as exc_info:
            engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        error_msg = str(exc_info.value)
        # Should mention expected columns from get_output_names()
        assert "upper" in error_msg or "lower" in error_msg or "middle" in error_msg

    def test_old_format_error_shows_actual_columns(self, sample_data):
        """Error message should list actual column names returned."""
        engine = IndicatorEngine()
        indicator = MockOldFormatIndicator(name="test")

        with pytest.raises(ValueError) as exc_info:
            engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        error_msg = str(exc_info.value)
        # Should show what columns were actually returned
        assert "upper_20_2.0" in error_msg


class TestComputeIndicatorNewFormat:
    """Tests for new-format multi-output indicators."""

    def test_new_format_columns_prefixed(self, sample_data):
        """New-format columns are prefixed with indicator_id."""
        engine = IndicatorEngine()
        indicator = MockNewFormatIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        # Columns should be prefixed
        assert "bbands_20_2.upper" in result.columns
        assert "bbands_20_2.middle" in result.columns
        assert "bbands_20_2.lower" in result.columns
        # Original semantic names should NOT be present
        assert "upper" not in result.columns
        assert "middle" not in result.columns
        assert "lower" not in result.columns

    def test_new_format_adds_alias(self, sample_data):
        """New-format indicators get alias column for indicator_id."""
        engine = IndicatorEngine()
        indicator = MockNewFormatIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        # Alias should exist
        assert "bbands_20_2" in result.columns
        # Alias should point to primary output
        assert result["bbands_20_2"].tolist() == result["bbands_20_2.upper"].tolist()

    def test_new_format_preserves_all_values(self, sample_data):
        """New-format indicators preserve all column values."""
        engine = IndicatorEngine()
        indicator = MockNewFormatIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        assert result["bbands_20_2.upper"].tolist() == [1.0, 1.0, 1.0]
        assert result["bbands_20_2.middle"].tolist() == [0.5, 0.5, 0.5]
        assert result["bbands_20_2.lower"].tolist() == [0.0, 0.0, 0.0]


class TestFormatDetection:
    """Tests for format detection logic.

    After M6 cleanup, old-format indicators raise errors instead of
    being detected and handled specially.
    """

    def test_column_mismatch_raises_error(self, sample_data):
        """Column mismatch (old format) now raises ValueError."""
        engine = IndicatorEngine()
        indicator = MockOldFormatIndicator(name="test")

        with pytest.raises(ValueError) as exc_info:
            engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        # Should clearly indicate mismatch
        assert "mismatch" in str(exc_info.value).lower()

    def test_detects_new_format_by_column_match(self, sample_data):
        """Format detection identifies new format by column name match."""
        engine = IndicatorEngine()
        indicator = MockNewFormatIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        # If new format detected, columns should be prefixed
        assert "bbands_20_2.upper" in result.columns
        # Original semantic names should not exist
        assert "upper" not in result.columns


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_single_output_with_dataframe_result(self, sample_data):
        """Handle edge case of single-output returning DataFrame."""

        class WeirdSingleOutputIndicator(BaseIndicator):
            @classmethod
            def is_multi_output(cls) -> bool:
                return False

            def compute(self, df: pd.DataFrame) -> pd.DataFrame:
                # Single output but returns DataFrame (edge case)
                return pd.DataFrame({"value": [1.0, 2.0, 3.0]}, index=df.index)

        engine = IndicatorEngine()
        indicator = WeirdSingleOutputIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "weird_14")

        # Should rename to indicator_id
        assert list(result.columns) == ["weird_14"]
        assert result["weird_14"].tolist() == [1.0, 2.0, 3.0]

    def test_multi_output_without_primary_output(self, sample_data):
        """Handle multi-output indicator without primary output defined."""

        class NoPrimaryIndicator(BaseIndicator):
            @classmethod
            def is_multi_output(cls) -> bool:
                return True

            @classmethod
            def get_output_names(cls) -> list[str]:
                return ["a", "b"]

            @classmethod
            def get_primary_output(cls) -> str | None:
                # No primary defined
                return None

            def compute(self, df: pd.DataFrame) -> pd.DataFrame:
                return pd.DataFrame({"a": [1, 1, 1], "b": [2, 2, 2]}, index=df.index)

        engine = IndicatorEngine()
        indicator = NoPrimaryIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "test_10")

        # Should have prefixed columns
        assert "test_10.a" in result.columns
        assert "test_10.b" in result.columns
        # No alias should be created (no primary)
        assert "test_10" not in result.columns


class TestApplyUsesComputeIndicator:
    """Tests for apply() routing through compute_indicator()."""

    def test_apply_single_output_uses_feature_id(self, sample_data):
        """apply() uses feature_id from indicator for single-output."""
        # Create indicator with feature_id set
        indicator = MockSingleOutputIndicator(name="rsi")
        indicator._feature_id = "rsi_14"

        engine = IndicatorEngine(indicators=[indicator])
        result = engine.apply(sample_data)

        # Should have column with feature_id (not technical name)
        assert "rsi_14" in result.columns
        assert result["rsi_14"].tolist() == [1.0, 2.0, 3.0]

    def test_apply_multi_output_old_format_raises_error(self, sample_data):
        """apply() raises error for old-format indicators after v3 cleanup."""
        indicator = MockOldFormatIndicator(name="bbands")
        indicator._feature_id = "bbands_20_2"

        engine = IndicatorEngine(indicators=[indicator])

        # Old format should now raise ProcessingError (wrapping ValueError)
        with pytest.raises(Exception) as exc_info:
            engine.apply(sample_data)

        error_msg = str(exc_info.value).lower()
        assert "mismatch" in error_msg or "failed" in error_msg

    def test_apply_multi_output_new_format_prefixes_columns(self, sample_data):
        """apply() prefixes columns for multi-output new-format indicators."""
        indicator = MockNewFormatIndicator(name="bbands")
        indicator._feature_id = "bbands_20_2"

        engine = IndicatorEngine(indicators=[indicator])
        result = engine.apply(sample_data)

        # Prefixed columns should exist
        assert "bbands_20_2.upper" in result.columns
        assert "bbands_20_2.middle" in result.columns
        assert "bbands_20_2.lower" in result.columns
        # Alias should exist
        assert "bbands_20_2" in result.columns
        # Original semantic names should NOT exist
        assert "upper" not in result.columns

    def test_apply_multiple_indicators(self, sample_data):
        """apply() handles multiple indicators correctly."""
        indicator1 = MockSingleOutputIndicator(name="rsi")
        indicator1._feature_id = "rsi_14"

        indicator2 = MockNewFormatIndicator(name="bbands")
        indicator2._feature_id = "bbands_20_2"

        engine = IndicatorEngine(indicators=[indicator1, indicator2])
        result = engine.apply(sample_data)

        # Both indicators should be present
        assert "rsi_14" in result.columns
        assert "bbands_20_2" in result.columns
        assert "bbands_20_2.upper" in result.columns
        assert "bbands_20_2.middle" in result.columns
        assert "bbands_20_2.lower" in result.columns

    def test_apply_preserves_ohlcv_columns(self, sample_data):
        """apply() preserves original OHLCV columns."""
        indicator = MockSingleOutputIndicator(name="rsi")
        indicator._feature_id = "rsi_14"

        engine = IndicatorEngine(indicators=[indicator])
        result = engine.apply(sample_data)

        # Original columns should be preserved
        assert "close" in result.columns
        # New indicator column should be added
        assert "rsi_14" in result.columns

    def test_apply_uses_fallback_when_no_feature_id(self, sample_data):
        """apply() uses get_column_name() when feature_id not set."""
        indicator = MockSingleOutputIndicator(name="rsi")
        # Don't set feature_id - should fall back to get_column_name()

        engine = IndicatorEngine(indicators=[indicator])
        result = engine.apply(sample_data)

        # Should use technical column name as fallback
        expected_name = indicator.get_column_name()
        assert expected_name in result.columns

    def test_apply_supports_indicator_chaining(self, sample_data):
        """apply() supports indicators that depend on previously computed indicators."""

        class ChainedIndicator(BaseIndicator):
            """Mock indicator that reads a column added by a previous indicator."""

            @classmethod
            def is_multi_output(cls) -> bool:
                return False

            def compute(self, df: pd.DataFrame) -> pd.Series:
                # This indicator depends on 'first_indicator' column
                if "first_indicator" not in df.columns:
                    raise ValueError(
                        "Expected 'first_indicator' column from previous indicator"
                    )
                # Compute based on the previous indicator's output
                return df["first_indicator"] * 2.0

        # First indicator
        indicator1 = MockSingleOutputIndicator(name="first")
        indicator1._feature_id = "first_indicator"

        # Second indicator depends on first
        indicator2 = ChainedIndicator(name="second")
        indicator2._feature_id = "second_indicator"

        engine = IndicatorEngine(indicators=[indicator1, indicator2])
        result = engine.apply(sample_data)

        # Both indicators should be computed successfully
        assert "first_indicator" in result.columns
        assert "second_indicator" in result.columns
        # Second indicator should be 2x the first
        assert result["second_indicator"].tolist() == [2.0, 4.0, 6.0]

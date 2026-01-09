"""
Unit tests for IndicatorEngine after M6 cleanup (v3-only mode).

After the v3 migration, old-format indicators (those returning columns
with parameters embedded in names like 'upper_20_2.0') are no longer
supported and should raise ValueError.
"""

import pandas as pd
import pytest

from ktrdr.indicators import IndicatorEngine
from ktrdr.indicators.base_indicator import BaseIndicator


class MockOldFormatIndicator(BaseIndicator):
    """Mock indicator returning old-format columns (params in names).

    This represents an indicator that hasn't been migrated to v3.
    After M6 cleanup, this should raise ValueError.
    """

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
        """OLD FORMAT: params in column names - should no longer be supported."""
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


class MockSingleOutputIndicator(BaseIndicator):
    """Mock single-output indicator."""

    @classmethod
    def is_multi_output(cls) -> bool:
        return False

    @classmethod
    def get_output_names(cls) -> list[str]:
        return []

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return pd.Series([1.0, 2.0, 3.0], index=df.index)


@pytest.fixture
def sample_data():
    """Sample OHLCV data for testing."""
    return pd.DataFrame({"close": [100, 101, 102]})


class TestOldFormatRaisesError:
    """Tests that old-format indicators now raise errors."""

    def test_old_format_raises_value_error(self, sample_data):
        """Old-format indicator should raise ValueError after v3 cleanup."""
        engine = IndicatorEngine()
        indicator = MockOldFormatIndicator(name="test")

        with pytest.raises(ValueError) as exc_info:
            engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        # Error message should be helpful
        assert "output mismatch" in str(exc_info.value).lower()
        # Should mention expected vs actual
        assert (
            "upper" in str(exc_info.value) or "expected" in str(exc_info.value).lower()
        )

    def test_old_format_in_apply_raises_error(self, sample_data):
        """Old-format indicator via apply() should also raise error."""
        indicator = MockOldFormatIndicator(name="bbands")
        indicator._feature_id = "bbands_20_2"

        engine = IndicatorEngine(indicators=[indicator])

        # Should raise ProcessingError (which wraps ValueError)
        with pytest.raises(Exception) as exc_info:
            engine.apply(sample_data)

        # The error should bubble up through apply()
        error_msg = str(exc_info.value).lower()
        assert "mismatch" in error_msg or "failed" in error_msg


class TestNewFormatStillWorks:
    """Tests that new-format indicators continue to work correctly."""

    def test_new_format_columns_prefixed(self, sample_data):
        """New-format columns should still be prefixed with indicator_id."""
        engine = IndicatorEngine()
        indicator = MockNewFormatIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        assert "bbands_20_2.upper" in result.columns
        assert "bbands_20_2.middle" in result.columns
        assert "bbands_20_2.lower" in result.columns

    def test_new_format_adds_alias(self, sample_data):
        """New-format indicators should still get alias column."""
        engine = IndicatorEngine()
        indicator = MockNewFormatIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        assert "bbands_20_2" in result.columns
        assert result["bbands_20_2"].tolist() == result["bbands_20_2.upper"].tolist()

    def test_single_output_still_works(self, sample_data):
        """Single-output indicators should still work."""
        engine = IndicatorEngine()
        indicator = MockSingleOutputIndicator(name="test")

        result = engine.compute_indicator(sample_data, indicator, "rsi_14")

        assert list(result.columns) == ["rsi_14"]
        assert result["rsi_14"].tolist() == [1.0, 2.0, 3.0]


class TestErrorMessages:
    """Tests for error message quality."""

    def test_error_message_shows_expected_outputs(self, sample_data):
        """Error message should list expected output names."""
        engine = IndicatorEngine()
        indicator = MockOldFormatIndicator(name="test")

        with pytest.raises(ValueError) as exc_info:
            engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        error_msg = str(exc_info.value)
        # Should mention expected columns
        assert "upper" in error_msg or "lower" in error_msg or "middle" in error_msg

    def test_error_message_shows_actual_outputs(self, sample_data):
        """Error message should list actual output names."""
        engine = IndicatorEngine()
        indicator = MockOldFormatIndicator(name="test")

        with pytest.raises(ValueError) as exc_info:
            engine.compute_indicator(sample_data, indicator, "bbands_20_2")

        error_msg = str(exc_info.value)
        # Should mention what was actually returned
        assert "upper_20_2.0" in error_msg or "actual" in error_msg.lower()

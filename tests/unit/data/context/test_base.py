"""Tests for context data provider base classes."""

import pandas as pd
import pytest

from ktrdr.data.context.base import (
    ContextDataAligner,
    ContextDataProvider,
    ContextDataResult,
)


class TestContextDataResult:
    """Test ContextDataResult stores all required fields."""

    def test_stores_required_fields(self):
        """ContextDataResult should store source_id, data, frequency, provider, metadata."""
        df = pd.DataFrame(
            {"value": [1.0, 2.0, 3.0]},
            index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        )
        result = ContextDataResult(
            source_id="fred_DGS2",
            data=df,
            frequency="daily",
            provider="fred",
            metadata={"series_id": "DGS2"},
        )
        assert result.source_id == "fred_DGS2"
        assert result.frequency == "daily"
        assert result.provider == "fred"
        assert result.metadata == {"series_id": "DGS2"}
        assert len(result.data) == 3

    def test_data_is_dataframe(self):
        """Data field must be a pandas DataFrame."""
        df = pd.DataFrame({"value": [1.0]})
        result = ContextDataResult(
            source_id="test",
            data=df,
            frequency="daily",
            provider="test",
            metadata={},
        )
        assert isinstance(result.data, pd.DataFrame)


class TestContextDataProviderABC:
    """Test ContextDataProvider cannot be instantiated directly."""

    def test_cannot_instantiate_directly(self):
        """ContextDataProvider is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            ContextDataProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_fetch(self):
        """Subclass that doesn't implement fetch() cannot be instantiated."""

        class IncompleteProvider(ContextDataProvider):
            async def validate(self, config, **kwargs):
                return []

            def get_source_ids(self, config):
                return []

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_validate(self):
        """Subclass that doesn't implement validate() cannot be instantiated."""

        class IncompleteProvider(ContextDataProvider):
            async def fetch(self, config, start_date, end_date):
                return []

            def get_source_ids(self, config):
                return []

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_get_source_ids(self):
        """Subclass that doesn't implement get_source_ids() cannot be instantiated."""

        class IncompleteProvider(ContextDataProvider):
            async def fetch(self, config, start_date, end_date):
                return []

            async def validate(self, config, **kwargs):
                return []

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_complete_subclass_can_be_instantiated(self):
        """Subclass implementing all methods can be instantiated."""

        class CompleteProvider(ContextDataProvider):
            async def fetch(self, config, start_date, end_date):
                return []

            async def validate(self, config, **kwargs):
                return []

            def get_source_ids(self, config):
                return []

        provider = CompleteProvider()
        assert provider is not None


class TestContextDataAligner:
    """Test forward-fill alignment of context data to primary timeframe."""

    def _make_hourly_index(self, start: str, periods: int) -> pd.DatetimeIndex:
        """Create an hourly datetime index."""
        return pd.date_range(start=start, periods=periods, freq="h")

    def _make_daily_index(self, start: str, periods: int) -> pd.DatetimeIndex:
        """Create a daily datetime index."""
        return pd.date_range(start=start, periods=periods, freq="D")

    def test_forward_fill_daily_to_hourly(self):
        """Daily data should be forward-filled to hourly index."""
        daily_data = pd.DataFrame(
            {"value": [4.38, 4.35, 4.40]},
            index=self._make_daily_index("2024-01-02", 3),
        )
        # 72 hours covers all 3 daily observations
        hourly_index = self._make_hourly_index("2024-01-02", 72)

        aligner = ContextDataAligner()
        result = aligner.align(daily_data, hourly_index)

        # Should have data for all hourly bars
        assert len(result) == 72
        # First value should match first daily value
        assert result["value"].iloc[0] == 4.38
        # Hours on Jan 3 should have Jan 3 value
        assert result.loc["2024-01-03 12:00", "value"] == 4.35
        # Hours on Jan 4 should have Jan 4 value
        assert result.loc["2024-01-04 12:00", "value"] == 4.40
        # No NaN values in the result
        assert not result["value"].isna().any()

    def test_drops_leading_nans(self):
        """Leading NaN rows (before first context observation) should be dropped."""
        # Context data starts on Jan 3, but primary starts on Jan 1
        daily_data = pd.DataFrame(
            {"value": [4.38, 4.35]},
            index=self._make_daily_index("2024-01-03", 2),
        )
        hourly_index = self._make_hourly_index("2024-01-01", 96)  # 4 days

        aligner = ContextDataAligner()
        result = aligner.align(daily_data, hourly_index)

        # First row should start at or after the first context data point
        assert result.index[0] >= pd.Timestamp("2024-01-03")
        # No NaN values
        assert not result.isna().any().any()

    def test_weekend_gaps_forward_filled(self):
        """Weekend gaps in daily data should be correctly forward-filled."""
        # Friday and Monday data, no Saturday/Sunday
        daily_data = pd.DataFrame(
            {"value": [4.38, 4.40]},
            index=pd.to_datetime(["2024-01-05", "2024-01-08"]),  # Fri, Mon
        )
        # Hourly index includes the weekend
        hourly_index = pd.date_range(
            start="2024-01-05", end="2024-01-08 23:00", freq="h"
        )

        aligner = ContextDataAligner()
        result = aligner.align(daily_data, hourly_index)

        # Saturday/Sunday hours should have Friday's value (4.38)
        saturday = result.loc["2024-01-06"]
        assert (saturday["value"] == 4.38).all()

    def test_weekly_to_hourly_alignment(self):
        """Weekly data should be forward-filled across ~168 hourly bars."""
        weekly_data = pd.DataFrame(
            {"value": [72.5, 78.2]},
            index=pd.to_datetime(["2024-01-02", "2024-01-09"]),  # Tuesdays
        )
        hourly_index = self._make_hourly_index("2024-01-02", 336)  # 14 days

        aligner = ContextDataAligner()
        result = aligner.align(weekly_data, hourly_index)

        # Values between Jan 2 and Jan 9 should be 72.5
        mid_week = result.loc["2024-01-05 12:00"]
        assert mid_week["value"] == 72.5
        # Values from Jan 9 onward should be 78.2
        post_second = result.loc["2024-01-10 12:00"]
        assert post_second["value"] == 78.2

    def test_preserves_column_names(self):
        """Aligned result should preserve original column names."""
        daily_data = pd.DataFrame(
            {"yield_value": [4.38], "rate": [3.5]},
            index=self._make_daily_index("2024-01-02", 1),
        )
        hourly_index = self._make_hourly_index("2024-01-02", 24)

        aligner = ContextDataAligner()
        result = aligner.align(daily_data, hourly_index)

        assert "yield_value" in result.columns
        assert "rate" in result.columns

    def test_empty_context_data(self):
        """Aligning empty context data should return empty DataFrame."""
        empty_data = pd.DataFrame({"value": pd.Series([], dtype=float)})
        hourly_index = self._make_hourly_index("2024-01-02", 24)

        aligner = ContextDataAligner()
        result = aligner.align(empty_data, hourly_index)

        assert len(result) == 0

    def test_same_frequency_alignment(self):
        """When context and primary have same frequency, should still work."""
        hourly_data = pd.DataFrame(
            {"value": [1.0, 2.0, 3.0]},
            index=self._make_hourly_index("2024-01-02", 3),
        )
        hourly_index = self._make_hourly_index("2024-01-02", 3)

        aligner = ContextDataAligner()
        result = aligner.align(hourly_data, hourly_index)

        assert len(result) == 3
        assert list(result["value"]) == [1.0, 2.0, 3.0]

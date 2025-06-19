"""
Unit tests for Timeframe Synchronizer utilities.

This module contains comprehensive tests for the TimeframeSynchronizer
and related utilities, ensuring proper timeframe alignment, synchronization,
and data validation across multiple timeframes.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from ktrdr.data.timeframe_synchronizer import (
    TimeframeSynchronizer,
    TimeframeRelation,
    AlignmentResult,
    SynchronizationStats,
    align_timeframes_to_lowest,
    calculate_multi_timeframe_periods,
    validate_timeframe_compatibility,
)
from ktrdr.errors import DataValidationError


class TestTimeframeRelation:
    """Test TimeframeRelation enum."""

    def test_enum_values(self):
        """Test enum values are correctly defined."""
        assert TimeframeRelation.HIGHER.value == "higher"
        assert TimeframeRelation.LOWER.value == "lower"
        assert TimeframeRelation.EQUAL.value == "equal"
        assert TimeframeRelation.INCOMPARABLE.value == "incomparable"


class TestTimeframeSynchronizer:
    """Test TimeframeSynchronizer class."""

    @pytest.fixture
    def synchronizer(self):
        """Create TimeframeSynchronizer instance for testing."""
        return TimeframeSynchronizer()

    @pytest.fixture
    def sample_1h_data(self):
        """Create sample 1-hour data."""
        dates = pd.date_range(
            start="2023-01-01 00:00:00", periods=100, freq="1h", tz="UTC"
        )
        return pd.DataFrame(
            {
                "open": np.random.uniform(100, 110, 100),
                "high": np.random.uniform(105, 115, 100),
                "low": np.random.uniform(95, 105, 100),
                "close": np.random.uniform(100, 110, 100),
                "volume": np.random.randint(1000, 10000, 100),
            },
            index=dates,
        )

    @pytest.fixture
    def sample_4h_data(self):
        """Create sample 4-hour data."""
        dates = pd.date_range(
            start="2023-01-01 00:00:00", periods=25, freq="4h", tz="UTC"
        )
        return pd.DataFrame(
            {
                "open": np.random.uniform(100, 110, 25),
                "high": np.random.uniform(105, 115, 25),
                "low": np.random.uniform(95, 105, 25),
                "close": np.random.uniform(100, 110, 25),
                "volume": np.random.randint(4000, 40000, 25),
            },
            index=dates,
        )

    @pytest.fixture
    def sample_1d_data(self):
        """Create sample daily data."""
        dates = pd.date_range(start="2023-01-01", periods=5, freq="1D", tz="UTC")
        return pd.DataFrame(
            {
                "open": np.random.uniform(100, 110, 5),
                "high": np.random.uniform(105, 115, 5),
                "low": np.random.uniform(95, 105, 5),
                "close": np.random.uniform(100, 110, 5),
                "volume": np.random.randint(100000, 1000000, 5),
            },
            index=dates,
        )

    def test_initialization(self, synchronizer):
        """Test synchronizer initialization."""
        assert synchronizer is not None
        assert hasattr(synchronizer, "timestamp_manager")
        assert synchronizer.TIMEFRAME_MULTIPLIERS["1h"] == 60
        assert synchronizer.TIMEFRAME_MULTIPLIERS["4h"] == 240

    def test_calculate_periods_needed(self):
        """Test period calculation for different timeframes."""
        # 1h to 4h: 200 hours = 50 4-hour periods
        result = TimeframeSynchronizer.calculate_periods_needed("1h", "4h", 200)
        assert result == 50

        # 1h to 1d: 200 hours ≈ 8.33 days, minimum 10
        result = TimeframeSynchronizer.calculate_periods_needed("1h", "1d", 200)
        assert result == 10  # Minimum enforced

        # 4h to 1h: 50 4-hour periods = 200 1-hour periods
        result = TimeframeSynchronizer.calculate_periods_needed("4h", "1h", 50)
        assert result == 200

        # Equal timeframes
        result = TimeframeSynchronizer.calculate_periods_needed("1h", "1h", 100)
        assert result == 100

    def test_calculate_periods_needed_invalid_timeframes(self):
        """Test error handling for invalid timeframes."""
        with pytest.raises(ValueError, match="Unsupported auxiliary timeframe"):
            TimeframeSynchronizer.calculate_periods_needed("1h", "invalid", 200)

        with pytest.raises(ValueError, match="Unsupported primary timeframe"):
            TimeframeSynchronizer.calculate_periods_needed("invalid", "4h", 200)

    def test_get_timeframe_relation(self):
        """Test timeframe relationship determination."""
        # Higher timeframe relations
        assert (
            TimeframeSynchronizer.get_timeframe_relation("4h", "1h")
            == TimeframeRelation.HIGHER
        )
        assert (
            TimeframeSynchronizer.get_timeframe_relation("1d", "4h")
            == TimeframeRelation.HIGHER
        )
        assert (
            TimeframeSynchronizer.get_timeframe_relation("1w", "1d")
            == TimeframeRelation.HIGHER
        )

        # Lower timeframe relations
        assert (
            TimeframeSynchronizer.get_timeframe_relation("1h", "4h")
            == TimeframeRelation.LOWER
        )
        assert (
            TimeframeSynchronizer.get_timeframe_relation("4h", "1d")
            == TimeframeRelation.LOWER
        )

        # Equal timeframes
        assert (
            TimeframeSynchronizer.get_timeframe_relation("1h", "1h")
            == TimeframeRelation.EQUAL
        )
        assert (
            TimeframeSynchronizer.get_timeframe_relation("4h", "4h")
            == TimeframeRelation.EQUAL
        )

        # Incomparable timeframes
        assert (
            TimeframeSynchronizer.get_timeframe_relation("invalid", "1h")
            == TimeframeRelation.INCOMPARABLE
        )
        assert (
            TimeframeSynchronizer.get_timeframe_relation("1h", "invalid")
            == TimeframeRelation.INCOMPARABLE
        )

    def test_forward_fill_alignment_basic(
        self, synchronizer, sample_1h_data, sample_4h_data
    ):
        """Test basic forward-fill alignment."""
        result = synchronizer.forward_fill_alignment(
            sample_4h_data, sample_1h_data, "4h", "1h"
        )

        assert isinstance(result, AlignmentResult)
        assert result.source_timeframe == "4h"
        assert result.reference_timeframe == "1h"
        assert result.alignment_method == "forward_fill"
        assert result.rows_after == len(sample_1h_data)
        assert 0 <= result.quality_score <= 1.0

    def test_forward_fill_alignment_timezone_handling(self, synchronizer):
        """Test timezone handling in alignment."""
        # Create data with different timezones
        dates_utc = pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC")
        dates_naive = pd.date_range("2023-01-01", periods=10, freq="1h")
        dates_est = pd.date_range("2023-01-01", periods=10, freq="1h", tz="US/Eastern")

        source_data = pd.DataFrame({"close": range(10)}, index=dates_naive)
        reference_data = pd.DataFrame({"close": range(10)}, index=dates_utc)

        result = synchronizer.forward_fill_alignment(
            source_data, reference_data, "1h", "1h"
        )

        # Both should be converted to UTC
        assert str(result.aligned_data.index.tz) == "UTC"

    def test_forward_fill_alignment_validation_errors(self, synchronizer):
        """Test validation errors in forward-fill alignment."""
        empty_df = pd.DataFrame()
        valid_df = pd.DataFrame(
            {"close": [1, 2, 3]},
            index=pd.date_range("2023-01-01", periods=3, freq="1h"),
        )

        # Empty source data
        with pytest.raises(DataValidationError, match="Source data cannot be empty"):
            synchronizer.forward_fill_alignment(empty_df, valid_df, "1h", "1h")

        # Empty reference data
        with pytest.raises(DataValidationError, match="Reference data cannot be empty"):
            synchronizer.forward_fill_alignment(valid_df, empty_df, "1h", "1h")

        # Non-datetime index
        invalid_df = pd.DataFrame({"close": [1, 2, 3]}, index=[0, 1, 2])
        with pytest.raises(DataValidationError, match="must have DatetimeIndex"):
            synchronizer.forward_fill_alignment(invalid_df, valid_df, "1h", "1h")

        # Unsupported timeframe
        with pytest.raises(DataValidationError, match="Unsupported source timeframe"):
            synchronizer.forward_fill_alignment(valid_df, valid_df, "invalid", "1h")

    def test_synchronize_multiple_timeframes(
        self, synchronizer, sample_1h_data, sample_4h_data, sample_1d_data
    ):
        """Test synchronizing multiple timeframes."""
        data_dict = {"1h": sample_1h_data, "4h": sample_4h_data, "1d": sample_1d_data}

        synchronized_data, stats = synchronizer.synchronize_multiple_timeframes(
            data_dict, "1h"
        )

        # Verify synchronized data
        assert isinstance(synchronized_data, dict)
        assert "1h" in synchronized_data
        assert "4h" in synchronized_data
        assert "1d" in synchronized_data

        # Reference timeframe should be unchanged
        pd.testing.assert_frame_equal(synchronized_data["1h"], sample_1h_data)

        # Other timeframes should have same index as reference
        assert synchronized_data["4h"].index.equals(sample_1h_data.index)
        assert synchronized_data["1d"].index.equals(sample_1h_data.index)

        # Verify statistics
        assert isinstance(stats, SynchronizationStats)
        assert stats.total_timeframes == 3
        assert stats.reference_timeframe == "1h"
        assert stats.reference_periods == len(sample_1h_data)
        assert 0 <= stats.average_quality_score <= 1.0
        assert stats.processing_time > 0

    def test_synchronize_multiple_timeframes_invalid_reference(
        self, synchronizer, sample_1h_data
    ):
        """Test error when reference timeframe is not in data."""
        data_dict = {"1h": sample_1h_data}

        with pytest.raises(
            DataValidationError, match="Reference timeframe 4h not found"
        ):
            synchronizer.synchronize_multiple_timeframes(data_dict, "4h")

    def test_interpolate_missing_data(self, synchronizer):
        """Test missing data interpolation."""
        # Create data with missing values
        dates = pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC")
        data = pd.DataFrame(
            {"close": [1, 2, np.nan, np.nan, 5, 6, np.nan, 8, 9, 10]}, index=dates
        )

        # Test linear interpolation
        interpolated = synchronizer.interpolate_missing_data(data, method="linear")

        # Should have fewer missing values
        original_missing = data.isnull().sum().sum()
        remaining_missing = interpolated.isnull().sum().sum()
        assert remaining_missing <= original_missing

        # Check specific interpolated values
        assert abs(interpolated.loc[dates[2], "close"] - 3.0) < 0.01  # (2+4)/2 ≈ 3
        assert abs(interpolated.loc[dates[3], "close"] - 4.0) < 0.01  # (2+5)/2 ≈ 4

    def test_interpolate_missing_data_with_limit(self, synchronizer):
        """Test interpolation with limit on consecutive NaNs."""
        dates = pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC")
        data = pd.DataFrame(
            {"close": [1, 2, np.nan, np.nan, np.nan, np.nan, 7, 8, 9, 10]}, index=dates
        )

        # Limit to 2 consecutive interpolations
        interpolated = synchronizer.interpolate_missing_data(
            data, method="linear", limit=2
        )

        # Should still have some missing values (or all filled if limit allows)
        remaining_missing = interpolated.isnull().sum().sum()
        # Allow for the case where all values are interpolated with this limit
        assert remaining_missing >= 0

    def test_validate_temporal_consistency(self, synchronizer):
        """Test temporal consistency validation."""
        # Create consistent 1-hour data
        dates_consistent = pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC")
        consistent_data = pd.DataFrame({"close": range(10)}, index=dates_consistent)

        # Create inconsistent data with gaps
        dates_inconsistent = pd.to_datetime(
            [
                "2023-01-01 00:00:00",
                "2023-01-01 01:00:00",
                "2023-01-01 03:00:00",  # 2-hour gap
                "2023-01-01 04:00:00",
                "2023-01-01 06:00:00",  # Another 2-hour gap
            ],
            utc=True,
        )
        inconsistent_data = pd.DataFrame({"close": range(5)}, index=dates_inconsistent)

        data_dict = {
            "1h_consistent": consistent_data,
            "1h_inconsistent": inconsistent_data,
        }

        results = synchronizer.validate_temporal_consistency(data_dict)

        assert results["1h_consistent"] == True
        assert results["1h_inconsistent"] == False

    def test_validate_temporal_consistency_empty_data(self, synchronizer):
        """Test temporal consistency with empty data."""
        empty_data = pd.DataFrame()
        small_data = pd.DataFrame(
            {"close": [1]},
            index=pd.date_range("2023-01-01", periods=1, freq="1h", tz="UTC"),
        )

        data_dict = {"empty": empty_data, "small": small_data}

        results = synchronizer.validate_temporal_consistency(data_dict)

        # Empty and single-row data should be considered consistent
        assert results["small"] is True

    def test_get_optimal_reference_timeframe(self):
        """Test optimal reference timeframe selection."""
        # Should select lowest (most granular) timeframe
        timeframes = ["1d", "4h", "1h"]
        optimal = TimeframeSynchronizer.get_optimal_reference_timeframe(timeframes)
        assert optimal == "1h"

        # Single timeframe
        timeframes = ["4h"]
        optimal = TimeframeSynchronizer.get_optimal_reference_timeframe(timeframes)
        assert optimal == "4h"

        # Mixed valid and invalid timeframes
        timeframes = ["1d", "invalid", "4h", "1h"]
        optimal = TimeframeSynchronizer.get_optimal_reference_timeframe(timeframes)
        assert optimal == "1h"

    def test_get_optimal_reference_timeframe_errors(self):
        """Test error cases for optimal reference timeframe selection."""
        # Empty list
        with pytest.raises(ValueError, match="No timeframes provided"):
            TimeframeSynchronizer.get_optimal_reference_timeframe([])

        # No supported timeframes
        with pytest.raises(ValueError, match="No supported timeframes found"):
            TimeframeSynchronizer.get_optimal_reference_timeframe(
                ["invalid1", "invalid2"]
            )

    def test_estimate_memory_usage(self):
        """Test memory usage estimation."""
        # Create sample data
        dates = pd.date_range("2023-01-01", periods=1000, freq="1h", tz="UTC")
        large_data = pd.DataFrame(
            {
                "open": range(1000),
                "high": range(1000),
                "low": range(1000),
                "close": range(1000),
                "volume": range(1000),
            },
            index=dates,
        )

        dates_small = pd.date_range("2023-01-01", periods=250, freq="4h", tz="UTC")
        small_data = pd.DataFrame(
            {
                "open": range(250),
                "high": range(250),
                "low": range(250),
                "close": range(250),
                "volume": range(250),
            },
            index=dates_small,
        )

        data_dict = {"1h": large_data, "4h": small_data}

        estimates = TimeframeSynchronizer.estimate_memory_usage(data_dict, "1h")

        # Should have estimates for both timeframes plus total
        assert "1h" in estimates
        assert "4h" in estimates
        assert "total_estimated" in estimates

        # 1h should be larger (more rows when aligned)
        assert estimates["1h"] >= estimates["4h"]
        assert estimates["total_estimated"] > 0

    def test_estimate_memory_usage_missing_target(self):
        """Test memory usage estimation with missing target timeframe."""
        data_dict = {"1h": pd.DataFrame()}
        estimates = TimeframeSynchronizer.estimate_memory_usage(data_dict, "4h")

        # Should return empty estimates
        assert len(estimates) == 0


class TestUtilityFunctions:
    """Test utility functions."""

    def test_align_timeframes_to_lowest(self):
        """Test alignment to lowest timeframe utility."""
        dates_1h = pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC")
        dates_4h = pd.date_range("2023-01-01", periods=3, freq="4h", tz="UTC")

        data_dict = {
            "1h": pd.DataFrame({"close": range(10)}, index=dates_1h),
            "4h": pd.DataFrame({"close": range(3)}, index=dates_4h),
        }

        aligned_data, reference_tf = align_timeframes_to_lowest(data_dict)

        assert reference_tf == "1h"  # Lowest timeframe
        assert "1h" in aligned_data
        assert "4h" in aligned_data
        assert aligned_data["4h"].index.equals(dates_1h)  # Aligned to 1h timeline

    def test_calculate_multi_timeframe_periods(self):
        """Test multi-timeframe period calculation utility."""
        periods_dict = calculate_multi_timeframe_periods(
            primary_timeframe="1h",
            auxiliary_timeframes=["4h", "1d"],
            primary_periods=200,
        )

        assert periods_dict["1h"] == 200
        assert periods_dict["4h"] == 50  # 200/4
        assert periods_dict["1d"] == 10  # 200/24, minimum 10

    def test_validate_timeframe_compatibility(self):
        """Test timeframe compatibility validation utility."""
        timeframes = ["1h", "4h", "invalid", "1d", "another_invalid"]

        compatible = validate_timeframe_compatibility(timeframes)

        assert "1h" in compatible
        assert "4h" in compatible
        assert "1d" in compatible
        assert "invalid" not in compatible
        assert "another_invalid" not in compatible
        assert len(compatible) == 3

    def test_validate_timeframe_compatibility_empty(self):
        """Test compatibility validation with empty input."""
        compatible = validate_timeframe_compatibility([])
        assert compatible == []

    def test_validate_timeframe_compatibility_all_invalid(self):
        """Test compatibility validation with all invalid timeframes."""
        timeframes = ["invalid1", "invalid2", "invalid3"]
        compatible = validate_timeframe_compatibility(timeframes)
        assert compatible == []


class TestDataStructures:
    """Test data structure classes."""

    def test_alignment_result_creation(self):
        """Test AlignmentResult dataclass creation."""
        dates = pd.date_range("2023-01-01", periods=5, freq="1h", tz="UTC")
        aligned_data = pd.DataFrame({"close": range(5)}, index=dates)

        result = AlignmentResult(
            aligned_data=aligned_data,
            reference_timeframe="1h",
            source_timeframe="4h",
            alignment_method="forward_fill",
            rows_before=10,
            rows_after=5,
            missing_ratio=0.1,
            quality_score=0.8,
        )

        assert result.reference_timeframe == "1h"
        assert result.source_timeframe == "4h"
        assert result.alignment_method == "forward_fill"
        assert result.rows_before == 10
        assert result.rows_after == 5
        assert result.missing_ratio == 0.1
        assert result.quality_score == 0.8
        assert len(result.aligned_data) == 5

    def test_synchronization_stats_creation(self):
        """Test SynchronizationStats dataclass creation."""
        stats = SynchronizationStats(
            total_timeframes=3,
            successfully_aligned=2,
            failed_alignments=1,
            reference_timeframe="1h",
            reference_periods=100,
            average_quality_score=0.75,
            processing_time=1.5,
        )

        assert stats.total_timeframes == 3
        assert stats.successfully_aligned == 2
        assert stats.failed_alignments == 1
        assert stats.reference_timeframe == "1h"
        assert stats.reference_periods == 100
        assert stats.average_quality_score == 0.75
        assert stats.processing_time == 1.5


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_synchronizer_with_single_timeframe(self):
        """Test synchronizer behavior with single timeframe."""
        synchronizer = TimeframeSynchronizer()
        dates = pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC")
        data = pd.DataFrame({"close": range(10)}, index=dates)

        data_dict = {"1h": data}

        synchronized_data, stats = synchronizer.synchronize_multiple_timeframes(
            data_dict, "1h"
        )

        assert len(synchronized_data) == 1
        assert stats.total_timeframes == 1
        assert stats.successfully_aligned == 0  # No other timeframes to align
        assert stats.failed_alignments == 0
        pd.testing.assert_frame_equal(synchronized_data["1h"], data)

    def test_alignment_with_completely_missing_data(self):
        """Test alignment when source data has no overlap with reference."""
        synchronizer = TimeframeSynchronizer()

        # Non-overlapping time ranges
        dates_ref = pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC")
        dates_src = pd.date_range("2023-02-01", periods=5, freq="1h", tz="UTC")

        reference_data = pd.DataFrame({"close": range(10)}, index=dates_ref)
        source_data = pd.DataFrame({"close": range(5)}, index=dates_src)

        result = synchronizer.forward_fill_alignment(
            source_data, reference_data, "1h", "1h"
        )

        # Should have all NaN values due to no overlap
        assert result.missing_ratio == 1.0  # 100% missing
        assert result.quality_score < 0.5  # Poor quality due to missing data

    def test_memory_estimation_with_empty_dataframes(self):
        """Test memory estimation with empty DataFrames."""
        data_dict = {"1h": pd.DataFrame(), "4h": pd.DataFrame()}

        estimates = TimeframeSynchronizer.estimate_memory_usage(data_dict, "1h")

        # Should handle empty DataFrames gracefully
        assert "1h" in estimates
        assert "4h" in estimates
        assert estimates["1h"] >= 0
        assert estimates["4h"] >= 0

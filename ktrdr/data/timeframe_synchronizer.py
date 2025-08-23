"""
Timeframe Synchronization Utilities for Multi-Timeframe Data Processing.

This module provides utilities for synchronizing, aligning, and managing data
across multiple timeframes. It handles the complex task of ensuring temporal
consistency when working with data from different time intervals.

Key Features:
- Period calculation for different timeframes
- Data alignment with forward-fill strategy
- Timezone consistency handling (UTC)
- Missing data interpolation
- Data quality validation across timeframes
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataValidationError
from ktrdr.utils.timezone_utils import TimestampManager

# Get module logger
logger = get_logger(__name__)


class TimeframeRelation(Enum):
    """Relationship between two timeframes."""

    HIGHER = "higher"  # tf1 is higher than tf2 (e.g., 1d vs 1h)
    LOWER = "lower"  # tf1 is lower than tf2 (e.g., 1h vs 1d)
    EQUAL = "equal"  # tf1 equals tf2
    INCOMPARABLE = "incomparable"  # Cannot compare (e.g., different types)


@dataclass
class AlignmentResult:
    """Result of timeframe alignment operation."""

    aligned_data: pd.DataFrame
    reference_timeframe: str
    source_timeframe: str
    alignment_method: str
    rows_before: int
    rows_after: int
    missing_ratio: float
    quality_score: float


@dataclass
class SynchronizationStats:
    """Statistics for multi-timeframe synchronization."""

    total_timeframes: int
    successfully_aligned: int
    failed_alignments: int
    reference_timeframe: str
    reference_periods: int
    average_quality_score: float
    processing_time: float


class TimeframeSynchronizer:
    """
    Handles data alignment and synchronization across timeframes.

    This class provides methods for aligning data from different timeframes
    to a common timeline, handling missing data, and ensuring temporal
    consistency across multi-timeframe datasets.
    """

    # Timeframe hierarchy and multipliers (in minutes)
    TIMEFRAME_HIERARCHY = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
    TIMEFRAME_MULTIPLIERS = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
        "1w": 10080,
        "1M": 43200,
    }

    # Resampling rules for pandas
    RESAMPLE_RULES = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
        "4h": "4h",
        "1d": "1D",
        "1w": "1W",
        "1M": "1M",
    }

    def __init__(self):
        """Initialize the TimeframeSynchronizer."""
        self.timestamp_manager = TimestampManager()
        logger.info("TimeframeSynchronizer initialized")

    @staticmethod
    def calculate_periods_needed(
        primary_timeframe: str, auxiliary_timeframe: str, primary_periods: int
    ) -> int:
        """
        Calculate how many periods are needed in auxiliary timeframe.

        This method calculates the equivalent number of periods needed in an
        auxiliary timeframe to cover the same time span as the primary timeframe.

        Args:
            primary_timeframe: Primary timeframe (e.g., '1h')
            auxiliary_timeframe: Auxiliary timeframe (e.g., '4h')
            primary_periods: Number of periods in primary timeframe

        Returns:
            Number of periods needed in auxiliary timeframe

        Raises:
            ValueError: If timeframes are not supported

        Example:
            >>> TimeframeSynchronizer.calculate_periods_needed('1h', '4h', 200)
            50  # 200 hours = 50 4-hour periods
        """
        if auxiliary_timeframe not in TimeframeSynchronizer.TIMEFRAME_MULTIPLIERS:
            raise ValueError(f"Unsupported auxiliary timeframe: {auxiliary_timeframe}")

        if primary_timeframe not in TimeframeSynchronizer.TIMEFRAME_MULTIPLIERS:
            raise ValueError(f"Unsupported primary timeframe: {primary_timeframe}")

        primary_minutes = TimeframeSynchronizer.TIMEFRAME_MULTIPLIERS[primary_timeframe]
        aux_minutes = TimeframeSynchronizer.TIMEFRAME_MULTIPLIERS[auxiliary_timeframe]

        # Calculate ratio and ensure minimum periods
        ratio = aux_minutes / primary_minutes
        calculated_periods = max(10, int(primary_periods / ratio))

        logger.debug(
            f"Calculated {calculated_periods} periods for {auxiliary_timeframe} "
            f"(ratio: {ratio:.2f}, primary: {primary_periods} {primary_timeframe})"
        )

        return calculated_periods

    @staticmethod
    def get_timeframe_relation(timeframe1: str, timeframe2: str) -> TimeframeRelation:
        """
        Determine the relationship between two timeframes.

        Args:
            timeframe1: First timeframe
            timeframe2: Second timeframe

        Returns:
            TimeframeRelation indicating the relationship
        """
        try:
            pos1 = TimeframeSynchronizer.TIMEFRAME_HIERARCHY.index(timeframe1)
            pos2 = TimeframeSynchronizer.TIMEFRAME_HIERARCHY.index(timeframe2)

            if pos1 > pos2:
                return TimeframeRelation.HIGHER
            elif pos1 < pos2:
                return TimeframeRelation.LOWER
            else:
                return TimeframeRelation.EQUAL

        except ValueError:
            return TimeframeRelation.INCOMPARABLE

    def forward_fill_alignment(
        self,
        source_data: pd.DataFrame,
        reference_data: pd.DataFrame,
        source_timeframe: str,
        reference_timeframe: str,
    ) -> AlignmentResult:
        """
        Align source data to reference timeline using forward-fill strategy.

        This method aligns data from one timeframe to the timeline of another
        timeframe using forward-fill to handle missing values.

        Args:
            source_data: Data to be aligned
            reference_data: Reference data providing the target timeline
            source_timeframe: Timeframe of source data
            reference_timeframe: Timeframe of reference data

        Returns:
            AlignmentResult with aligned data and metadata

        Raises:
            DataValidationError: If data validation fails
        """
        # Validate inputs
        self._validate_alignment_inputs(
            source_data, reference_data, source_timeframe, reference_timeframe
        )

        rows_before = len(source_data)

        # Ensure timezone consistency (UTC)
        source_data = self._ensure_utc_timezone(source_data, source_timeframe)
        reference_data = self._ensure_utc_timezone(reference_data, reference_timeframe)

        # Perform alignment using forward-fill
        aligned_data = source_data.reindex(reference_data.index, method="ffill")

        rows_after = len(aligned_data)
        missing_count = aligned_data.isnull().sum().sum()
        total_values = aligned_data.size
        missing_ratio = missing_count / total_values if total_values > 0 else 0

        # Calculate quality score
        quality_score = self._calculate_alignment_quality(
            aligned_data, source_data, missing_ratio
        )

        result = AlignmentResult(
            aligned_data=aligned_data,
            reference_timeframe=reference_timeframe,
            source_timeframe=source_timeframe,
            alignment_method="forward_fill",
            rows_before=rows_before,
            rows_after=rows_after,
            missing_ratio=missing_ratio,
            quality_score=quality_score,
        )

        logger.info(
            f"Aligned {source_timeframe} to {reference_timeframe}: "
            f"{rows_before} → {rows_after} rows, "
            f"missing ratio: {missing_ratio:.3f}, "
            f"quality: {quality_score:.3f}"
        )

        return result

    def synchronize_multiple_timeframes(
        self, data_dict: dict[str, pd.DataFrame], reference_timeframe: str
    ) -> tuple[dict[str, pd.DataFrame], SynchronizationStats]:
        """
        Validate and prepare multiple timeframes without destroying timeframe integrity.

        This method does NOT expand or synchronize raw data to a common timeline.
        Each timeframe maintains its native temporal resolution for proper indicator calculation.
        Temporal alignment happens later in the FuzzyNeuralProcessor for neural network input.

        Args:
            data_dict: Dictionary mapping timeframes to DataFrames
            reference_timeframe: Timeframe to use as reference (for stats only)

        Returns:
            Tuple of (validated_data, synchronization_stats)

        Raises:
            DataValidationError: If reference timeframe not found or data invalid
        """
        import time

        start_time = time.time()

        if reference_timeframe not in data_dict:
            raise DataValidationError(
                f"Reference timeframe {reference_timeframe} not found in data"
            )

        # Return original data without modification - preserve timeframe integrity!
        validated_data = {}
        quality_scores = []

        # Validate and ensure UTC timezone for each timeframe
        for timeframe, data in data_dict.items():
            try:
                # Ensure timezone consistency (UTC) but don't modify temporal structure
                validated_data[timeframe] = self._ensure_utc_timezone(data, timeframe)
                quality_scores.append(1.0)  # All timeframes are valid as-is
                logger.debug(f"Validated {timeframe}: {len(data)} bars preserved")

            except Exception as e:
                logger.warning(f"Failed to validate {timeframe}: {e}")
                # Include original data if validation fails
                validated_data[timeframe] = data
                quality_scores.append(0.5)  # Penalty for validation failure

        # Create statistics (no actual alignment performed)
        processing_time = time.time() - start_time
        # successfully_aligned should be the number of non-reference timeframes (since we don't align)
        non_reference_count = len(data_dict) - 1  # Exclude reference timeframe
        stats = SynchronizationStats(
            total_timeframes=len(data_dict),
            successfully_aligned=max(
                0, non_reference_count
            ),  # Only count non-reference timeframes
            failed_alignments=0,  # No alignment failures since we don't align
            reference_timeframe=reference_timeframe,
            reference_periods=len(data_dict[reference_timeframe]),
            average_quality_score=np.mean(quality_scores) if quality_scores else 1.0,
            processing_time=processing_time,
        )

        logger.info(
            f"Validated {len(data_dict)} timeframes in {processing_time:.2f}s. "
            f"Timeframes preserved: {list(validated_data.keys())}, "
            f"Avg Quality: {stats.average_quality_score:.3f}"
        )

        return validated_data, stats

    def interpolate_missing_data(
        self, data: pd.DataFrame, method: str = "linear", limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Interpolate missing data using specified method.

        Args:
            data: DataFrame with potential missing values
            method: Interpolation method ('linear', 'time', 'cubic', etc.)
            limit: Maximum number of consecutive NaNs to fill

        Returns:
            DataFrame with interpolated values
        """
        interpolated_data = data.interpolate(
            method=method, limit=limit, limit_direction="both"
        )

        # Log interpolation statistics
        original_missing = data.isnull().sum().sum()
        remaining_missing = interpolated_data.isnull().sum().sum()
        filled_count = original_missing - remaining_missing

        if filled_count > 0:
            logger.info(
                f"Interpolated {filled_count} missing values using {method} method. "
                f"Remaining missing: {remaining_missing}"
            )

        return interpolated_data

    def validate_temporal_consistency(
        self, data_dict: dict[str, pd.DataFrame], tolerance_minutes: int = 1
    ) -> dict[str, bool]:
        """
        Validate temporal consistency across timeframes.

        Args:
            data_dict: Dictionary of timeframe data
            tolerance_minutes: Tolerance for timestamp alignment (minutes)

        Returns:
            Dictionary mapping timeframes to consistency status
        """
        consistency_results = {}

        for timeframe, data in data_dict.items():
            try:
                # Check if timestamps are properly spaced for timeframe
                expected_delta = pd.Timedelta(
                    minutes=self.TIMEFRAME_MULTIPLIERS.get(timeframe, 60)
                )

                if len(data) < 2:
                    consistency_results[timeframe] = True
                    continue

                # Calculate actual deltas
                actual_deltas = data.index.to_series().diff().dropna()

                # Check if most deltas are within tolerance of expected
                tolerance = pd.Timedelta(minutes=tolerance_minutes)
                consistent_count = (
                    (actual_deltas - expected_delta).abs() <= tolerance
                ).sum()
                consistency_ratio = consistent_count / len(actual_deltas)

                # Consider consistent if >90% of deltas are correct
                is_consistent = consistency_ratio >= 0.9
                consistency_results[timeframe] = is_consistent

                if not is_consistent:
                    logger.warning(
                        f"Timeframe {timeframe} has poor temporal consistency: "
                        f"{consistency_ratio:.2%} of timestamps are properly spaced"
                    )

            except Exception as e:
                logger.warning(f"Failed to validate consistency for {timeframe}: {e}")
                consistency_results[timeframe] = False

        return consistency_results

    def _validate_alignment_inputs(
        self,
        source_data: pd.DataFrame,
        reference_data: pd.DataFrame,
        source_timeframe: str,
        reference_timeframe: str,
    ) -> None:
        """Validate inputs for alignment operation."""
        if source_data.empty:
            raise DataValidationError("Source data cannot be empty")

        if reference_data.empty:
            raise DataValidationError("Reference data cannot be empty")

        if not isinstance(source_data.index, pd.DatetimeIndex):
            raise DataValidationError("Source data must have DatetimeIndex")

        if not isinstance(reference_data.index, pd.DatetimeIndex):
            raise DataValidationError("Reference data must have DatetimeIndex")

        if source_timeframe not in self.TIMEFRAME_MULTIPLIERS:
            raise DataValidationError(
                f"Unsupported source timeframe: {source_timeframe}"
            )

        if reference_timeframe not in self.TIMEFRAME_MULTIPLIERS:
            raise DataValidationError(
                f"Unsupported reference timeframe: {reference_timeframe}"
            )

    def _ensure_utc_timezone(self, data: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Ensure data has UTC timezone."""
        if data.index.tz is None:
            # Localize to UTC
            data = data.copy()
            data.index = data.index.tz_localize("UTC")
            logger.debug(f"Localized {timeframe} data to UTC")
        elif str(data.index.tz) != "UTC":
            # Convert to UTC
            data = data.copy()
            data.index = data.index.tz_convert("UTC")
            logger.debug(f"Converted {timeframe} data to UTC from {data.index.tz}")

        return data

    def _calculate_alignment_quality(
        self,
        aligned_data: pd.DataFrame,
        source_data: pd.DataFrame,
        missing_ratio: float,
    ) -> float:
        """
        Calculate quality score for alignment operation.

        Quality score is based on:
        - Missing data ratio (lower is better)
        - Data coverage (higher is better)
        - Timestamp consistency

        Returns:
            Quality score between 0.0 and 1.0
        """
        # Base score from missing data (inverted)
        missing_penalty = missing_ratio

        # Coverage score (how much of the reference timeline is covered)
        coverage_score = (
            min(1.0, len(source_data) / len(aligned_data))
            if len(aligned_data) > 0
            else 0
        )

        # Combine scores with weights
        quality_score = (
            0.6 * (1.0 - missing_penalty)  # 60% weight on completeness
            + 0.4 * coverage_score  # 40% weight on coverage
        )

        return max(0.0, min(1.0, quality_score))

    @staticmethod
    def get_optimal_reference_timeframe(timeframes: list[str]) -> str:
        """
        Get the optimal reference timeframe for synchronization.

        The optimal reference is typically the lowest (most granular) timeframe
        as it provides the most detailed timeline for alignment.

        Args:
            timeframes: List of available timeframes

        Returns:
            Optimal reference timeframe

        Raises:
            ValueError: If no valid timeframes provided
        """
        if not timeframes:
            raise ValueError("No timeframes provided")

        # Filter to supported timeframes only
        supported_timeframes = [
            tf for tf in timeframes if tf in TimeframeSynchronizer.TIMEFRAME_HIERARCHY
        ]

        if not supported_timeframes:
            raise ValueError("No supported timeframes found")

        # Return the lowest timeframe (most granular)
        hierarchy_positions = [
            (tf, TimeframeSynchronizer.TIMEFRAME_HIERARCHY.index(tf))
            for tf in supported_timeframes
        ]
        hierarchy_positions.sort(key=lambda x: x[1])

        optimal_timeframe = hierarchy_positions[0][0]
        logger.info(f"Selected {optimal_timeframe} as optimal reference timeframe")

        return optimal_timeframe

    @staticmethod
    def estimate_memory_usage(
        data_dict: dict[str, pd.DataFrame], target_timeframe: str
    ) -> dict[str, float]:
        """
        Estimate memory usage for synchronization operation.

        Args:
            data_dict: Dictionary of timeframe data
            target_timeframe: Target timeframe for synchronization

        Returns:
            Dictionary with memory usage estimates in MB
        """
        estimates = {}

        if target_timeframe not in data_dict:
            return estimates

        reference_size = len(data_dict[target_timeframe])

        for timeframe, data in data_dict.items():
            # Estimate aligned data size
            if timeframe == target_timeframe:
                aligned_size = len(data)
            else:
                aligned_size = reference_size

            # Estimate memory (assuming float64 = 8 bytes per value)
            columns = len(data.columns) if not data.empty else 5  # OHLCV default
            bytes_per_row = columns * 8  # 8 bytes per float64
            estimated_mb = (aligned_size * bytes_per_row) / (1024 * 1024)

            estimates[timeframe] = estimated_mb

        estimates["total_estimated"] = sum(estimates.values())

        return estimates


# Utility functions for common operations
def align_timeframes_to_lowest(
    data_dict: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], str]:
    """
    Align all timeframes to the lowest (most granular) timeframe.

    Args:
        data_dict: Dictionary of timeframe data

    Returns:
        Tuple of (aligned_data, reference_timeframe)
    """
    synchronizer = TimeframeSynchronizer()
    reference_timeframe = synchronizer.get_optimal_reference_timeframe(
        list(data_dict.keys())
    )

    # Get reference data
    reference_data = data_dict[reference_timeframe]
    aligned_data = {reference_timeframe: reference_data}  # Reference stays unchanged

    # Align all other timeframes to reference
    for timeframe, data in data_dict.items():
        if timeframe != reference_timeframe:
            alignment_result = synchronizer.forward_fill_alignment(
                data, reference_data, timeframe, reference_timeframe
            )
            aligned_data[timeframe] = alignment_result.aligned_data

    return aligned_data, reference_timeframe


def calculate_multi_timeframe_periods(
    primary_timeframe: str, auxiliary_timeframes: list[str], primary_periods: int
) -> dict[str, int]:
    """
    Calculate required periods for all auxiliary timeframes.

    Args:
        primary_timeframe: Primary timeframe
        auxiliary_timeframes: List of auxiliary timeframes
        primary_periods: Periods needed in primary timeframe

    Returns:
        Dictionary mapping timeframes to required periods
    """
    periods_dict = {primary_timeframe: primary_periods}

    for aux_tf in auxiliary_timeframes:
        periods_dict[aux_tf] = TimeframeSynchronizer.calculate_periods_needed(
            primary_timeframe, aux_tf, primary_periods
        )

    return periods_dict


def validate_timeframe_compatibility(timeframes: list[str]) -> list[str]:
    """
    Validate and filter compatible timeframes.

    Args:
        timeframes: List of timeframes to validate

    Returns:
        List of validated, compatible timeframes
    """
    compatible_timeframes = []

    for tf in timeframes:
        if tf in TimeframeSynchronizer.TIMEFRAME_MULTIPLIERS:
            compatible_timeframes.append(tf)
        else:
            logger.warning(f"Incompatible timeframe ignored: {tf}")

    return compatible_timeframes

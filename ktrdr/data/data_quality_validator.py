"""
Unified Data Quality Validator for OHLCV financial data.

This module provides comprehensive data quality validation that can be used
by both IB data fetching and local CSV data loading, consolidating and enhancing
the validation logic previously scattered across different components.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ktrdr.logging import get_logger
from ktrdr.utils.timezone_utils import TimestampManager

logger = get_logger(__name__)


class DataQualityIssue:
    """Represents a data quality issue found during validation."""

    def __init__(
        self,
        issue_type: str,
        severity: str,
        description: str,
        location: Optional[str] = None,
        corrected: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize data quality issue.

        Args:
            issue_type: Type of issue (gap, ohlc_invalid, duplicate, etc.)
            severity: Severity level (low, medium, high, critical)
            description: Human-readable description
            location: Location in data where issue occurs
            corrected: Whether the issue was auto-corrected
            metadata: Additional metadata about the issue
        """
        self.issue_type = issue_type
        self.severity = severity
        self.description = description
        self.location = location
        self.corrected = corrected
        self.metadata = metadata or {}
        self.timestamp = TimestampManager.now_utc()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/reporting."""
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "description": self.description,
            "location": self.location,
            "corrected": self.corrected,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class DataQualityReport:
    """Comprehensive data quality report."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        total_bars: int,
        validation_type: str = "general",
    ):
        """
        Initialize quality report.

        Args:
            symbol: Symbol validated
            timeframe: Timeframe validated
            total_bars: Total number of bars in dataset
            validation_type: Type of validation (ib, local, general)
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.total_bars = total_bars
        self.validation_type = validation_type
        self.issues: list[DataQualityIssue] = []
        self.corrections_made = 0
        self.validation_time = TimestampManager.now_utc()

    def add_issue(self, issue: DataQualityIssue):
        """Add a quality issue to the report."""
        self.issues.append(issue)
        if issue.corrected:
            self.corrections_made += 1

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics for the report."""
        issues_by_severity: dict[str, int] = {}
        issues_by_type: dict[str, int] = {}

        for issue in self.issues:
            # Count by severity
            issues_by_severity[issue.severity] = (
                issues_by_severity.get(issue.severity, 0) + 1
            )
            # Count by type
            issues_by_type[issue.issue_type] = (
                issues_by_type.get(issue.issue_type, 0) + 1
            )

        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "total_bars": self.total_bars,
            "validation_type": self.validation_type,
            "total_issues": len(self.issues),
            "corrections_made": self.corrections_made,
            "issues_by_severity": issues_by_severity,
            "issues_by_type": issues_by_type,
            "validation_time": self.validation_time.isoformat(),
        }

    def is_healthy(self, max_critical: int = 0, max_high: int = 5) -> bool:
        """
        Check if data is considered healthy based on issue thresholds.

        Args:
            max_critical: Maximum allowed critical issues
            max_high: Maximum allowed high severity issues

        Returns:
            True if data passes health checks

        Note:
            "info" level issues are not counted as health problems
        """
        critical_count = sum(1 for issue in self.issues if issue.severity == "critical")
        high_count = sum(1 for issue in self.issues if issue.severity == "high")

        return critical_count <= max_critical and high_count <= max_high

    def get_issues_by_type(self, issue_type: str) -> list[DataQualityIssue]:
        """Get all issues of a specific type."""
        return [issue for issue in self.issues if issue.issue_type == issue_type]

    def get_issues_by_severity(self, severity: str) -> list[DataQualityIssue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]


class DataQualityValidator:
    """
    Unified data quality validator for OHLCV financial data.

    Consolidates validation logic from DataManager and IbDataValidator,
    providing comprehensive data quality checking for both IB and local data.
    """

    def __init__(self, auto_correct: bool = True, max_gap_percentage: float = 10.0):
        """
        Initialize data quality validator.

        Args:
            auto_correct: Whether to automatically correct minor issues
            max_gap_percentage: Maximum acceptable gap percentage
        """
        self.auto_correct = auto_correct
        self.max_gap_percentage = max_gap_percentage
        self.validation_count = 0

        logger.info(f"DataQualityValidator initialized (auto_correct={auto_correct})")

    def validate_data(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        validation_type: str = "general",
    ) -> tuple[pd.DataFrame, DataQualityReport]:
        """
        Perform comprehensive data quality validation.

        Args:
            df: DataFrame with OHLCV data to validate
            symbol: Symbol being validated
            timeframe: Timeframe of the data
            validation_type: Type of validation (ib, local, general)

        Returns:
            Tuple of (corrected_dataframe, quality_report)
        """
        self.validation_count += 1
        logger.info(
            f"Starting data quality validation for {symbol} {timeframe} ({len(df)} bars, type: {validation_type})"
        )

        # Initialize quality report
        report = DataQualityReport(symbol, timeframe, len(df), validation_type)

        if df.empty:
            issue = DataQualityIssue(
                issue_type="empty_dataset",
                severity="critical",
                description="Dataset is empty",
                location="entire dataset",
            )
            report.add_issue(issue)
            return df, report

        # Start with original data
        df_validated = df.copy()

        try:
            # 1. Basic structure validation
            df_validated = self._validate_basic_structure(df_validated, report)

            # 2. Handle duplicates
            df_validated = self._detect_and_fix_duplicates(df_validated, report)

            # 3. Sort index if needed
            df_validated = self._ensure_sorted_index(df_validated, report)

            # 4. Validate OHLC relationships
            df_validated = self._validate_ohlc_relationships(df_validated, report)

            # 5. Detect and handle missing values
            df_validated = self._handle_missing_values(df_validated, report)

            # 6. Detect timestamp gaps
            self._detect_timestamp_gaps(df_validated, timeframe, symbol, report)

            # 7. Detect price outliers and anomalies
            self._detect_price_outliers(df_validated, report)

            # 8. Validate volume patterns
            df_validated = self._validate_volume_patterns(df_validated, report)

            # 9. Check for extreme price movements
            self._detect_extreme_price_movements(df_validated, report)

            # Generate summary
            summary = report.get_summary()
            logger.info(
                f"Validation complete: {summary['total_issues']} issues found, {summary['corrections_made']} corrected"
            )

            if not report.is_healthy():
                logger.warning(f"Data quality check failed for {symbol} {timeframe}")
            else:
                logger.info(f"Data quality check passed for {symbol} {timeframe}")

            return df_validated, report

        except Exception as e:
            logger.error(f"Error during data validation: {e}")
            issue = DataQualityIssue(
                issue_type="validation_error",
                severity="critical",
                description=f"Validation failed: {str(e)}",
                location="validation process",
            )
            report.add_issue(issue)
            return df, report

    def _validate_basic_structure(
        self, df: pd.DataFrame, report: DataQualityReport
    ) -> pd.DataFrame:
        """Validate basic DataFrame structure."""
        logger.debug("Validating basic structure")

        # Check required columns
        required_columns = ["open", "high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            issue = DataQualityIssue(
                issue_type="missing_columns",
                severity="critical",
                description=f"Missing required columns: {missing_columns}",
                location="dataframe structure",
                metadata={"missing_columns": missing_columns},
            )
            report.add_issue(issue)

        # Check index type
        if not isinstance(df.index, pd.DatetimeIndex):
            issue = DataQualityIssue(
                issue_type="invalid_index_type",
                severity="high",
                description=f"Index is not DatetimeIndex: {type(df.index)}",
                location="dataframe index",
            )
            report.add_issue(issue)

        return df

    def _detect_and_fix_duplicates(
        self, df: pd.DataFrame, report: DataQualityReport
    ) -> pd.DataFrame:
        """Detect and handle duplicate timestamps."""
        logger.debug("Detecting duplicate timestamps")

        if df.index.duplicated().any():
            duplicate_count = df.index.duplicated().sum()
            issue = DataQualityIssue(
                issue_type="duplicate_timestamps",
                severity="medium",
                description=f"{duplicate_count} duplicate timestamps found",
                location="index",
                corrected=self.auto_correct,
                metadata={"duplicate_count": duplicate_count},
            )
            report.add_issue(issue)

            if self.auto_correct:
                # Keep last occurrence of duplicates
                df_corrected = df[~df.index.duplicated(keep="last")]
                logger.warning(f"Removed {duplicate_count} duplicate timestamps")
                return df_corrected

        return df

    def _ensure_sorted_index(
        self, df: pd.DataFrame, report: DataQualityReport
    ) -> pd.DataFrame:
        """Ensure index is sorted chronologically."""
        logger.debug("Checking index sort order")

        if not df.index.is_monotonic_increasing:
            issue = DataQualityIssue(
                issue_type="unsorted_index",
                severity="medium",
                description="Index is not sorted in ascending order",
                location="index",
                corrected=self.auto_correct,
            )
            report.add_issue(issue)

            if self.auto_correct:
                df_sorted = df.sort_index()
                logger.warning("Sorted index to ascending order")
                return df_sorted

        return df

    def _validate_ohlc_relationships(
        self, df: pd.DataFrame, report: DataQualityReport
    ) -> pd.DataFrame:
        """Validate OHLC price relationships."""
        logger.debug("Validating OHLC relationships")
        df_corrected = df.copy()

        # Check for non-positive prices
        price_cols = ["open", "high", "low", "close"]
        for col in price_cols:
            if col in df.columns:
                non_positive = df[col] <= 0
                if non_positive.any():
                    count = non_positive.sum()
                    issue = DataQualityIssue(
                        issue_type="non_positive_price",
                        severity="critical",
                        description=f"{count} bars with non-positive {col} prices",
                        location=f"{col} column",
                        corrected=self.auto_correct,
                        metadata={"count": count, "column": col},
                    )
                    report.add_issue(issue)

                    if self.auto_correct:
                        # Replace with NaN for interpolation later
                        df_corrected.loc[non_positive, col] = np.nan
                        logger.warning(f"Corrected {count} non-positive {col} prices")

        # Check for negative volume (IB data indicators)
        if "volume" in df.columns:
            negative_volume = df["volume"] < 0
            no_data_volume = (
                df["volume"] == -1
            )  # IB's explicit "no data available" indicator
            other_negative = negative_volume & ~no_data_volume

            if negative_volume.any():
                count = negative_volume.sum()
                no_data_count = no_data_volume.sum()
                other_neg_count = other_negative.sum()

                # Log summary of negative volume values found
                if no_data_count > 0:
                    logger.debug(
                        f"Found {no_data_count} bars with volume=-1 (IB indicators)"
                    )
                if other_neg_count > 0:
                    logger.debug(
                        f"Found {other_neg_count} bars with invalid negative volumes"
                    )

                # Different treatment for volume=-1 vs other negative volumes
                if other_neg_count > 0:
                    # Other negative volumes are actual data quality issues
                    issue = DataQualityIssue(
                        issue_type="invalid_negative_volume",
                        severity="medium",
                        description=f"{other_neg_count} bars with invalid negative volumes (not -1)",
                        location="volume column",
                        corrected=self.auto_correct,
                        metadata={
                            "invalid_negative_count": other_neg_count,
                            "note": "Negative volumes other than -1 indicate data corruption",
                        },
                    )
                    report.add_issue(issue)

                    if self.auto_correct:
                        # Only correct non-(-1) negative volumes
                        df_corrected.loc[other_negative, "volume"] = 0
                        logger.warning(
                            f"Corrected {other_neg_count} invalid negative volume values to 0"
                        )

                if no_data_count > 0:
                    # Volume=-1 is informational, not an error to be "corrected"
                    issue = DataQualityIssue(
                        issue_type="ib_volume_indicator",
                        severity="info",  # Changed from "low" to "info" - this is not an error
                        description=f"{no_data_count} bars with volume=-1 (IB 'volume data not available' indicator)",
                        location="volume column",
                        corrected=False,  # Don't "correct" this - it's valid IB data
                        metadata={
                            "ib_no_data_count": no_data_count,
                            "note": "Volume=-1 is IB's way of indicating 'volume data not available' but price data is valid",
                        },
                    )
                    report.add_issue(issue)

                    logger.info(
                        f"📊 IB Volume Indicator: {no_data_count} bars have volume=-1 (volume data not available, price data valid)"
                    )
                    # DO NOT AUTO-CORRECT volume=-1 - it's valid IB data indicating no volume info available

        # Check OHLC relationships (only where all values are valid)
        if all(col in df.columns for col in ["open", "high", "low", "close"]):
            # High should be >= max(open, close)
            max_oc = np.maximum(df["open"], df["close"])
            high_too_low = (df["high"] < max_oc) & df[
                ["open", "high", "low", "close"]
            ].notna().all(axis=1)

            if high_too_low.any():
                count = high_too_low.sum()
                issue = DataQualityIssue(
                    issue_type="high_too_low",
                    severity="high",
                    description=f"{count} bars where high < max(open, close)",
                    location="high vs open/close",
                    corrected=self.auto_correct,
                    metadata={"count": count},
                )
                report.add_issue(issue)

                if self.auto_correct:
                    df_corrected.loc[high_too_low, "high"] = max_oc[high_too_low]
                    logger.warning(f"Corrected {count} high prices that were too low")

            # Low should be <= min(open, close)
            min_oc = np.minimum(df["open"], df["close"])
            low_too_high = (df["low"] > min_oc) & df[
                ["open", "high", "low", "close"]
            ].notna().all(axis=1)

            if low_too_high.any():
                count = low_too_high.sum()
                issue = DataQualityIssue(
                    issue_type="low_too_high",
                    severity="high",
                    description=f"{count} bars where low > min(open, close)",
                    location="low vs open/close",
                    corrected=self.auto_correct,
                    metadata={"count": count},
                )
                report.add_issue(issue)

                if self.auto_correct:
                    df_corrected.loc[low_too_high, "low"] = min_oc[low_too_high]
                    logger.warning(f"Corrected {count} low prices that were too high")

        return df_corrected

    def _handle_missing_values(
        self, df: pd.DataFrame, report: DataQualityReport
    ) -> pd.DataFrame:
        """Detect and handle missing values."""
        logger.debug("Handling missing values")

        df_corrected = df.copy()
        price_cols = ["open", "high", "low", "close"]

        for col in price_cols:
            if col in df.columns:
                missing_count = df[col].isna().sum()
                if missing_count > 0:
                    missing_percentage = (missing_count / len(df)) * 100

                    # Determine if we can correct this
                    can_correct = self.auto_correct and missing_percentage < 10.0
                    severity = "high" if missing_percentage >= 10.0 else "medium"

                    issue = DataQualityIssue(
                        issue_type="missing_values",
                        severity=severity,
                        description=f"{missing_count} missing values in {col} ({missing_percentage:.1f}%)",
                        location=f"{col} column",
                        corrected=can_correct,
                        metadata={
                            "count": missing_count,
                            "percentage": missing_percentage,
                            "column": col,
                        },
                    )
                    report.add_issue(issue)

                    if can_correct:
                        # Use linear interpolation for price data
                        df_corrected[col] = df_corrected[col].interpolate(
                            method="linear"
                        )
                        logger.info(
                            f"Interpolated {missing_count} missing values in {col}"
                        )

        return df_corrected

    def _detect_timestamp_gaps(
        self, df: pd.DataFrame, timeframe: str, symbol: str, report: DataQualityReport
    ):
        """Detect gaps in time series data using intelligent gap classification."""
        logger.debug("Detecting timestamp gaps using intelligent gap classifier")

        if df.empty or len(df) <= 1:
            return

        # Use the existing gap classifier for intelligent detection
        from ktrdr.data.gap_classifier import GapClassification, GapClassifier

        gap_classifier = GapClassifier()

        # Get data range
        start_date = df.index.min()
        end_date = df.index.max()

        # Convert to datetime if needed
        if isinstance(start_date, pd.Timestamp):
            start_date = start_date.to_pydatetime()
        if isinstance(end_date, pd.Timestamp):
            end_date = end_date.to_pydatetime()

        # Ensure timezone awareness
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=pd.Timestamp.now().tz)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=pd.Timestamp.now().tz)

        # For data quality validation, we'll detect gaps using basic logic but filter using intelligent classification
        # This maintains compatibility while using intelligent gap analysis

        # Get the pandas frequency string for this timeframe using centralized constants
        timeframe_frequencies = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1h",
            "4h": "4h",
            "1d": "1D",
            "1w": "1W",
        }
        freq = timeframe_frequencies.get(timeframe)
        if not freq:
            logger.warning(
                f"Unknown timeframe '{timeframe}', gap detection may be inaccurate"
            )
            # Try to infer the frequency from the data
            freq = pd.infer_freq(df.index)
            if not freq:
                logger.warning(
                    "Could not infer frequency from data, using '1D' as fallback"
                )
                freq = "1D"

        # Create the expected complete index
        expected_index = pd.date_range(start=start_date, end=end_date, freq=freq)

        # Find missing times
        missing_times = expected_index.difference(df.index)

        # Group consecutive missing times into gaps
        raw_gaps = []
        if len(missing_times) > 0:
            gap_start = missing_times[0]
            prev_time = gap_start

            for i in range(1, len(missing_times)):
                current_time = missing_times[i]
                expected_diff = pd.Timedelta(freq)

                # If there's a gap between missing times, this means we have two separate gaps
                if current_time - prev_time > expected_diff:
                    # Record the previous gap
                    raw_gaps.append((gap_start, prev_time))
                    # Start a new gap
                    gap_start = current_time

                prev_time = current_time

            # Add the last gap
            raw_gaps.append((gap_start, prev_time))

        # Filter gaps using intelligent classification
        # Only report unexpected gaps and market closures for data quality issues
        significant_gaps = []
        for gap_start, gap_end in raw_gaps:
            # Convert to datetime for gap classifier
            gap_start_dt = (
                gap_start.to_pydatetime()
                if hasattr(gap_start, "to_pydatetime")
                else gap_start
            )
            gap_end_dt = (
                gap_end.to_pydatetime()
                if hasattr(gap_end, "to_pydatetime")
                else gap_end
            )

            # Ensure timezone awareness
            if gap_start_dt.tzinfo is None:
                gap_start_dt = gap_start_dt.replace(tzinfo=start_date.tzinfo)
            if gap_end_dt.tzinfo is None:
                gap_end_dt = gap_end_dt.replace(tzinfo=end_date.tzinfo)

            # Use the actual symbol for intelligent gap classification, pass context data for volume analysis
            gap_info = gap_classifier.analyze_gap(
                gap_start_dt, gap_end_dt, symbol, timeframe, df
            )

            # Only include unexpected gaps and market closures in data quality issues
            if gap_info.classification in [
                GapClassification.UNEXPECTED,
                GapClassification.MARKET_CLOSURE,
            ]:
                significant_gaps.append((gap_start, gap_end))
                logger.debug(
                    f"Significant gap: {gap_start} to {gap_end} ({gap_info.classification.value})"
                )
            else:
                logger.debug(
                    f"Expected gap filtered out: {gap_start} to {gap_end} ({gap_info.classification.value})"
                )

        # Report only significant gaps
        if significant_gaps:
            # Calculate percentage based on significant gaps only
            significant_missing = sum(
                len(pd.date_range(start=gap_start, end=gap_end, freq=freq)) - 1
                for gap_start, gap_end in significant_gaps
            )
            gap_percentage = (significant_missing / len(expected_index)) * 100

            # Determine severity based on gap percentage
            if gap_percentage > self.max_gap_percentage:
                severity = "high"
            elif gap_percentage > 5.0:
                severity = "medium"
            else:
                severity = "low"

            issue = DataQualityIssue(
                issue_type="timestamp_gaps",
                severity=severity,
                description=f"{len(significant_gaps)} significant gaps detected ({significant_missing} missing periods, {gap_percentage:.2f}%)",
                location="time series",
                metadata={
                    "gap_count": len(significant_gaps),
                    "missing_periods": significant_missing,
                    "gap_percentage": gap_percentage,
                    "total_raw_gaps": len(raw_gaps),
                    "filtered_expected_gaps": len(raw_gaps) - len(significant_gaps),
                    "gaps": [
                        (start.isoformat(), end.isoformat())
                        for start, end in significant_gaps[:5]
                    ],  # First 5 significant gaps
                },
            )
            report.add_issue(issue)

            logger.info(
                f"Detected {len(significant_gaps)} significant gaps out of {len(raw_gaps)} total gaps "
                f"({significant_missing} missing periods, {gap_percentage:.2f}% missing) using intelligent classification"
            )
        else:
            if raw_gaps:
                logger.info(
                    f"Found {len(raw_gaps)} gaps but all were classified as expected (weekends, holidays, etc.) - no data quality issues"
                )

    def _detect_price_outliers(
        self,
        df: pd.DataFrame,
        report: DataQualityReport,
        std_threshold: float = 2.5,
        context_window: Optional[int] = None,
    ):
        """Detect price outliers using Z-score method (enhanced from DataManager)."""
        logger.debug("Detecting price outliers")

        if df.empty:
            return

        columns = ["open", "high", "low", "close"]
        columns = [col for col in columns if col in df.columns]

        if not columns:
            logger.warning("No valid columns for outlier detection")
            return

        outlier_count = 0

        for col in columns:
            if context_window and len(df) > context_window:
                # Context-aware detection: Use rolling statistics
                rolling_mean = (
                    df[col].rolling(window=context_window, min_periods=3).mean()
                )
                rolling_std = (
                    df[col].rolling(window=context_window, min_periods=3).std()
                )

                # Calculate Z-scores using rolling statistics
                z_scores = np.abs((df[col] - rolling_mean) / rolling_std)
            else:
                # Global statistics
                mean_val = df[col].mean()
                std_val = df[col].std()

                if std_val == 0 or pd.isna(std_val):
                    continue  # Skip if no variation or invalid std

                # Calculate Z-scores using global statistics
                z_scores = np.abs((df[col] - mean_val) / std_val)

            # Find outliers (handle NaN values)
            outliers = (z_scores > std_threshold) & ~pd.isna(z_scores)
            if outliers.any():
                count = outliers.sum()
                outlier_count += count
                max_z_score = z_scores[~pd.isna(z_scores)].max()

                severity = "high" if max_z_score > 5.0 else "medium"

                logger.debug(
                    f"Found {count} outliers in {col}: mean={mean_val:.2f}, std={std_val:.2f}, max_z={max_z_score:.2f}"
                )

                issue = DataQualityIssue(
                    issue_type="price_outliers",
                    severity=severity,
                    description=f"{count} outliers in {col} (max Z-score: {max_z_score:.2f})",
                    location=f"{col} column",
                    metadata={
                        "count": count,
                        "column": col,
                        "max_z_score": max_z_score,
                        "threshold": std_threshold,
                        "context_window": context_window,
                    },
                )
                report.add_issue(issue)

        if outlier_count > 0:
            logger.info(f"Detected {outlier_count} price outliers")

    def _validate_volume_patterns(
        self, df: pd.DataFrame, report: DataQualityReport
    ) -> pd.DataFrame:
        """Validate volume patterns and detect anomalies."""
        logger.debug("Validating volume patterns")

        if "volume" not in df.columns or len(df) < 2:
            return df

        df_corrected = df.copy()

        # Check for zero volume bars
        zero_volume = df["volume"] == 0
        if zero_volume.any():
            count = zero_volume.sum()
            percentage = (count / len(df)) * 100

            if percentage > 50:
                severity = "high"
            elif percentage > 20:
                severity = "medium"
            else:
                severity = "low"

            issue = DataQualityIssue(
                issue_type="zero_volume",
                severity=severity,
                description=f"{count} bars ({percentage:.1f}%) with zero volume",
                location="volume column",
                metadata={"count": count, "percentage": percentage},
            )
            report.add_issue(issue)

        # Check for extreme volume spikes
        volume_median = df["volume"].median()
        if volume_median > 0:
            volume_ratio = df["volume"] / volume_median
            extreme_volume = volume_ratio > 100  # 100x median volume

            if extreme_volume.any():
                count = extreme_volume.sum()
                max_ratio = volume_ratio.max()

                issue = DataQualityIssue(
                    issue_type="extreme_volume_spike",
                    severity="medium",
                    description=f"{count} bars with extreme volume (max: {max_ratio:.0f}x median)",
                    location="volume spikes",
                    metadata={
                        "count": count,
                        "max_ratio": max_ratio,
                        "median_volume": volume_median,
                    },
                )
                report.add_issue(issue)

        return df_corrected

    def _detect_extreme_price_movements(
        self, df: pd.DataFrame, report: DataQualityReport
    ):
        """Detect extreme price movements."""
        logger.debug("Detecting extreme price movements")

        if len(df) < 2 or "close" not in df.columns:
            return

        # Calculate price change percentages
        price_changes = df["close"].pct_change(fill_method=None)

        # Define thresholds
        extreme_threshold = 0.20  # 20% change
        suspicious_threshold = 0.10  # 10% change

        # Find extreme price movements
        extreme_moves = np.abs(price_changes) > extreme_threshold
        if extreme_moves.any():
            count = extreme_moves.sum()
            max_change = np.abs(price_changes).max()

            issue = DataQualityIssue(
                issue_type="extreme_price_movement",
                severity="high",
                description=f"{count} bars with >20% price change (max: {max_change:.1%})",
                location="close price changes",
                metadata={
                    "count": count,
                    "max_change": max_change,
                    "threshold": extreme_threshold,
                },
            )
            report.add_issue(issue)

            # Log extreme movements for review
            for idx in df.index[extreme_moves]:
                change = price_changes.loc[idx]
                logger.warning(f"Extreme price movement at {idx}: {change:.1%}")

        # Find suspicious but not extreme movements
        suspicious_moves = (
            np.abs(price_changes) > suspicious_threshold
        ) & ~extreme_moves
        if suspicious_moves.any():
            count = suspicious_moves.sum()

            issue = DataQualityIssue(
                issue_type="suspicious_price_movement",
                severity="medium",
                description=f"{count} bars with >10% price change",
                location="close price changes",
                metadata={"count": count, "threshold": suspicious_threshold},
            )
            report.add_issue(issue)

    def get_validation_statistics(self) -> dict[str, Any]:
        """Get validation statistics."""
        return {
            "total_validations": self.validation_count,
            "auto_correct_enabled": self.auto_correct,
            "max_gap_percentage": self.max_gap_percentage,
        }

"""
DataValidator Component

Consolidates data validation logic extracted from DataManager into a dedicated,
focused component that provides comprehensive market data validation, quality checks,
and compliance verification.

This component follows the async architecture specification:
- Sync Computer Pattern: Pure validation computations
- Clear separation: Validation logic vs orchestration
- Reuses existing DataQualityValidator for OHLCV validation
"""

import asyncio
import concurrent.futures
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any, Union

import numpy as np
import pandas as pd

from ktrdr.data.data_quality_validator import (
    DataQualityValidator,
    DataQualityReport,
    DataQualityIssue,
)
from ktrdr.data.components.data_processor import ValidationResult
from ktrdr.errors import DataValidationError
from ktrdr.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationConfig:
    """Configuration for DataValidator component."""

    strict_ohlc: bool = True
    max_price_gap_percent: float = 20.0
    min_volume_threshold: int = 0
    validate_market_hours: bool = True
    weekend_data_allowed: bool = False
    max_consecutive_zeros: int = 5
    auto_correct: bool = True
    max_gap_percentage: float = 10.0
    enable_head_timestamp_validation: bool = True


@dataclass
class ValidationError:
    """Represents a validation error with context."""

    error_type: str
    message: str
    location: Optional[str] = None
    severity: str = "medium"
    metadata: Optional[dict] = None

    def __str__(self) -> str:
        return f"{self.error_type}: {self.message}"


@dataclass
class ValidationStatistics:
    """Statistics about validation results."""

    total_bars: int
    issues_found: int
    corrections_made: int
    validation_time_ms: float


@dataclass
class ValidationReport:
    """Comprehensive validation report."""

    is_valid: bool
    symbol: str
    timeframe: str
    errors: List[ValidationError]
    warnings: List[ValidationError]
    statistics: ValidationStatistics
    recommendations: List[str]
    quality_report: Optional[DataQualityReport] = None


@dataclass
class RangeValidationResult:
    """Result of request range validation."""

    is_valid: bool
    error_message: Optional[str] = None
    adjusted_start_date: Optional[datetime] = None


class DataValidator:
    """
    DataValidator component for comprehensive market data validation.

    Consolidates validation logic previously scattered in DataManager,
    providing a unified interface for all data validation needs while
    reusing the existing DataQualityValidator infrastructure.

    Architecture:
    - Sync Computer Pattern: All validation methods are synchronous
    - External I/O: Async operations delegated to injected providers
    - Clear boundaries: Pure validation vs orchestration logic
    """

    def __init__(self, config: ValidationConfig):
        """
        Initialize DataValidator with configuration.

        Args:
            config: Validation configuration options
        """
        self.config = config
        self.data_quality_validator = DataQualityValidator(
            auto_correct=config.auto_correct,
            max_gap_percentage=config.max_gap_percentage,
        )
        self.external_provider = None  # Injected dependency for async operations
        self._lock = threading.RLock()  # Thread safety
        self.validation_count = 0

        logger.info(f"DataValidator initialized with config: {config}")

    def set_external_provider(self, provider):
        """Set external data provider for async operations."""
        self.external_provider = provider

    def validate_complete_dataset(
        self, data: pd.DataFrame, symbol: str, timeframe: str
    ) -> ValidationReport:
        """
        Comprehensive validation of entire dataset.

        Args:
            data: OHLCV DataFrame to validate
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            Complete validation report with all findings
        """
        start_time = pd.Timestamp.now()

        with self._lock:
            self.validation_count += 1
            logger.info(
                f"Starting comprehensive validation for {symbol} {timeframe} ({len(data)} bars)"
            )

        # Use existing DataQualityValidator for core validation
        validated_data, quality_report = self.data_quality_validator.validate_data(
            data, symbol, timeframe
        )

        errors: List[ValidationError] = []
        warnings: List[ValidationError] = []

        # Convert DataQualityIssues to ValidationErrors
        for issue in quality_report.issues:
            validation_error = ValidationError(
                error_type=issue.issue_type,
                message=issue.description,
                location=issue.location,
                severity=issue.severity,
                metadata=issue.metadata,
            )

            if issue.severity in ["critical", "high"]:
                errors.append(validation_error)
            else:
                warnings.append(validation_error)

        # Additional validation layers
        ohlc_errors = self.validate_ohlc_constraints(data)
        errors.extend(ohlc_errors)

        if self.config.validate_market_hours:
            market_errors = self.validate_market_hours(
                data, "NASDAQ"
            )  # Default exchange
            errors.extend(market_errors)

        price_errors = self.validate_price_continuity(data)
        errors.extend(price_errors)

        volume_errors = self.validate_volume_patterns(data)
        warnings.extend(volume_errors)  # Volume issues usually warnings

        # Calculate statistics
        validation_time = (pd.Timestamp.now() - start_time).total_seconds() * 1000
        statistics = ValidationStatistics(
            total_bars=len(data),
            issues_found=len(errors) + len(warnings),
            corrections_made=quality_report.corrections_made,
            validation_time_ms=validation_time,
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(errors, warnings, statistics)

        is_valid = len(errors) == 0

        report = ValidationReport(
            is_valid=is_valid,
            symbol=symbol,
            timeframe=timeframe,
            errors=errors,
            warnings=warnings,
            statistics=statistics,
            recommendations=recommendations,
            quality_report=quality_report,
        )

        logger.info(
            f"Validation complete: {len(errors)} errors, {len(warnings)} warnings, "
            f"{statistics.corrections_made} corrections, {validation_time:.1f}ms"
        )

        return report

    def validate_ohlc_constraints(self, data: pd.DataFrame) -> List[ValidationError]:
        """
        Validate OHLC mathematical constraints.

        Args:
            data: OHLCV DataFrame

        Returns:
            List of OHLC constraint violations
        """
        errors: List[ValidationError] = []

        if data.empty:
            return errors

        required_cols = ["open", "high", "low", "close"]
        if not all(col in data.columns for col in required_cols):
            errors.append(
                ValidationError(
                    error_type="missing_ohlc_columns",
                    message=f"Missing required OHLC columns",
                    severity="critical",
                )
            )
            return errors

        # OHLC mathematical constraints
        valid_rows = data[required_cols].notna().all(axis=1)

        if not valid_rows.any():
            return errors

        valid_data = data[valid_rows]

        # High must be >= max(open, close)
        max_oc = np.maximum(valid_data["open"], valid_data["close"])
        high_violations = valid_data["high"] < max_oc

        if high_violations.any():
            count = high_violations.sum()
            errors.append(
                ValidationError(
                    error_type="high_constraint_violation",
                    message=f"{count} bars where high < max(open, close)",
                    location="high vs open/close",
                    severity="high",
                    metadata={"count": count},
                )
            )

        # Low must be <= min(open, close)
        min_oc = np.minimum(valid_data["open"], valid_data["close"])
        low_violations = valid_data["low"] > min_oc

        if low_violations.any():
            count = low_violations.sum()
            errors.append(
                ValidationError(
                    error_type="low_constraint_violation",
                    message=f"{count} bars where low > min(open, close)",
                    location="low vs open/close",
                    severity="high",
                    metadata={"count": count},
                )
            )

        # High must be >= low
        high_low_violations = valid_data["high"] < valid_data["low"]

        if high_low_violations.any():
            count = high_low_violations.sum()
            errors.append(
                ValidationError(
                    error_type="high_low_constraint_violation",
                    message=f"{count} bars where high < low",
                    location="high vs low",
                    severity="critical",
                    metadata={"count": count},
                )
            )

        return errors

    def validate_market_hours(
        self, data: pd.DataFrame, exchange: str
    ) -> List[ValidationError]:
        """
        Verify data timestamps align with market hours.

        Args:
            data: OHLCV DataFrame
            exchange: Exchange name for market hours lookup

        Returns:
            List of market hours violations
        """
        errors: List[ValidationError] = []

        if data.empty or not isinstance(data.index, pd.DatetimeIndex):
            return errors

        if not self.config.weekend_data_allowed:
            # Check for weekend data
            weekend_data = data.index.weekday >= 5  # Saturday=5, Sunday=6

            if weekend_data.any():
                count = weekend_data.sum()
                errors.append(
                    ValidationError(
                        error_type="weekend_trading_data",
                        message=f"{count} bars found during weekends",
                        location="timestamp index",
                        severity="medium",
                        metadata={"count": count, "exchange": exchange},
                    )
                )

        # Note: More sophisticated market hours validation would require
        # trading hours data integration, which is beyond current scope

        return errors

    def validate_price_continuity(self, data: pd.DataFrame) -> List[ValidationError]:
        """
        Check for unrealistic price jumps or gaps.

        Args:
            data: OHLCV DataFrame

        Returns:
            List of price continuity issues
        """
        errors: List[ValidationError] = []

        if len(data) < 2 or "close" not in data.columns:
            return errors

        # Calculate price changes
        price_changes = data["close"].pct_change().abs()

        # Check for extreme price gaps
        extreme_threshold = self.config.max_price_gap_percent / 100.0
        extreme_gaps = price_changes > extreme_threshold

        if extreme_gaps.any():
            count = extreme_gaps.sum()
            max_gap = price_changes.max()

            errors.append(
                ValidationError(
                    error_type="extreme_price_gap",
                    message=f"{count} extreme price gaps > {self.config.max_price_gap_percent}% (max: {max_gap:.1%})",
                    location="price continuity",
                    severity="high" if max_gap > 0.5 else "medium",
                    metadata={
                        "count": count,
                        "max_gap_percent": max_gap * 100,
                        "threshold_percent": self.config.max_price_gap_percent,
                    },
                )
            )

        return errors

    def validate_volume_patterns(self, data: pd.DataFrame) -> List[ValidationError]:
        """
        Analyze volume data for anomalies.

        Args:
            data: OHLCV DataFrame

        Returns:
            List of volume pattern issues
        """
        errors: List[ValidationError] = []

        if "volume" not in data.columns or data.empty:
            return errors

        # Check for negative volumes (excluding IB's -1 indicator)
        negative_volume = data["volume"] < 0
        ib_no_data = data["volume"] == -1
        invalid_negative = negative_volume & ~ib_no_data

        if invalid_negative.any():
            count = invalid_negative.sum()
            errors.append(
                ValidationError(
                    error_type="invalid_negative_volume",
                    message=f"{count} bars with invalid negative volumes",
                    location="volume column",
                    severity="medium",
                    metadata={"count": count},
                )
            )

        # Check for volume below minimum threshold
        if self.config.min_volume_threshold > 0:
            low_volume = (data["volume"] >= 0) & (
                data["volume"] < self.config.min_volume_threshold
            )

            if low_volume.any():
                count = low_volume.sum()
                errors.append(
                    ValidationError(
                        error_type="low_volume_threshold",
                        message=f"{count} bars below minimum volume threshold ({self.config.min_volume_threshold})",
                        location="volume column",
                        severity="low",
                        metadata={
                            "count": count,
                            "threshold": self.config.min_volume_threshold,
                        },
                    )
                )

        # Check for consecutive zero volumes
        zero_volume = data["volume"] == 0
        if zero_volume.any():
            # Find consecutive zero runs
            zero_runs = (zero_volume != zero_volume.shift()).cumsum()
            zero_lengths = zero_volume.groupby(zero_runs).sum()
            max_consecutive = zero_lengths.max() if len(zero_lengths) > 0 else 0

            if max_consecutive > self.config.max_consecutive_zeros:
                errors.append(
                    ValidationError(
                        error_type="excessive_consecutive_zero_volume",
                        message=f"Found {max_consecutive} consecutive zero volume bars (max allowed: {self.config.max_consecutive_zeros})",
                        location="volume patterns",
                        severity="medium",
                        metadata={
                            "max_consecutive": max_consecutive,
                            "threshold": self.config.max_consecutive_zeros,
                        },
                    )
                )

        return errors

    def validate_data_integrity(self, df: pd.DataFrame) -> ValidationResult:
        """
        Validate data integrity - maintains DataManager compatibility.

        Args:
            df: DataFrame to validate

        Returns:
            ValidationResult compatible with existing DataProcessor interface
        """
        # Use DataProcessor-compatible validation via DataQualityValidator
        validated_df, quality_report = self.data_quality_validator.validate_data(
            df, "UNKNOWN", "UNKNOWN", "integrity_check"
        )

        # Convert to ValidationResult format for compatibility
        errors: List[str] = []
        warnings: List[str] = []

        for issue in quality_report.issues:
            if issue.severity in ["critical", "high"]:
                errors.append(issue.description)
            else:
                warnings.append(issue.description)

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            quality_report=quality_report,
        )

    def detect_gaps(
        self, df: pd.DataFrame, timeframe: str
    ) -> List[tuple[datetime, datetime]]:
        """
        Detect significant gaps in time series data.

        This method maintains compatibility with DataManager.detect_gaps()
        but uses intelligent gap classification.

        Args:
            df: DataFrame with DatetimeIndex
            timeframe: Data timeframe (e.g., '1h', '1d')

        Returns:
            List of (start_time, end_time) tuples for significant gaps
        """
        if df.empty or len(df) <= 1:
            return []

        # Use existing gap detection from DataQualityValidator
        _, quality_report = self.data_quality_validator.validate_data(
            df, "GAP_DETECTION", timeframe, "gap_check"
        )

        # Extract gaps from quality report
        gaps = []
        gap_issues = quality_report.get_issues_by_type("timestamp_gaps")

        for issue in gap_issues:
            if "gaps" in issue.metadata:
                # Parse gaps from metadata
                gap_data = issue.metadata["gaps"]
                for gap_start_str, gap_end_str in gap_data:
                    try:
                        gap_start = pd.Timestamp(gap_start_str).to_pydatetime()
                        gap_end = pd.Timestamp(gap_end_str).to_pydatetime()
                        gaps.append((gap_start, gap_end))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse gap timestamp: {e}")

        return gaps

    async def validate_request_range(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> RangeValidationResult:
        """
        Validate request date range against available data.

        This async method delegates to external provider for head timestamp lookup.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start_date: Requested start date
            end_date: Requested end date

        Returns:
            Range validation result with any necessary adjustments
        """
        if (
            not self.config.enable_head_timestamp_validation
            or not self.external_provider
        ):
            return RangeValidationResult(is_valid=True)

        try:
            # Get head timestamp from external provider (async operation)
            head_timestamp = await self.external_provider.get_head_timestamp(
                symbol, timeframe
            )

            if head_timestamp is None:
                return RangeValidationResult(is_valid=True)  # No constraint available

            # Check if start_date is before head timestamp
            if start_date < head_timestamp:
                error_message = f"Requested start date {start_date} is before earliest available data {head_timestamp}"
                logger.warning(f"📅 RANGE VALIDATION FAILED: {error_message}")
                return RangeValidationResult(
                    is_valid=False,
                    error_message=error_message,
                    adjusted_start_date=head_timestamp,
                )
            else:
                logger.debug(f"📅 RANGE VALIDATION PASSED: {symbol} from {start_date}")
                return RangeValidationResult(is_valid=True)

        except Exception as e:
            logger.warning(f"Range validation failed for {symbol}: {e}")
            # Don't block requests if validation fails
            return RangeValidationResult(is_valid=True)

    def validate_request_against_head_timestamp_sync(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[bool, Optional[str], Optional[datetime]]:
        """
        Validate request date range against cached head timestamp data (sync version).

        Extracted from DataManager._validate_request_against_head_timestamp().
        This method checks if the requested start date is within the available
        data range for the symbol, helping prevent unnecessary error 162s.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start_date: Requested start date
            end_date: Requested end date

        Returns:
            Tuple of (is_valid, error_message, adjusted_start_date)
        """
        if not self.external_provider:
            return True, None, None

        try:
            # Get head timestamp from external provider using async wrapper
            async def get_head_async():
                return await self.external_provider.get_head_timestamp(
                    symbol, timeframe
                )

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, get_head_async())
                        head_timestamp = future.result(timeout=30)
                else:
                    head_timestamp = loop.run_until_complete(get_head_async())
            except RuntimeError:
                head_timestamp = asyncio.run(get_head_async())

            if head_timestamp is None:
                return True, None, None  # No head timestamp available, assume valid

            # Check if start_date is before head timestamp
            if start_date < head_timestamp:
                error_message = f"Requested start date {start_date} is before earliest available data {head_timestamp}"
                logger.warning(f"📅 HEAD TIMESTAMP VALIDATION FAILED: {error_message}")
                return False, error_message, head_timestamp
            else:
                # Request is valid as-is
                logger.debug(
                    f"📅 HEAD TIMESTAMP VALIDATION PASSED: {symbol} from {start_date}"
                )
                return True, None, None

        except Exception as e:
            logger.warning(f"Head timestamp validation failed for {symbol}: {e}")
            # Don't block requests if validation fails
            return True, None, None

    def ensure_symbol_has_head_timestamp(self, symbol: str, timeframe: str) -> bool:
        """
        Ensure symbol has head timestamp data, triggering validation if needed.

        Extracted from DataManager._ensure_symbol_has_head_timestamp().

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            True if head timestamp is available, False otherwise
        """
        if not self.external_provider:
            return False

        try:
            # Check if we can get head timestamp from external provider
            async def check_head_async():
                head_timestamp = await self.external_provider.get_head_timestamp(
                    symbol, timeframe
                )
                return head_timestamp is not None

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, check_head_async())
                        return future.result(timeout=10)
                else:
                    return loop.run_until_complete(check_head_async())
            except RuntimeError:
                return asyncio.run(check_head_async())

        except Exception as e:
            logger.warning(
                f"Failed to check head timestamp availability for {symbol}: {e}"
            )
            return False

    def _generate_recommendations(
        self,
        errors: List[ValidationError],
        warnings: List[ValidationError],
        statistics: ValidationStatistics,
    ) -> List[str]:
        """Generate actionable recommendations based on validation results."""
        recommendations = []

        if len(errors) > 0:
            recommendations.append(
                "Critical data quality issues detected - manual review recommended"
            )

        if any(e.error_type == "extreme_price_gap" for e in errors):
            recommendations.append(
                "Check for stock splits, dividends, or data source issues"
            )

        if any(e.error_type.endswith("constraint_violation") for e in errors):
            recommendations.append(
                "Verify OHLC data integrity at source - mathematical constraints violated"
            )

        if len(warnings) > statistics.total_bars * 0.1:  # More than 10% warnings
            recommendations.append(
                "High warning rate suggests systematic data quality issues"
            )

        if statistics.corrections_made > 0:
            recommendations.append(
                f"Auto-corrections applied ({statistics.corrections_made}) - verify results"
            )

        return recommendations

    def get_validation_statistics(self) -> dict[str, Any]:
        """Get validator statistics."""
        base_stats = self.data_quality_validator.get_validation_statistics()

        return {
            **base_stats,
            "validator_validations": self.validation_count,
            "config": {
                "strict_ohlc": self.config.strict_ohlc,
                "max_price_gap_percent": self.config.max_price_gap_percent,
                "validate_market_hours": self.config.validate_market_hours,
                "auto_correct": self.config.auto_correct,
            },
        }

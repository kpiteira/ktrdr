"""Error recovery and resilience for multi-timeframe indicator processing.

This module provides robust error handling and recovery strategies for
multi-timeframe indicator pipelines.
"""

import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import numpy as np
import pandas as pd

from ktrdr import get_logger
from ktrdr.indicators.indicator_engine import IndicatorEngine
from ktrdr.indicators.multi_timeframe_indicator_engine import (
    MultiTimeframeIndicatorEngine,
)

logger = get_logger(__name__)


class RecoveryStrategy(Enum):
    """Strategies for error recovery."""

    FAIL_FAST = "fail_fast"  # Stop on first error
    SKIP_TIMEFRAME = "skip_timeframe"  # Skip failed timeframes
    SKIP_INDICATOR = "skip_indicator"  # Skip failed indicators
    USE_FALLBACK = "use_fallback"  # Use fallback values
    RETRY = "retry"  # Retry with different parameters
    PARTIAL_PROCESSING = "partial_processing"  # Process what we can


@dataclass
class ErrorContext:
    """Context information for an error."""

    timeframe: str
    indicator_type: Optional[str]
    error_type: str
    error_message: str
    timestamp: float
    data_info: dict[str, Any]
    recovery_attempted: bool = False
    recovery_successful: bool = False


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    successful: bool
    data: Optional[pd.DataFrame]
    error_context: ErrorContext
    recovery_action: str
    message: str


class ResilientProcessor:
    """Processor with error recovery capabilities."""

    def __init__(
        self,
        recovery_strategy: RecoveryStrategy = RecoveryStrategy.SKIP_INDICATOR,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        """
        Initialize resilient processor.

        Args:
            recovery_strategy: Strategy to use for error recovery
            max_retries: Maximum number of retries for recoverable errors
            retry_delay: Delay between retries in seconds
        """
        self.recovery_strategy = recovery_strategy
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.error_history: list[ErrorContext] = []
        self.logger = get_logger(__name__)

    def process_with_recovery(
        self, engine: MultiTimeframeIndicatorEngine, data: dict[str, pd.DataFrame]
    ) -> tuple[dict[str, pd.DataFrame], list[ErrorContext]]:
        """
        Process data with error recovery.

        Args:
            engine: MultiTimeframeIndicatorEngine
            data: Input data

        Returns:
            Tuple of (processed results, error contexts)
        """
        results = {}
        error_contexts = []

        self.logger.info(
            f"Processing {len(data)} timeframes with {self.recovery_strategy.value} recovery"
        )

        for timeframe, df in data.items():
            try:
                result = self._process_timeframe_with_recovery(engine, timeframe, df)

                if result.successful and result.data is not None:
                    results[timeframe] = result.data
                else:
                    error_contexts.append(result.error_context)

            except Exception as e:
                error_context = ErrorContext(
                    timeframe=timeframe,
                    indicator_type=None,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=time.time(),
                    data_info={"rows": len(df), "columns": list(df.columns)},
                )
                error_contexts.append(error_context)
                self.error_history.append(error_context)

                if self.recovery_strategy == RecoveryStrategy.FAIL_FAST:
                    raise
                else:
                    self.logger.error(f"Failed to process timeframe {timeframe}: {e}")

        return results, error_contexts

    def _process_timeframe_with_recovery(
        self, engine: MultiTimeframeIndicatorEngine, timeframe: str, data: pd.DataFrame
    ) -> RecoveryResult:
        """Process a single timeframe with recovery."""

        if timeframe not in engine.engines:
            error_context = ErrorContext(
                timeframe=timeframe,
                indicator_type=None,
                error_type="ConfigurationError",
                error_message=f"No engine configured for timeframe {timeframe}",
                timestamp=time.time(),
                data_info={"rows": len(data)},
            )

            return RecoveryResult(
                successful=False,
                data=None,
                error_context=error_context,
                recovery_action="none",
                message="No engine configuration available",
            )

        timeframe_engine = engine.engines[timeframe]

        # Try processing normally first
        for attempt in range(self.max_retries + 1):
            try:
                result = timeframe_engine.apply(data)

                # Apply column standardization
                standardized = engine._standardize_column_names(
                    result, timeframe, data.columns.tolist()
                )

                # Create a dummy context for successful processing
                success_context = ErrorContext(
                    timeframe=timeframe,
                    indicator_type=None,
                    error_type="",
                    error_message="",
                    timestamp=time.time(),
                    data_info={
                        "rows": len(standardized),
                        "columns": list(standardized.columns),
                    },
                )

                return RecoveryResult(
                    successful=True,
                    data=standardized,
                    error_context=success_context,
                    recovery_action="none",
                    message="Processed successfully",
                )

            except Exception as e:
                error_context = ErrorContext(
                    timeframe=timeframe,
                    indicator_type=None,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=time.time(),
                    data_info={"rows": len(data), "columns": list(data.columns)},
                    recovery_attempted=attempt > 0,
                )

                if attempt < self.max_retries:
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed for {timeframe}: {e}. Retrying..."
                    )
                    time.sleep(self.retry_delay)
                    continue
                else:
                    # All retries failed, try recovery
                    return self._attempt_recovery(
                        timeframe_engine, timeframe, data, error_context
                    )

        # Fallback return (should never reach here due to loop structure)
        error_context = ErrorContext(
            timeframe=timeframe,
            indicator_type=None,
            error_type="UnknownError",
            error_message="Unexpected code path reached",
            timestamp=time.time(),
            data_info={"rows": len(data)},
        )
        return RecoveryResult(
            successful=False,
            data=None,
            error_context=error_context,
            recovery_action="none",
            message="Unexpected error occurred",
        )

    def _attempt_recovery(
        self,
        engine: IndicatorEngine,
        timeframe: str,
        data: pd.DataFrame,
        error_context: ErrorContext,
    ) -> RecoveryResult:
        """Attempt recovery from error."""

        if self.recovery_strategy == RecoveryStrategy.SKIP_TIMEFRAME:
            return self._skip_timeframe_recovery(error_context)

        elif self.recovery_strategy == RecoveryStrategy.SKIP_INDICATOR:
            return self._skip_indicator_recovery(engine, timeframe, data, error_context)

        elif self.recovery_strategy == RecoveryStrategy.USE_FALLBACK:
            return self._fallback_recovery(timeframe, data, error_context)

        elif self.recovery_strategy == RecoveryStrategy.PARTIAL_PROCESSING:
            return self._partial_processing_recovery(
                engine, timeframe, data, error_context
            )

        else:
            return RecoveryResult(
                successful=False,
                data=None,
                error_context=error_context,
                recovery_action="none",
                message=f"No recovery strategy for {self.recovery_strategy.value}",
            )

    def _skip_timeframe_recovery(self, error_context: ErrorContext) -> RecoveryResult:
        """Skip the entire timeframe."""
        self.logger.info(f"Skipping timeframe {error_context.timeframe} due to error")

        error_context.recovery_attempted = True
        error_context.recovery_successful = False

        return RecoveryResult(
            successful=False,
            data=None,
            error_context=error_context,
            recovery_action="skip_timeframe",
            message=f"Skipped timeframe {error_context.timeframe}",
        )

    def _skip_indicator_recovery(
        self,
        engine: IndicatorEngine,
        timeframe: str,
        data: pd.DataFrame,
        error_context: ErrorContext,
    ) -> RecoveryResult:
        """Try processing with indicators removed one by one."""

        original_indicators = engine.indicators.copy()

        # Try removing indicators one by one
        for i, _indicator in enumerate(original_indicators):
            try:
                # Create new engine without this indicator
                remaining_indicators = [
                    ind for j, ind in enumerate(original_indicators) if j != i
                ]

                if not remaining_indicators:
                    # No indicators left
                    break

                # Create temporary engine
                temp_engine = IndicatorEngine(remaining_indicators)
                result = temp_engine.apply(data)

                self.logger.info(
                    f"Successfully processed {timeframe} after removing indicator {i}"
                )

                error_context.recovery_attempted = True
                error_context.recovery_successful = True

                return RecoveryResult(
                    successful=True,
                    data=result,
                    error_context=error_context,
                    recovery_action=f"removed_indicator_{i}",
                    message="Processed after removing problematic indicator",
                )

            except Exception:
                continue

        # If we get here, no single indicator removal worked
        return self._partial_processing_recovery(engine, timeframe, data, error_context)

    def _fallback_recovery(
        self, timeframe: str, data: pd.DataFrame, error_context: ErrorContext
    ) -> RecoveryResult:
        """Use fallback values."""

        # Create minimal result with original data plus dummy indicators
        fallback_data = data.copy()

        # Add some basic fallback indicators
        if len(data) > 0:
            # Simple moving average fallback
            if "close" in data.columns:
                fallback_data[f"SMA_fallback_{timeframe}"] = (
                    data["close"]
                    .rolling(window=min(10, len(data)), min_periods=1)
                    .mean()
                )

                # Simple momentum fallback
                fallback_data[f"momentum_fallback_{timeframe}"] = (
                    data["close"].pct_change().fillna(0)
                )

        error_context.recovery_attempted = True
        error_context.recovery_successful = True

        return RecoveryResult(
            successful=True,
            data=fallback_data,
            error_context=error_context,
            recovery_action="fallback_indicators",
            message=f"Used fallback indicators for {timeframe}",
        )

    def _partial_processing_recovery(
        self,
        engine: IndicatorEngine,
        timeframe: str,
        data: pd.DataFrame,
        error_context: ErrorContext,
    ) -> RecoveryResult:
        """Try to process indicators individually."""

        result_data = data.copy()
        successful_indicators = 0

        for i, indicator in enumerate(engine.indicators):
            try:
                # Try processing just this indicator
                temp_engine = IndicatorEngine([indicator])
                temp_result = temp_engine.apply(data)

                # Add the new columns to our result
                new_columns = set(temp_result.columns) - set(data.columns)
                for col in new_columns:
                    result_data[col] = temp_result[col]

                successful_indicators += 1

            except Exception as e:
                self.logger.warning(
                    f"Failed to process indicator {i} in {timeframe}: {e}"
                )
                continue

        if successful_indicators > 0:
            error_context.recovery_attempted = True
            error_context.recovery_successful = True

            return RecoveryResult(
                successful=True,
                data=result_data,
                error_context=error_context,
                recovery_action=f"partial_processing_{successful_indicators}_indicators",
                message=f"Processed {successful_indicators} indicators successfully",
            )
        else:
            # No indicators worked, fall back to fallback strategy
            return self._fallback_recovery(timeframe, data, error_context)


class DataQualityChecker:
    """Check data quality and suggest fixes."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def check_data_quality(self, data: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
        """
        Check data quality across timeframes.

        Args:
            data: Multi-timeframe data

        Returns:
            Dictionary of timeframe -> list of issues
        """
        issues = {}

        for timeframe, df in data.items():
            timeframe_issues = []

            # Check if DataFrame is empty
            if df.empty:
                timeframe_issues.append("DataFrame is empty")
                issues[timeframe] = timeframe_issues
                continue

            # Check for required columns
            required_columns = ["open", "high", "low", "close"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                timeframe_issues.append(f"Missing required columns: {missing_columns}")

            # Check for NaN values
            for col in required_columns:
                if col in df.columns:
                    nan_count = df[col].isna().sum()
                    if nan_count > 0:
                        nan_percentage = (nan_count / len(df)) * 100
                        timeframe_issues.append(
                            f"Column '{col}' has {nan_count} NaN values ({nan_percentage:.1f}%)"
                        )

            # Check for infinite values
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                inf_count = np.isinf(df[col]).sum()
                if inf_count > 0:
                    timeframe_issues.append(
                        f"Column '{col}' has {inf_count} infinite values"
                    )

            # Check for OHLC constraints
            if all(col in df.columns for col in ["open", "high", "low", "close"]):
                # High should be >= max(open, close)
                high_violations = (
                    df["high"] < np.maximum(df["open"], df["close"])
                ).sum()
                if high_violations > 0:
                    timeframe_issues.append(
                        f"{high_violations} rows violate high >= max(open, close)"
                    )

                # Low should be <= min(open, close)
                low_violations = (df["low"] > np.minimum(df["open"], df["close"])).sum()
                if low_violations > 0:
                    timeframe_issues.append(
                        f"{low_violations} rows violate low <= min(open, close)"
                    )

            # Check for suspicious price movements
            if "close" in df.columns:
                returns = df["close"].pct_change().abs()
                extreme_returns = (returns > 0.5).sum()  # >50% moves
                if extreme_returns > 0:
                    timeframe_issues.append(
                        f"{extreme_returns} extreme price movements (>50%)"
                    )

            # Check for duplicate timestamps
            if "timestamp" in df.columns:
                duplicates = df["timestamp"].duplicated().sum()
                if duplicates > 0:
                    timeframe_issues.append(f"{duplicates} duplicate timestamps")

            # Check data volume
            if len(df) < 10:
                timeframe_issues.append(f"Very small dataset ({len(df)} rows)")

            issues[timeframe] = timeframe_issues

        return issues

    def fix_data_quality_issues(
        self,
        data: dict[str, pd.DataFrame],
        fix_nan: bool = True,
        fix_inf: bool = True,
        fix_ohlc: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """
        Attempt to fix common data quality issues.

        Args:
            data: Input data
            fix_nan: Whether to fix NaN values
            fix_inf: Whether to fix infinite values
            fix_ohlc: Whether to fix OHLC constraint violations

        Returns:
            Fixed data
        """
        fixed_data = {}

        for timeframe, df in data.items():
            if df.empty:
                fixed_data[timeframe] = df
                continue

            fixed_df = df.copy()

            # Fix NaN values
            if fix_nan:
                for col in ["open", "high", "low", "close"]:
                    if col in fixed_df.columns:
                        # Forward fill, then backward fill
                        fixed_df[col] = fixed_df[col].ffill().bfill()

                        # If still NaN, use a default value
                        if fixed_df[col].isna().any():
                            default_value = 100.0  # Reasonable default price
                            fixed_df[col] = fixed_df[col].fillna(default_value)
                            self.logger.warning(
                                f"Used default value {default_value} for NaN in {timeframe}.{col}"
                            )

            # Fix infinite values
            if fix_inf:
                numeric_columns = fixed_df.select_dtypes(include=[np.number]).columns
                for col in numeric_columns:
                    inf_mask = np.isinf(fixed_df[col])
                    if inf_mask.any():
                        # Replace with median of non-infinite values
                        finite_values = fixed_df[col][~inf_mask]
                        if len(finite_values) > 0:
                            replacement = finite_values.median()
                        else:
                            replacement = 0.0

                        fixed_df.loc[inf_mask, col] = replacement
                        self.logger.warning(
                            f"Replaced {inf_mask.sum()} infinite values in {timeframe}.{col}"
                        )

            # Fix OHLC constraints
            if fix_ohlc and all(
                col in fixed_df.columns for col in ["open", "high", "low", "close"]
            ):
                # Ensure high >= max(open, close)
                max_oc = np.maximum(fixed_df["open"], fixed_df["close"])
                fixed_df["high"] = np.maximum(fixed_df["high"], max_oc)

                # Ensure low <= min(open, close)
                min_oc = np.minimum(fixed_df["open"], fixed_df["close"])
                fixed_df["low"] = np.minimum(fixed_df["low"], min_oc)

            fixed_data[timeframe] = fixed_df

        return fixed_data


@contextmanager
def error_recovery_context(
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.SKIP_INDICATOR,
    log_errors: bool = True,
):
    """Context manager for error recovery."""
    processor = ResilientProcessor(recovery_strategy)

    try:
        yield processor
    except Exception as e:
        if log_errors:
            logger.error(f"Error in recovery context: {e}")
            logger.error(traceback.format_exc())
        raise
    finally:
        # Log error summary
        if processor.error_history:
            logger.info(
                f"Processing completed with {len(processor.error_history)} errors"
            )


def create_resilient_engine(
    base_engine: MultiTimeframeIndicatorEngine,
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.SKIP_INDICATOR,
) -> tuple[ResilientProcessor, MultiTimeframeIndicatorEngine]:
    """
    Create a resilient processing setup.

    Args:
        base_engine: Base engine to wrap
        recovery_strategy: Recovery strategy to use

    Returns:
        Tuple of (resilient processor, base engine)
    """
    processor = ResilientProcessor(recovery_strategy)
    return processor, base_engine


def process_with_comprehensive_error_handling(
    engine: MultiTimeframeIndicatorEngine,
    data: dict[str, pd.DataFrame],
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.SKIP_INDICATOR,
    check_data_quality: bool = True,
    fix_data_issues: bool = True,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """
    Process data with comprehensive error handling and recovery.

    Args:
        engine: MultiTimeframeIndicatorEngine
        data: Input data
        recovery_strategy: Strategy for error recovery
        check_data_quality: Whether to check data quality
        fix_data_issues: Whether to attempt fixing data issues

    Returns:
        Tuple of (results, error report)
    """
    error_report: dict[str, Any] = {
        "data_quality_issues": {},
        "processing_errors": [],
        "recovery_actions": [],
        "success_rate": {},
        "warnings": [],
    }

    processed_data = data

    # Check data quality
    if check_data_quality:
        quality_checker = DataQualityChecker()
        quality_issues = quality_checker.check_data_quality(data)
        error_report["data_quality_issues"] = quality_issues

        # Fix data issues if requested
        if fix_data_issues:
            has_issues = any(issues for issues in quality_issues.values())
            if has_issues:
                logger.info("Attempting to fix data quality issues")
                processed_data = quality_checker.fix_data_quality_issues(data)
                error_report["warnings"].append(
                    "Data quality issues were automatically fixed"
                )

    # Process with recovery
    processor = ResilientProcessor(recovery_strategy)
    results, error_contexts = processor.process_with_recovery(engine, processed_data)

    # Compile error report
    error_report["processing_errors"] = [
        {
            "timeframe": ctx.timeframe,
            "indicator_type": ctx.indicator_type,
            "error_type": ctx.error_type,
            "error_message": ctx.error_message,
            "recovery_attempted": ctx.recovery_attempted,
            "recovery_successful": ctx.recovery_successful,
        }
        for ctx in error_contexts
    ]

    # Calculate success rates
    total_timeframes = len(data)
    successful_timeframes = len(results)
    error_report["success_rate"] = {
        "timeframes_processed": successful_timeframes,
        "total_timeframes": total_timeframes,
        "success_percentage": (
            (successful_timeframes / total_timeframes * 100)
            if total_timeframes > 0
            else 0
        ),
    }

    return results, error_report

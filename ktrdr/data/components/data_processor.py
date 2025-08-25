"""
DataProcessor component for handling data validation, cleaning, and transformation.

This component extracts data processing logic from DataManager to provide
a dedicated, reusable component for data processing operations.
"""

import threading
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

import pandas as pd

from ktrdr.data.data_quality_validator import DataQualityReport, DataQualityValidator
from ktrdr.errors import DataValidationError
from ktrdr.logging import get_logger
from ktrdr.utils.timezone_utils import TimestampManager

logger = get_logger(__name__)


@dataclass
class ProcessorConfig:
    """Configuration for DataProcessor component."""

    remove_duplicates: bool = True
    fill_gaps: bool = True
    validate_ohlc: bool = True
    max_gap_tolerance: timedelta = timedelta(hours=1)
    timezone_conversion: bool = True
    auto_correct: bool = True
    max_gap_percentage: float = 10.0
    strict_validation: bool = False


@dataclass
class ValidationResult:
    """Result of data integrity validation."""

    is_valid: bool
    errors: list[str]
    warnings: Optional[list[str]] = None
    quality_report: Optional[DataQualityReport] = None

    def __post_init__(self):
        """Initialize warnings list if None."""
        if self.warnings is None:
            self.warnings = []


class DataProcessor:
    """
    Data processor component for validation, cleaning, and transformation.

    This component handles all data processing operations that were previously
    scattered throughout DataManager, providing a focused, reusable interface
    for data processing tasks.
    """

    def __init__(self, config: ProcessorConfig):
        """
        Initialize DataProcessor with configuration.

        Args:
            config: Processing configuration options
        """
        self.config = config
        self.validators = self._init_validators()
        self._lock = threading.RLock()  # For thread safety

        logger.info(f"DataProcessor initialized with config: {config}")

    def _init_validators(self) -> dict:
        """Initialize validation components."""
        return {
            "quality_validator": DataQualityValidator(
                auto_correct=self.config.auto_correct,
                max_gap_percentage=self.config.max_gap_percentage,
            )
        }

    def process_raw_data(
        self, raw_data: pd.DataFrame, symbol: str, timeframe: str
    ) -> pd.DataFrame:
        """
        Main processing pipeline: validate -> clean -> transform.

        Args:
            raw_data: Raw OHLCV data to process
            symbol: Symbol being processed
            timeframe: Timeframe of the data

        Returns:
            Processed DataFrame ready for use

        Raises:
            DataValidationError: If validation fails in strict mode
        """
        with self._lock:
            logger.debug(
                f"Processing raw data for {symbol} {timeframe} ({len(raw_data)} rows)"
            )

            # Step 1: Validate data integrity
            validation_result = self.validate_data_integrity(raw_data)
            if not validation_result.is_valid and self.config.strict_validation:
                raise DataValidationError(
                    f"Data validation failed for {symbol} {timeframe}: {validation_result.errors}"
                )

            # Step 2: Clean data (remove duplicates, handle missing values)
            cleaned_data = self.clean_data(raw_data)

            # Step 3: Apply transformations (timezone conversion, symbol-specific processing)
            transformed_data = self.apply_transformations(cleaned_data, symbol)

            logger.debug(
                f"Processing complete: {len(raw_data)} -> {len(transformed_data)} rows"
            )
            return transformed_data

    def validate_data_integrity(self, data: pd.DataFrame) -> ValidationResult:
        """
        Check for gaps, duplicates, invalid values using existing DataQualityValidator.

        Args:
            data: DataFrame to validate

        Returns:
            ValidationResult with validation status and details
        """
        if data.empty:
            return ValidationResult(
                is_valid=False, errors=["Dataset is empty"], warnings=[]
            )

        # Use existing DataQualityValidator for comprehensive validation
        validator = self.validators["quality_validator"]

        # Extract symbol and timeframe from context (using defaults if not available)
        symbol = "UNKNOWN"
        timeframe = "UNKNOWN"

        try:
            _, quality_report = validator.validate_data(
                data, symbol, timeframe, validation_type="processor"
            )

            # Convert quality report to ValidationResult
            errors = []
            warnings = []

            for issue in quality_report.issues:
                if issue.severity in ("critical", "high"):
                    errors.append(f"{issue.issue_type}: {issue.description}")
                else:
                    warnings.append(f"{issue.issue_type}: {issue.description}")

            # Check for OHLC constraint violations specifically
            ohlc_issues = quality_report.get_issues_by_type("ohlc_invalid")
            if ohlc_issues:
                errors.append("OHLC constraint violation")

            # Also check for corrected issues that indicate OHLC problems
            if quality_report.corrections_made > 0:
                # Look for specific correction types in the report
                for issue in quality_report.issues:
                    if issue.corrected and (
                        "high" in issue.description
                        or "OHLC" in issue.description.upper()
                    ):
                        if "OHLC constraint violation" not in errors:
                            errors.append("OHLC constraint violation")

            is_valid = len(errors) == 0

            return ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                quality_report=quality_report,
            )

        except Exception as e:
            logger.error(f"Error during data integrity validation: {e}")
            return ValidationResult(
                is_valid=False, errors=[f"Validation error: {str(e)}"], warnings=[]
            )

    def clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Remove duplicates, handle missing values, fix data types.

        This method performs basic cleaning operations based on configuration,
        respecting the remove_duplicates setting.

        Args:
            data: DataFrame to clean

        Returns:
            Cleaned DataFrame
        """
        if data.empty:
            return data

        cleaned_data = data.copy()

        # Handle duplicate removal based on configuration
        if self.config.remove_duplicates and not cleaned_data.index.is_unique:
            original_len = len(cleaned_data)
            cleaned_data = cleaned_data[~cleaned_data.index.duplicated(keep="first")]
            if len(cleaned_data) < original_len:
                logger.debug(
                    f"Removed {original_len - len(cleaned_data)} duplicate rows"
                )

        # For other cleaning operations (missing values, data types),
        # use DataQualityValidator only for non-duplicate corrections if enabled
        if self.config.auto_correct:
            symbol = "UNKNOWN"
            timeframe = "UNKNOWN"

            try:
                # Create validator with auto-correct disabled for duplicates if we don't want them removed
                validator = self.validators["quality_validator"]

                # Use our cleaned data (with our duplicate decision already applied)
                validated_data, quality_report = validator.validate_data(
                    cleaned_data, symbol, timeframe, validation_type="cleaning"
                )

                # If config says to remove duplicates, we can use validator result
                # If config says not to remove duplicates, only use result if no duplicates were removed
                if self.config.remove_duplicates or len(validated_data) == len(
                    cleaned_data
                ):
                    cleaned_data = validated_data
                # Otherwise keep our version that respects the duplicate config

            except Exception as e:
                logger.error(f"Error during data cleaning validation: {e}")

        return cleaned_data

    def apply_transformations(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Apply symbol-specific transformations and calculations.

        This method applies transformations including timezone conversion
        and any symbol-specific processing logic.

        Args:
            data: DataFrame to transform
            symbol: Symbol for symbol-specific processing

        Returns:
            Transformed DataFrame
        """
        if data.empty:
            return data

        transformed_data = data.copy()

        # Apply timezone conversion if enabled
        if self.config.timezone_conversion:
            transformed_data = self._normalize_dataframe_timezone(transformed_data)

        # Apply symbol-specific transformations
        transformed_data = self._apply_symbol_specific_transformations(
            transformed_data, symbol
        )

        return transformed_data

    def _normalize_dataframe_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DataFrame index to UTC timezone-aware.

        This method is extracted from DataManager._normalize_dataframe_timezone()

        Args:
            df: DataFrame with datetime index

        Returns:
            DataFrame with UTC timezone-aware index
        """
        return TimestampManager.convert_dataframe_index(df)

    def _apply_symbol_specific_transformations(
        self, data: pd.DataFrame, symbol: str
    ) -> pd.DataFrame:
        """
        Apply any symbol-specific transformations.

        This method can be extended to include symbol-specific logic
        such as split adjustments, dividend adjustments, etc.

        Args:
            data: DataFrame to transform
            symbol: Symbol for context

        Returns:
            Transformed DataFrame
        """
        # Currently no symbol-specific transformations implemented
        # This is a placeholder for future enhancements
        return data

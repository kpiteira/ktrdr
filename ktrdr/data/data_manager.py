"""
DataManager for managing, validating, and processing OHLCV data.

This module extends the LocalDataLoader with more sophisticated data
management capabilities, integrity checks, and utilities for detecting
and handling gaps or missing values in time series data.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Union

import pandas as pd

# Import logging system
from ktrdr import (
    get_logger,
    log_entry_exit,
    log_performance,
)
from ktrdr.data.components.data_fetcher import DataFetcher
from ktrdr.data.components.data_quality_validator import DataQualityValidator
from ktrdr.data.components.progress_manager import ProgressManager
from ktrdr.data.data_manager_builder import (
    DataManagerBuilder,
    create_default_datamanager_builder,
)
from ktrdr.data.ib_data_adapter import IbDataAdapter
from ktrdr.errors import (
    DataCorruptionError,
    DataError,
    DataNotFoundError,
)
from ktrdr.managers import ServiceOrchestrator
from ktrdr.utils.timezone_utils import TimestampManager

# Get module logger
logger = get_logger(__name__)


@dataclass
# Legacy DataLoadingProgress and ProgressCallback classes removed
# Now using ProgressManager with ProgressState for clean progress tracking


class DataManager(ServiceOrchestrator):
    """
    Manages, validates, and processes OHLCV data.

    This class builds upon LocalDataLoader to provide higher-level data management
    capabilities, including data integrity checks, gap detection, and data repair.

    Attributes:
        data_loader: The underlying LocalDataLoader instance
        max_gap_percentage: Maximum allowed percentage of gaps in data
        default_repair_method: Default method for repairing missing values
    """

    # Mapping of repair methods to their functions
    REPAIR_METHODS = {
        "ffill": pd.DataFrame.ffill,
        "bfill": pd.DataFrame.bfill,
        "interpolate": pd.DataFrame.interpolate,
        "zero": lambda df: df.fillna(0),
        "mean": lambda df: df.fillna(df.mean()),
        "median": lambda df: df.fillna(df.median()),
        "drop": lambda df: df.dropna(),
    }

    def __init__(
        self,
        data_dir: Optional[str] = None,
        max_gap_percentage: float = 5.0,
        default_repair_method: str = "ffill",
        builder: Optional[DataManagerBuilder] = None,
    ):
        """
        Initialize the DataManager using builder pattern.

        Args:
            data_dir: Path to the directory containing data files.
            max_gap_percentage: Maximum allowed percentage of gaps in data (default: 5.0)
            default_repair_method: Default method for repairing missing values
            builder: Optional custom builder. If None, creates default builder.
                    IB integration is always enabled (container mode removed)

        Raises:
            DataError: If initialization parameters are invalid
        """
        # Use provided builder or create default one
        if builder is None:
            builder = (
                create_default_datamanager_builder()
                .with_data_directory(data_dir)
                .with_gap_settings(max_gap_percentage)
                .with_repair_method(default_repair_method)
            )

        # Build the configuration
        config = builder.build_configuration()

        # Initialize all components from the built configuration
        # Assert components are non-None after builder.build_configuration()
        assert config.data_loader is not None, "Builder must create data_loader"
        assert (
            config.external_provider is not None
        ), "Builder must create external_provider"
        assert config.data_validator is not None, "Builder must create data_validator"
        assert config.gap_classifier is not None, "Builder must create gap_classifier"
        assert config.gap_analyzer is not None, "Builder must create gap_analyzer"
        assert config.segment_manager is not None, "Builder must create segment_manager"
        assert config.data_processor is not None, "Builder must create data_processor"

        self.data_loader = config.data_loader
        self.external_provider = config.external_provider
        self.max_gap_percentage = config.max_gap_percentage
        self.default_repair_method = config.default_repair_method
        self.data_validator = config.data_validator
        self.gap_classifier = config.gap_classifier
        self.gap_analyzer = config.gap_analyzer
        self.segment_manager = config.segment_manager
        self.data_processor = config.data_processor

        # Initialize operational components (will be configured per operation)
        self._progress_manager: Optional[ProgressManager] = None
        self._data_fetcher: Optional[DataFetcher] = None

        # Initialize ServiceOrchestrator (always enabled - container mode removed)
        super().__init__()

        # Finalize configuration with components that need DataManager reference
        config = builder.finalize_configuration(self)
        assert (
            config.data_loading_orchestrator is not None
        ), "Builder must create data_loading_orchestrator"
        assert config.health_checker is not None, "Builder must create health_checker"

        self.data_loading_orchestrator = config.data_loading_orchestrator
        self.health_checker = config.health_checker

    # ServiceOrchestrator abstract method implementations
    def _initialize_adapter(self) -> IbDataAdapter:
        """Initialize IB data adapter based on environment variables."""
        import os

        env_enabled = os.getenv("USE_IB_HOST_SERVICE", "").lower()
        use_host_service = env_enabled in ("true", "1", "yes")
        host_service_url = os.getenv(
            "IB_HOST_SERVICE_URL", self._get_default_host_url()
        )

        return IbDataAdapter(
            use_host_service=use_host_service, host_service_url=host_service_url
        )

    def _get_service_name(self) -> str:
        """Get the service name for logging and configuration."""
        return "Data/IB"

    def _get_default_host_url(self) -> str:
        """Get the default host service URL."""
        return "http://localhost:8001"

    def _get_env_var_prefix(self) -> str:
        """Get environment variable prefix."""
        return "IB"

    def _check_cancellation(
        self,
        cancellation_token: Optional[Any],
        operation_description: str = "operation",
    ) -> bool:
        """
        Check if cancellation has been requested.

        Args:
            cancellation_token: Token to check for cancellation
            operation_description: Description of current operation for logging

        Returns:
            True if cancellation was requested, False otherwise

        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        if cancellation_token is None:
            return False

        # Check if token has cancellation method
        is_cancelled = False
        if hasattr(cancellation_token, "is_cancelled_requested"):
            is_cancelled = cancellation_token.is_cancelled_requested
        elif hasattr(cancellation_token, "is_set"):
            is_cancelled = cancellation_token.is_set()
        elif hasattr(cancellation_token, "cancelled"):
            is_cancelled = cancellation_token.cancelled()

        if is_cancelled:
            logger.info(f"🛑 Cancellation requested during {operation_description}")
            # Import here to avoid circular imports
            import asyncio

            raise asyncio.CancelledError(
                f"Operation cancelled during {operation_description}"
            )

        return False

    # Legacy _create_progress_wrapper method removed
    # Now using ProgressManager directly with ProgressState callbacks

    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=500, logger=logger)
    def load_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "local",
        validate: bool = True,
        repair: bool = False,
        repair_outliers: bool = True,
        strict: bool = False,
        cancellation_token: Optional[Any] = None,
        progress_callback: Optional[Callable] = None,
    ) -> pd.DataFrame:
        """
        Load data with optional validation and repair using unified validator.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            start_date: Optional start date for filtering data
            end_date: Optional end date for filtering data
            mode: Loading mode - 'local' (local only), 'tail' (recent gaps), 'backfill' (historical), 'full' (backfill + tail)
            validate: Whether to validate data integrity (default: True)
            repair: Whether to repair any detected issues (default: False)
            repair_outliers: Whether to repair detected outliers when repair=True (default: True)
            strict: If True, raises an exception for integrity issues instead of warning (default: False)
            cancellation_token: Optional cancellation token to check for early termination
            progress_callback: Optional callback for progress updates during loading

        Returns:
            DataFrame containing validated (and optionally repaired) OHLCV data

        Raises:
            DataNotFoundError: If the data file is not found
            DataCorruptionError: If data has integrity issues and strict=True
            DataError: For other data-related errors

        Note:
            This method uses the unified DataQualityValidator and enhanced IB integration.
            When mode is 'tail', 'backfill', or 'full', it uses intelligent gap analysis
            and IB fetching for missing data segments.
        """
        # Initialize clean ProgressManager (no legacy DataLoadingProgress)
        total_steps = 5 if mode == "local" else 10  # More steps for IB-enabled modes

        # Create enhanced context for better progress descriptions
        operation_context = {
            "symbol": symbol,
            "timeframe": timeframe,
            "mode": mode,
            "start_date": (
                start_date.isoformat()
                if start_date and hasattr(start_date, "isoformat")
                else str(start_date) if start_date else None
            ),
            "end_date": (
                end_date.isoformat()
                if end_date and hasattr(end_date, "isoformat")
                else str(end_date) if end_date else None
            ),
        }

        progress_manager = ProgressManager(progress_callback)
        progress_manager.start_operation(
            total_steps,
            f"load_data_{symbol}_{timeframe}",
            operation_context=operation_context,
        )

        # Set cancellation token if provided
        if cancellation_token:
            progress_manager.set_cancellation_token(cancellation_token)

        # Load data based on mode
        logger.info(f"Loading data for {symbol} ({timeframe}) - mode: {mode}")

        if mode == "local":
            # Local-only mode: use basic loader without IB integration
            progress_manager.update_progress_with_context(
                1,
                "Loading local data from cache",
                current_item_detail=f"Reading {symbol} {timeframe} from local storage",
            )

            df = self.data_loader.load(symbol, timeframe, start_date, end_date)
        else:
            # Enhanced modes: use intelligent gap analysis with IB integration
            df = self.data_loading_orchestrator.load_with_fallback(
                symbol,
                timeframe,
                start_date,
                end_date,
                mode,
                cancellation_token,
                progress_manager,  # Pass ProgressManager for clean integration
            )

        # Check if df is None (happens when fallback returns None)
        if df is None:
            raise DataNotFoundError(
                message=f"Data not found for {symbol} ({timeframe})",
                error_code="DATA-FileNotFound",
                details={"symbol": symbol, "timeframe": timeframe},
            )

        if validate:
            # Update progress for validation step with context
            progress_manager.update_progress_with_context(
                total_steps,
                "Validating data quality",
                current_item_detail=f"Checking {len(df)} data points for completeness and accuracy",
            )

            # Use the unified data quality validator
            validation_type = "local"  # Default to local validation type

            # Temporarily disable auto-correct if repair is not requested
            if not repair:
                # Create a non-correcting validator for validation-only mode
                validator = DataQualityValidator(
                    auto_correct=False, max_gap_percentage=self.max_gap_percentage
                )
            else:
                # Use the instance validator which has auto-correct enabled
                validator = self.data_validator

            # Perform validation
            df_validated, quality_report = validator.validate_data(
                df, symbol, timeframe, validation_type
            )

            # Handle repair_outliers parameter if repair is enabled but repair_outliers is False
            if repair and not repair_outliers:
                # For now, log that outlier repair was skipped (full implementation would
                # require enhanced DataQualityValidator to support selective correction types)
                logger.info(
                    "Outlier repair was skipped as requested (repair_outliers=False)"
                )
                # Note: Current unified validator doesn't support selective repair types yet

            # Check if there are critical issues and handle based on strict mode
            # In strict mode, no critical or high severity issues are allowed
            is_healthy = quality_report.is_healthy(
                max_critical=0, max_high=0 if strict else 5
            )

            if not is_healthy:
                issues_summary = quality_report.get_summary()
                issues_str = f"{issues_summary['total_issues']} issues found"

                if strict:
                    logger.error(
                        f"Data quality issues found and strict mode enabled: {issues_str}"
                    )
                    raise DataCorruptionError(
                        message=f"Data quality issues found: {issues_str}",
                        error_code="DATA-IntegrityIssue",
                        details={
                            "issues": issues_summary,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "quality_report": quality_report.get_summary(),
                        },
                    )
                else:
                    logger.warning(f"Data quality issues found: {issues_str}")

                    if repair:
                        # The validator already performed repairs, use the validated data
                        df = df_validated
                        logger.info(
                            f"Data automatically repaired by validator: {quality_report.corrections_made} corrections made"
                        )
                    else:
                        # Just log the issues without repairing
                        for issue in quality_report.issues:
                            logger.warning(
                                f"  - {issue.issue_type}: {issue.description}"
                            )
            else:
                if repair:
                    # Use the validated data even if no issues were found (could have minor corrections)
                    df = df_validated
                    if quality_report.corrections_made > 0:
                        logger.info(
                            f"Minor data corrections applied: {quality_report.corrections_made} corrections made"
                        )

        # Complete operation with final item count
        progress_manager.complete_operation()

        logger.debug(
            f"Successfully loaded and processed {len(df)} rows of data for {symbol} ({timeframe})"
        )
        return df

    @log_entry_exit(logger=logger, log_args=True)
    def load(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        days: Optional[int] = None,
        validate: bool = True,
        repair: bool = False,
    ) -> pd.DataFrame:
        """
        Load data with simpler parameter naming for backward compatibility.

        This is a wrapper around load_data with parameter names aligned with the UI expectations.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            interval: The timeframe of the data (e.g., '1h', '1d'), same as timeframe
            start_date: Optional start date for filtering data
            end_date: Optional end date for filtering data
            days: Optional number of days to load from end_date going backwards
            validate: Whether to validate data integrity (default: True)
            repair: Whether to repair any detected issues (default: False)

        Returns:
            DataFrame containing validated (and optionally repaired) OHLCV data
        """
        # Handle the days parameter to calculate start_date if provided
        if days is not None and end_date is None:
            # If end_date is not provided, use current UTC date
            end_date = TimestampManager.now_utc()

        if days is not None:
            # Calculate start_date based on days going backwards from end_date
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)
            if end_date is not None:
                start_date = end_date - timedelta(days=days)

        # Call the original load_data method with the processed parameters
        return self.load_data(
            symbol=symbol,
            timeframe=interval,  # interval is the same as timeframe
            start_date=start_date,
            end_date=end_date,
            validate=validate,
            repair=repair,
        )

    def _normalize_timezone(
        self, dt: Union[str, datetime, pd.Timestamp, None], default_tz: str = "UTC"
    ) -> Optional[pd.Timestamp]:
        """
        Normalize datetime to UTC timezone-aware timestamp.

        Note: Using TimestampManager for consistent timezone handling.

        Args:
            dt: Input datetime (string, datetime, or Timestamp)
            default_tz: Default timezone to assume for naive datetimes (deprecated, always UTC)

        Returns:
            UTC timezone-aware Timestamp or None
        """
        return TimestampManager.to_utc(dt)

    def _normalize_dataframe_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DataFrame index to UTC timezone-aware.

        Note: Using TimestampManager for consistent timezone handling.

        Args:
            df: DataFrame with datetime index

        Returns:
            DataFrame with UTC timezone-aware index
        """
        return TimestampManager.convert_dataframe_index(df)

    # Gap analysis methods have been extracted to GapAnalyzer component
    # See: ktrdr.data.components.gap_analyzer.GapAnalyzer

    def _ensure_data_fetcher(self) -> DataFetcher:
        """
        Ensure DataFetcher component is initialized for HTTP session persistence.

        Returns:
            DataFetcher component instance
        """
        if self._data_fetcher is None:
            self._data_fetcher = DataFetcher()
        return self._data_fetcher

    def _fetch_segments_with_component(
        self,
        symbol: str,
        timeframe: str,
        segments: list[tuple[datetime, datetime]],
        cancellation_token: Optional[Any] = None,
        progress_manager: Optional[ProgressManager] = None,
    ) -> tuple[list[pd.DataFrame], int, int]:
        """
        Enhanced async fetching using DataFetcher component.

        This method provides compatibility with the current synchronous DataManager
        while delegating to the enhanced DataFetcher component for optimal
        performance with connection pooling and advanced progress tracking.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            segments: List of (start, end) segments to fetch
            cancellation_token: Optional cancellation token
            progress_manager: Optional progress manager
        Returns:
            Tuple of (successful_dataframes, successful_count, failed_count)
        """
        # Internal save interval - not exposed externally
        INTERNAL_SAVE_INTERVAL = 0.5

        if not self.external_provider:
            logger.error("No external provider available for fetching")
            return [], 0, len(segments)

        # Ensure DataFetcher is initialized
        data_fetcher = self._ensure_data_fetcher()

        # Run the enhanced async DataFetcher method
        try:

            async def fetch_with_data_fetcher():
                """Async wrapper for DataFetcher with periodic save integration."""
                try:
                    # Check if external provider is available
                    if self.external_provider is None:
                        logger.error("No external provider available for data fetching")
                        return [], 0, 0

                    # Create periodic save callback for time-based saving during fetch
                    def periodic_save_callback(
                        successful_data_list: list[pd.DataFrame],
                    ) -> int:
                        """Callback for periodic progress saving during fetch."""
                        return self._save_periodic_progress(
                            successful_data_list,
                            symbol,
                            timeframe,
                            0,  # TODO: Track previous bars properly
                        )

                    # Use SegmentManager for resilient fetching with periodic save support
                    successful_data, successful_count, failed_count = (
                        await self.segment_manager.fetch_segments_with_resilience(
                            symbol=symbol,
                            timeframe=timeframe,
                            segments=segments,
                            external_provider=self.external_provider,
                            progress_manager=progress_manager,
                            cancellation_token=cancellation_token,
                            periodic_save_callback=(
                                periodic_save_callback
                                if INTERNAL_SAVE_INTERVAL > 0
                                else None
                            ),
                            periodic_save_minutes=INTERNAL_SAVE_INTERVAL,
                        )
                    )

                    return successful_data, successful_count, failed_count

                finally:
                    # Clean up DataFetcher resources after operation
                    await data_fetcher.cleanup()

            return asyncio.run(fetch_with_data_fetcher())

        except asyncio.CancelledError:
            # Re-raise cancellation errors properly
            logger.info("Data fetching cancelled")
            raise
        except Exception as e:
            logger.error(f"Enhanced data fetching failed: {e}")
            return [], 0, len(segments)

    # Segmentation methods have been extracted to SegmentManager component
    # See: ktrdr.data.components.segment_manager.SegmentManager

    def _save_periodic_progress(
        self,
        successful_data: list[pd.DataFrame],
        symbol: str,
        timeframe: str,
        previous_bars_saved: int,
    ) -> int:
        """
        Save accumulated data progress to CSV file.

        This merges the new data with any existing data and saves to CSV,
        allowing downloads to resume from where they left off.

        Args:
            successful_data: List of DataFrames with newly fetched data
            symbol: Trading symbol
            timeframe: Data timeframe
            previous_bars_saved: Number of bars saved in previous saves (for counting)

        Returns:
            Number of new bars saved in this operation
        """
        if not successful_data:
            return 0

        try:
            # Merge newly fetched segments into single DataFrame
            new_data = pd.concat(successful_data, ignore_index=False).sort_index()
            new_data = new_data[~new_data.index.duplicated(keep="first")]

            # Load existing data if it exists
            try:
                existing_data = self.data_loader.load(symbol, timeframe)
                if existing_data is not None and not existing_data.empty:
                    # Merge new data with existing data
                    combined_data = pd.concat(
                        [existing_data, new_data], ignore_index=False
                    )
                    combined_data = combined_data.sort_index()
                    combined_data = combined_data[
                        ~combined_data.index.duplicated(keep="last")
                    ]

                    # Count only truly new bars (not in existing data)
                    new_bars_count = len(
                        new_data[~new_data.index.isin(existing_data.index)]
                    )
                else:
                    combined_data = new_data
                    new_bars_count = len(new_data)
            except (DataNotFoundError, FileNotFoundError):
                # No existing data - this is all new
                combined_data = new_data
                new_bars_count = len(new_data)

            # Save the combined data
            self.data_loader.save(combined_data, symbol, timeframe)

            return new_bars_count

        except Exception as e:
            logger.error(f"Failed to save periodic progress: {e}")
            raise

    def _fetch_head_timestamp_sync(self, symbol: str, timeframe: str) -> Optional[str]:
        """
        Sync wrapper for async head timestamp fetching.

        Simplified async/sync handling for better maintainability.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            ISO formatted head timestamp string or None if failed
        """
        if not self.external_provider:
            return None

        async def fetch_head_timestamp_async():
            """Async head timestamp fetch function."""
            return await self.external_provider.get_head_timestamp(
                symbol=symbol, timeframe=timeframe
            )

        try:
            return asyncio.run(fetch_head_timestamp_async())
        except Exception as e:
            logger.error(f"Head timestamp fetch failed for {symbol}: {e}")
            return None

    @log_entry_exit(logger=logger, log_args=True)
    def _validate_request_against_head_timestamp(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[bool, Optional[str], Optional[datetime]]:
        """
        Validate request date range against cached head timestamp data.

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
            # Get head timestamp from external provider using simplified async handling
            async def get_head_async():
                return await self.external_provider.get_head_timestamp(
                    symbol, timeframe
                )

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

    def _ensure_symbol_has_head_timestamp(self, symbol: str, timeframe: str) -> bool:
        """
        Ensure symbol has head timestamp data, triggering validation if needed.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            True if head timestamp is available, False otherwise
        """
        if not self.external_provider:
            return False

        try:
            # Simplified check using existing method
            head_timestamp = self._fetch_head_timestamp_sync(symbol, timeframe)

            if head_timestamp:
                logger.info(
                    f"📅 Successfully obtained head timestamp for {symbol}: {head_timestamp}"
                )
                return True
            else:
                logger.warning(f"📅 Failed to fetch head timestamp for {symbol}")
                return False

        except Exception as e:
            logger.warning(f"Error ensuring head timestamp for {symbol}: {e}")
            return False

    @log_entry_exit(logger=logger)
    def detect_gaps(
        self, df: pd.DataFrame, timeframe: str, gap_threshold: int = 1
    ) -> list[tuple[datetime, datetime]]:
        """
        Detect significant gaps in time series data using intelligent gap classification.

        This method finds gaps that would be considered data quality issues
        (excludes weekends, holidays, and non-trading hours) using the GapAnalyzer component.

        Args:
            df: DataFrame containing OHLCV data
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            gap_threshold: Number of consecutive missing periods to consider as a gap (legacy parameter, maintained for compatibility)

        Returns:
            List of (start_time, end_time) tuples representing significant gaps only
        """
        return self.gap_analyzer.detect_gaps(df, timeframe, gap_threshold)

    @log_entry_exit(logger=logger, log_args=True)
    def repair_data(
        self,
        df: pd.DataFrame,
        timeframe: str,
        method: str = "auto",
        repair_outliers: bool = True,
        context_window: Optional[int] = None,
        std_threshold: float = 2.5,
    ) -> pd.DataFrame:
        """
        Repair data issues using the unified data quality validator.

        Args:
            df: DataFrame containing OHLCV data
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            method: Repair method (legacy parameter, now uses unified validator)
            repair_outliers: Whether to repair detected outliers (default: True)
            context_window: Optional window size for contextual outlier detection
            std_threshold: Number of standard deviations to consider as outlier

        Returns:
            Repaired DataFrame

        Note:
            This method now delegates to the unified DataQualityValidator for
            all repair operations. The 'method' parameter is maintained for
            backward compatibility but the validator uses its own repair logic.
        """
        if df.empty:
            logger.warning("Cannot repair empty DataFrame")
            return df

        # Validate method parameter for backward compatibility
        if method not in [
            "auto",
            "ffill",
            "bfill",
            "interpolate",
            "zero",
            "mean",
            "median",
            "drop",
        ]:
            raise DataError(
                message=f"Invalid repair method: {method}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "method",
                    "value": method,
                    "valid_options": [
                        "auto",
                        "ffill",
                        "bfill",
                        "interpolate",
                        "zero",
                        "mean",
                        "median",
                        "drop",
                    ],
                },
            )

        logger.info(
            f"Repairing data using unified validator (method={method} - delegated to validator)"
        )

        # Use the unified data quality validator for repairs
        df_repaired, quality_report = self.data_validator.validate_data(
            df, "REPAIR", timeframe, validation_type="local"
        )

        # Log summary of repairs made
        if quality_report.corrections_made > 0:
            logger.info(
                f"Repair completed: {quality_report.corrections_made} corrections made"
            )

            # Log details of issues that were corrected
            corrected_issues = [
                issue for issue in quality_report.issues if issue.corrected
            ]
            for issue in corrected_issues:
                logger.debug(f"  - Fixed {issue.issue_type}: {issue.description}")
        else:
            logger.info("No repairs needed - data is already in good condition")

        return df_repaired

    @log_entry_exit(logger=logger, log_args=True)
    def get_data_summary(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """
        Get a summary of available data for a symbol and timeframe.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')

        Returns:
            Dictionary containing data summary information

        Raises:
            DataNotFoundError: If the data file is not found
        """
        # Check if file exists
        date_range = self.data_loader.get_data_date_range(symbol, timeframe)
        if date_range is None:
            raise DataNotFoundError(
                message=f"Data not found for {symbol} ({timeframe})",
                error_code="DATA-FileNotFound",
                details={"symbol": symbol, "timeframe": timeframe},
            )

        start_date, end_date = date_range

        # Load the data
        df = self.data_loader.load(symbol, timeframe)

        # Calculate summary statistics
        summary = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "duration": end_date - start_date,
            "days": (end_date - start_date).days,
            "rows": len(df),
            "columns": list(df.columns),
            "missing_values": df.isnull().sum().to_dict(),
            "has_gaps": len(self.detect_gaps(df, timeframe)) > 0,
            "min_price": df["low"].min(),
            "max_price": df["high"].max(),
            "avg_price": df["close"].mean(),
            "total_volume": df["volume"].sum(),
        }

        logger.info(f"Generated data summary for {symbol} ({timeframe})")
        return summary

    async def health_check(self) -> dict[str, Any]:
        """
        Perform comprehensive health check on data manager and components.

        Uses the DataHealthChecker component to provide detailed health information
        about all data-related components and their status.

        Returns:
            Dictionary with health status of all components
        """
        # Get base health check from ServiceOrchestrator
        health_info = await super().health_check()

        # Use DataHealthChecker for comprehensive component health checking
        if self.health_checker:
            component_health = (
                await self.health_checker.perform_comprehensive_health_check()
            )
            health_info.update(component_health)
        else:
            logger.warning(
                "Health checker not initialized, skipping component health checks"
            )

        return health_info

    @log_entry_exit(logger=logger)
    def merge_data(
        self,
        symbol: str,
        timeframe: str,
        new_data: pd.DataFrame,
        save_result: bool = True,
        overwrite_conflicts: bool = False,
    ) -> pd.DataFrame:
        """
        Merge new data with existing data, handling overlaps intelligently.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            new_data: New data to merge
            save_result: Whether to save the merged result
            overwrite_conflicts: Whether to overwrite existing data in case of conflicts

        Returns:
            Merged DataFrame

        Raises:
            DataError: For data-related errors
        """
        # Load existing data
        try:
            existing_data = self.data_loader.load(symbol, timeframe)
        except DataNotFoundError:
            existing_data = None

        # Delegate the core merging logic to DataProcessor component
        merged_data = self.data_processor.merge_data(
            existing_data, new_data, overwrite_conflicts, validate_data=True
        )

        # Save if requested
        if save_result:
            self.data_loader.save(merged_data, symbol, timeframe)
            logger.info(f"Saved merged data with {len(merged_data)} rows")

        return merged_data

    @log_entry_exit(logger=logger, log_args=True)
    def resample_data(
        self,
        df: pd.DataFrame,
        target_timeframe: str,
        source_timeframe: Optional[str] = None,
        fill_gaps: bool = True,
        agg_functions: Optional[dict[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Resample data to a different timeframe.

        Args:
            df: DataFrame to resample
            target_timeframe: Target timeframe (e.g., '1h', '1d')
            source_timeframe: Source timeframe (optional, used for validation)
            fill_gaps: Whether to fill gaps in the resampled data
            agg_functions: Dictionary of aggregation functions by column
                         (default uses standard OHLCV aggregation)

        Returns:
            Resampled DataFrame

        Raises:
            DataError: For resampling-related errors
        """
        # Delegate to DataProcessor component with default repair method
        return self.data_processor.resample_data(
            df,
            target_timeframe,
            source_timeframe,
            fill_gaps,
            agg_functions,
            repair_method=self.default_repair_method,
        )

    @log_entry_exit(logger=logger)
    def filter_data_by_condition(
        self,
        df: pd.DataFrame,
        condition: Callable[[pd.DataFrame], pd.Series],
        inverse: bool = False,
    ) -> pd.DataFrame:
        """
        Filter data based on a custom condition function.

        Args:
            df: DataFrame to filter
            condition: Function that takes a DataFrame and returns a boolean Series
            inverse: If True, returns rows that don't match the condition

        Returns:
            Filtered DataFrame
        """
        return self.data_processor.filter_data_by_condition(df, condition, inverse)

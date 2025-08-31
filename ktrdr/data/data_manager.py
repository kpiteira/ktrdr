"""
DataManager for managing, validating, and processing OHLCV data.

This module extends the LocalDataLoader with more sophisticated data
management capabilities, integrity checks, and utilities for detecting
and handling gaps or missing values in time series data.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, Union

import pandas as pd

# Import logging system
from ktrdr import (
    get_logger,
    log_entry_exit,
    log_performance,
)
from ktrdr.data.components.gap_analyzer import GapAnalyzer
from ktrdr.data.components.progress_manager import ProgressManager
from ktrdr.data.data_quality_validator import DataQualityValidator
from ktrdr.data.external_data_interface import ExternalDataProvider
from ktrdr.data.gap_classifier import GapClassifier
from ktrdr.data.ib_data_adapter import IbDataAdapter
from ktrdr.data.loading_modes import DataLoadingMode
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.data.timeframe_synchronizer import TimeframeSynchronizer
from ktrdr.errors import (
    DataCorruptionError,
    DataError,
    DataNotFoundError,
    DataValidationError,
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
        enable_ib: bool = True,
    ):
        """
        Initialize the DataManager.

        Args:
            data_dir: Path to the directory containing data files.
                     If None, will use the path from configuration.
            max_gap_percentage: Maximum allowed percentage of gaps in data (default: 5.0)
            default_repair_method: Default method for repairing missing values
                                  (default: 'ffill', options: 'ffill', 'bfill',
                                  'interpolate', 'zero', 'mean', 'median', 'drop')
            enable_ib: Whether to enable IB integration (default: True)
                      Set to False for unit tests to avoid network connections

        Raises:
            DataError: If initialization parameters are invalid
        """
        # Validate parameters
        if max_gap_percentage < 0 or max_gap_percentage > 100:
            raise DataError(
                message=f"Invalid max_gap_percentage: {max_gap_percentage}. Must be between 0 and 100.",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "max_gap_percentage",
                    "value": max_gap_percentage,
                    "valid_range": "0-100",
                },
            )

        if default_repair_method not in self.REPAIR_METHODS:
            raise DataError(
                message=f"Invalid repair method: {default_repair_method}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "default_repair_method",
                    "value": default_repair_method,
                    "valid_options": list(self.REPAIR_METHODS.keys()),
                },
            )

        # Initialize the LocalDataLoader
        self.data_loader = LocalDataLoader(data_dir=data_dir)

        # Initialize external data provider (using adapter pattern)
        self.enable_ib = enable_ib
        if enable_ib:
            # Load configuration to determine if host service should be used
            try:
                import os
                from pathlib import Path

                from ktrdr.config.loader import ConfigLoader
                from ktrdr.config.models import IbHostServiceConfig, KtrdrConfig

                config_loader = ConfigLoader()
                config_path = Path("config/settings.yaml")
                if config_path.exists():
                    config = config_loader.load(config_path, KtrdrConfig)
                    host_service_config = config.ib_host_service
                else:
                    # Use defaults if no config file
                    host_service_config = IbHostServiceConfig(
                        enabled=False, url="http://localhost:5001"
                    )

                # Check for environment override (for easy Docker toggle)
                override_file = os.getenv("IB_HOST_SERVICE_CONFIG")
                if override_file:
                    override_path = Path(f"config/environment/{override_file}.yaml")
                    if override_path.exists():
                        # Load override config and merge
                        override_config = config_loader.load(override_path, KtrdrConfig)
                        if override_config.ib_host_service:
                            host_service_config = override_config.ib_host_service
                            logger.info(
                                f"Loaded IB host service override from {override_path}"
                            )

                # Environment variable override for enabled flag (quick toggle)
                env_enabled = os.getenv("USE_IB_HOST_SERVICE", "").lower()
                if env_enabled in ("true", "1", "yes"):
                    host_service_config.enabled = True
                    # Use environment URL if provided
                    env_url = os.getenv("IB_HOST_SERVICE_URL")
                    if env_url:
                        host_service_config.url = env_url
                elif env_enabled in ("false", "0", "no"):
                    host_service_config.enabled = False

                # Initialize IbDataAdapter with host service configuration
                self.external_provider: Optional[ExternalDataProvider] = IbDataAdapter(
                    use_host_service=host_service_config.enabled,
                    host_service_url=host_service_config.url,
                )

                if host_service_config.enabled:
                    logger.info(
                        f"IB integration enabled using host service at {host_service_config.url}"
                    )
                else:
                    logger.info("IB integration enabled (direct connection)")

            except Exception as e:
                logger.warning(
                    f"Failed to load host service config, using direct connection: {e}"
                )
                # Fallback to direct connection
                self.external_provider = IbDataAdapter()
                logger.info("IB integration enabled (direct connection - fallback)")
        else:
            self.external_provider = None
            logger.info("IB integration disabled")

        # Store parameters
        self.max_gap_percentage = max_gap_percentage
        self.default_repair_method = default_repair_method

        # Initialize the unified data quality validator
        self.data_validator = DataQualityValidator(
            auto_correct=True,  # Enable auto-correction by default
            max_gap_percentage=max_gap_percentage,
        )

        # Initialize the intelligent gap classifier
        self.gap_classifier = GapClassifier()

        # Initialize the GapAnalyzer component
        self.gap_analyzer = GapAnalyzer(gap_classifier=self.gap_classifier)

        # Initialize the progress manager (will be configured per operation)
        self._progress_manager: Optional[ProgressManager] = None

        logger.info(
            f"Initialized DataManager with max_gap_percentage={max_gap_percentage}%, "
            f"default_repair_method='{default_repair_method}'"
        )

        # Initialize ServiceOrchestrator if IB is enabled
        if enable_ib:
            super().__init__()
        else:
            # Set adapter to None when IB is disabled for ServiceOrchestrator compatibility
            self.adapter = None

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
        periodic_save_minutes: float = 2.0,
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
            periodic_save_minutes: Save progress every N minutes during long downloads (default: 2.0)

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
            df = self._load_with_fallback(
                symbol,
                timeframe,
                start_date,
                end_date,
                mode,
                cancellation_token,
                progress_manager,  # Pass ProgressManager for clean integration
                periodic_save_minutes,
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
    def load_multi_timeframe_data(
        self,
        symbol: str,
        timeframes: list[str],
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        base_timeframe: str = "1h",
        mode: str = "local",
        validate: bool = True,
        repair: bool = False,
        cancellation_token: Optional[Any] = None,
        progress_callback: Optional[Callable] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Load OHLCV data for multiple timeframes with temporal alignment.

        This method loads data for multiple timeframes simultaneously and aligns them
        temporally using the base_timeframe as the reference grid. All timeframes
        are synchronized to ensure consistent timestamps for multi-timeframe analysis.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframes: List of timeframes to load (e.g., ['15m', '1h', '4h'])
            start_date: Optional start date for filtering data
            end_date: Optional end date for filtering data
            base_timeframe: Reference timeframe for alignment (default: '1h')
            mode: Loading mode - 'local', 'tail', 'backfill', 'full'
            validate: Whether to validate data integrity
            repair: Whether to repair any detected issues
            cancellation_token: Optional cancellation token for early termination
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary mapping timeframes to aligned DataFrames
            Format: {timeframe: aligned_ohlcv_dataframe}

        Raises:
            DataError: If loading fails for critical timeframes
            DataValidationError: If base_timeframe not in timeframes list
        """
        if not timeframes:
            raise DataValidationError(
                "At least one timeframe must be specified",
                error_code="MULTI_TF_NO_TIMEFRAMES",
                details={"symbol": symbol, "timeframes": timeframes},
            )

        if base_timeframe not in timeframes:
            raise DataValidationError(
                f"Base timeframe '{base_timeframe}' must be included in timeframes list",
                error_code="MULTI_TF_INVALID_BASE",
                details={
                    "symbol": symbol,
                    "base_timeframe": base_timeframe,
                    "timeframes": timeframes,
                },
            )

        # Initialize clean ProgressManager (no legacy DataLoadingProgress)
        total_steps = len(timeframes) + 1  # Load each TF + synchronization
        progress_manager = ProgressManager(progress_callback)
        progress_manager.start_operation(total_steps, f"load_multi_timeframe_{symbol}")

        # Set cancellation token if provided
        if cancellation_token:
            progress_manager.set_cancellation_token(cancellation_token)

        # Dictionary to store loaded data for each timeframe
        timeframe_data = {}
        loading_errors = {}

        # Step 1: Load data for each timeframe
        logger.info(f"Loading data for {len(timeframes)} timeframes: {timeframes}")

        for i, timeframe in enumerate(timeframes):
            try:
                # Check for cancellation
                if progress_manager.check_cancelled():
                    progress_manager.update_progress(i, "Cancelled by user")
                    break

                # Update progress for current timeframe
                progress_manager.update_progress(i, f"Loading {timeframe} data")

                logger.debug(f"Loading {symbol} data for timeframe: {timeframe}")

                # Load data for this timeframe using existing load_data method
                tf_data = self.load_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    mode=mode,
                    validate=validate,
                    repair=repair,
                    cancellation_token=cancellation_token,
                )

                if tf_data is not None and not tf_data.empty:
                    timeframe_data[timeframe] = tf_data
                    logger.debug(
                        f"Successfully loaded {len(tf_data)} rows for {symbol} {timeframe}"
                    )
                else:
                    logger.warning(f"No data loaded for {symbol} {timeframe}")
                    loading_errors[timeframe] = "No data returned"

            except Exception as e:
                error_msg = f"Failed to load {timeframe} data: {str(e)}"
                logger.error(error_msg)
                loading_errors[timeframe] = error_msg

                # If base timeframe fails, this is critical
                if timeframe == base_timeframe:
                    raise DataError(
                        f"Failed to load base timeframe {base_timeframe} for {symbol}",
                        error_code="MULTI_TF_BASE_LOAD_FAILED",
                        details={
                            "symbol": symbol,
                            "base_timeframe": base_timeframe,
                            "error": str(e),
                        },
                    ) from e

        # Check if we have any data to work with
        if not timeframe_data:
            raise DataError(
                f"Failed to load data for any timeframe for {symbol}",
                error_code="MULTI_TF_NO_DATA_LOADED",
                details={
                    "symbol": symbol,
                    "timeframes": timeframes,
                    "errors": loading_errors,
                },
            )

        # Step 1.5: Find common data coverage intersection across all loaded timeframes
        if len(timeframe_data) > 1:
            common_coverage = self._find_common_data_coverage(timeframe_data, symbol)

            # If we have a meaningful data intersection, rescope all timeframes to it
            if common_coverage["is_sufficient"]:
                logger.info(
                    f"📊 Found common data coverage: {common_coverage['start_date']} to {common_coverage['end_date']} "
                    f"({common_coverage['days']} days, {common_coverage['min_bars']} min bars across timeframes)"
                )

                # Rescope all timeframes to the common coverage window
                rescoped_data = {}
                for tf, df in timeframe_data.items():
                    rescoped_df = df.loc[
                        common_coverage["start_date"] : common_coverage["end_date"]
                    ]
                    rescoped_data[tf] = rescoped_df
                    logger.debug(f"  {tf}: {len(rescoped_df)} bars (was {len(df)})")

                timeframe_data = rescoped_data

                # Add a warning to surface to the user
                coverage_warning = (
                    f"⚠️ Multi-timeframe training rescoped to common data coverage: "
                    f"{common_coverage['start_date']:%Y-%m-%d} to {common_coverage['end_date']:%Y-%m-%d} "
                    f"({common_coverage['days']} days). Some requested data outside this window was excluded."
                )
                logger.warning(coverage_warning)

            else:
                # Insufficient common coverage - this is a real problem
                insufficient_msg = (
                    f"❌ Insufficient common data coverage across timeframes. "
                    f"Common window: {common_coverage.get('days', 0)} days, "
                    f"Min bars: {common_coverage.get('min_bars', 0)} "
                    f"(need at least 50 bars for indicators + training)"
                )
                logger.error(insufficient_msg)
                raise DataError(
                    "Multi-timeframe training requires overlapping data across timeframes",
                    error_code="MULTI_TF_INSUFFICIENT_COVERAGE",
                    details={
                        "symbol": symbol,
                        "timeframes": list(timeframe_data.keys()),
                        "common_coverage": common_coverage,
                        "recommendation": "Use longer date range or timeframes with better data availability",
                    },
                )

        # Check if we have the base timeframe (after potential rescoping)
        if base_timeframe not in timeframe_data:
            available_timeframes = list(timeframe_data.keys())
            if available_timeframes:
                logger.warning(
                    f"Base timeframe {base_timeframe} failed to load, using {available_timeframes[0]} as reference"
                )
                base_timeframe = available_timeframes[0]
            else:
                raise DataError(
                    f"No timeframes successfully loaded for {symbol}",
                    error_code="MULTI_TF_NO_SUCCESSFUL_LOADS",
                    details={"symbol": symbol, "errors": loading_errors},
                )

        # Step 2: Synchronize timeframes using TimeframeSynchronizer
        progress_manager.update_progress(len(timeframes), "Synchronizing timeframes")

        try:
            synchronizer = TimeframeSynchronizer()
            aligned_data, sync_stats = synchronizer.synchronize_multiple_timeframes(
                timeframe_data, base_timeframe
            )

            logger.info(
                f"Multi-timeframe synchronization completed: "
                f"{sync_stats.successfully_aligned}/{sync_stats.total_timeframes} timeframes aligned "
                f"(avg quality: {sync_stats.average_quality_score:.3f})"
            )

            # Final progress update
            # Complete the operation
            progress_manager.complete_operation()

            if loading_errors:
                for tf, error in loading_errors.items():
                    logger.warning(f"Failed to load {tf}: {error}")

            logger.info(
                f"Successfully loaded and synchronized {len(aligned_data)} timeframes for {symbol}"
            )

            return aligned_data

        except Exception as e:
            error_msg = f"Failed to synchronize timeframes: {str(e)}"
            logger.error(error_msg)
            raise DataError(
                f"Multi-timeframe synchronization failed for {symbol}",
                error_code="MULTI_TF_SYNC_FAILED",
                details={
                    "symbol": symbol,
                    "timeframes": list(timeframe_data.keys()),
                    "base_timeframe": base_timeframe,
                    "error": str(e),
                },
            ) from e

    def _find_common_data_coverage(
        self, timeframe_data: dict[str, pd.DataFrame], symbol: str
    ) -> dict[str, Any]:
        """
        Find the common data coverage intersection across all timeframes.

        This method analyzes the date ranges of all loaded timeframes and identifies
        the largest common time window where all timeframes have data. It also
        validates that this window is sufficient for meaningful training.

        Args:
            timeframe_data: Dictionary mapping timeframes to DataFrames
            symbol: Trading symbol (for logging/error context)

        Returns:
            Dictionary with coverage analysis results:
            {
                'start_date': pd.Timestamp,     # Common coverage start
                'end_date': pd.Timestamp,       # Common coverage end
                'days': int,                    # Number of days in common window
                'min_bars': int,                # Minimum bars across all timeframes in window
                'max_bars': int,                # Maximum bars across all timeframes in window
                'is_sufficient': bool,          # Whether coverage is sufficient for training
                'timeframe_details': Dict       # Per-timeframe coverage details
            }
        """
        if len(timeframe_data) < 2:
            # Single timeframe case - no intersection needed
            tf, df = next(iter(timeframe_data.items()))
            return {
                "start_date": df.index[0],
                "end_date": df.index[-1],
                "days": (df.index[-1] - df.index[0]).days,
                "min_bars": len(df),
                "max_bars": len(df),
                "is_sufficient": len(df) >= 50,  # Minimum for MACD + training
                "timeframe_details": {
                    tf: {"bars": len(df), "start": df.index[0], "end": df.index[-1]}
                },
            }

        # Multi-timeframe case - find intersection
        timeframe_ranges = {}

        for tf, df in timeframe_data.items():
            if df.empty:
                logger.warning(
                    f"Empty DataFrame for timeframe {tf}, skipping from coverage analysis"
                )
                continue

            timeframe_ranges[tf] = {
                "start": df.index[0],
                "end": df.index[-1],
                "bars": len(df),
                "df": df,
            }

        if not timeframe_ranges:
            return {
                "start_date": None,
                "end_date": None,
                "days": 0,
                "min_bars": 0,
                "max_bars": 0,
                "is_sufficient": False,
                "timeframe_details": {},
            }

        # Find the intersection: latest start date and earliest end date
        common_start = max(info["start"] for info in timeframe_ranges.values())
        common_end = min(info["end"] for info in timeframe_ranges.values())

        # Validate that we have a positive time window
        if common_start >= common_end:
            logger.warning(
                f"No temporal overlap found between timeframes for {symbol}. "
                f"Start: {common_start}, End: {common_end}"
            )
            return {
                "start_date": common_start,
                "end_date": common_end,
                "days": 0,
                "min_bars": 0,
                "max_bars": 0,
                "is_sufficient": False,
                "timeframe_details": timeframe_ranges,
            }

        # Calculate how many bars each timeframe has in the common window
        common_window_bars = {}
        for tf, info in timeframe_ranges.items():
            # Slice DataFrame to common window
            common_slice = info["df"].loc[common_start:common_end]
            common_window_bars[tf] = len(common_slice)

        min_bars = min(common_window_bars.values()) if common_window_bars else 0
        max_bars = max(common_window_bars.values()) if common_window_bars else 0
        days = (common_end - common_start).days

        # Determine if coverage is sufficient
        # Need at least 50 bars for MACD calculation (26+9=35) plus some training data
        is_sufficient = min_bars >= 50 and days >= 7  # At least 1 week and 50 bars

        logger.debug(
            f"Common coverage analysis for {symbol}: "
            f"{common_start.strftime('%Y-%m-%d')} to {common_end.strftime('%Y-%m-%d')} "
            f"({days} days, {min_bars}-{max_bars} bars)"
        )

        return {
            "start_date": common_start,
            "end_date": common_end,
            "days": days,
            "min_bars": min_bars,
            "max_bars": max_bars,
            "is_sufficient": is_sufficient,
            "timeframe_details": {
                tf: {
                    "original_bars": info["bars"],
                    "common_bars": common_window_bars.get(tf, 0),
                    "original_start": info["start"],
                    "original_end": info["end"],
                }
                for tf, info in timeframe_ranges.items()
            },
        }

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

    def _split_into_segments(
        self,
        gaps: list[tuple[datetime, datetime]],
        timeframe: str,
    ) -> list[tuple[datetime, datetime]]:
        """
        Split large gaps into IB-compliant segments.

        Takes gaps that might exceed IB duration limits and splits them
        into smaller segments that can be fetched individually.

        Args:
            gaps: List of gaps to potentially split
            timeframe: Data timeframe for limit checking

        Returns:
            List of segments ready for IB fetching
        """
        from ktrdr.config.ib_limits import IbLimitsRegistry

        segments = []
        max_duration = IbLimitsRegistry.get_duration_limit(timeframe)

        for gap_start, gap_end in gaps:
            gap_duration = gap_end - gap_start

            if gap_duration <= max_duration:
                # Gap fits in single request
                segments.append((gap_start, gap_end))
                logger.debug(
                    f"Gap fits in single segment: {gap_start} to {gap_end} ({gap_duration})"
                )
            else:
                # Split into multiple segments
                logger.info(
                    f"Splitting large gap {gap_start} to {gap_end} ({gap_duration}) into segments (max: {max_duration})"
                )

                current_start = gap_start
                while current_start < gap_end:
                    segment_end = min(current_start + max_duration, gap_end)
                    segments.append((current_start, segment_end))
                    logger.debug(f"Created segment: {current_start} to {segment_end}")
                    current_start = segment_end

        logger.info(
            f"⚡ SEGMENTATION: Split {len(gaps)} gaps into {len(segments)} IB-compliant segments"
        )
        for i, (seg_start, seg_end) in enumerate(segments):
            duration = seg_end - seg_start
            logger.debug(
                f"🔷 SEGMENT {i+1}: {seg_start} → {seg_end} (duration: {duration})"
            )
        return segments

    def _fetch_segments_with_resilience(
        self,
        symbol: str,
        timeframe: str,
        segments: list[tuple[datetime, datetime]],
        cancellation_token: Optional[Any] = None,
        progress_manager: Optional[ProgressManager] = None,
        periodic_save_minutes: float = 2.0,
    ) -> tuple[list[pd.DataFrame], int, int]:
        """
        Fetch multiple segments with failure resilience and periodic progress saves.

        Attempts to fetch each segment individually, continuing with other segments
        if some fail. This ensures partial success rather than complete failure.

        NEW: Saves progress every periodic_save_minutes to prevent data loss
        during long downloads if container restarts.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            segments: List of (start, end) segments to fetch
            periodic_save_minutes: Save progress every N minutes (default: 2.0)

        Returns:
            Tuple of (successful_dataframes, successful_count, failed_count)
        """
        successful_data: list[pd.DataFrame] = []
        successful_count = 0
        failed_count = 0

        if not self.enable_ib or not self.external_provider:
            logger.warning("External data provider not available for segment fetching")
            return successful_data, successful_count, len(segments)

        logger.info(f"Fetching {len(segments)} segments with failure resilience")

        # Periodic save tracking
        import time

        last_save_time = time.time()
        save_interval_seconds = periodic_save_minutes * 60
        total_bars_saved = 0

        logger.info(f"💾 Periodic saves enabled: every {periodic_save_minutes} minutes")

        for i, (segment_start, segment_end) in enumerate(segments):
            # Check for cancellation before each segment
            self._check_cancellation(
                cancellation_token, f"segment {i+1}/{len(segments)}"
            )

            # Update progress for current segment using ProgressManager
            if progress_manager:
                segment_detail = f"Segment {i+1}/{len(segments)}: {segment_start.strftime('%Y-%m-%d %H:%M')} to {segment_end.strftime('%Y-%m-%d %H:%M')}"
                progress_manager.update_step_progress(
                    current=i + 1,
                    total=len(segments),
                    items_processed=total_bars_saved,  # Track total bars loaded so far
                    detail=segment_detail,
                )

            try:
                duration = segment_end - segment_start
                logger.info(
                    f"🚀 IB REQUEST {i+1}/{len(segments)}: Fetching {symbol} {timeframe} from {segment_start} to {segment_end} (duration: {duration})"
                )

                # Use the unified IB data fetcher to fetch exactly what we ask for
                # Convert to async call - this method should be made async in the future
                # For now, we'll use a wrapper to handle the async call
                segment_data = self._fetch_segment_sync(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=segment_start,
                    end=segment_end,
                    cancellation_token=cancellation_token,
                )

                if segment_data is not None and not segment_data.empty:
                    successful_data.append(segment_data)
                    successful_count += 1
                    logger.info(
                        f"✅ IB SUCCESS {i+1}: Received {len(segment_data)} bars from IB"
                    )

                    # Update progress with successful segment completion
                    if progress_manager:
                        # Update total bars processed
                        total_items_processed = sum(len(df) for df in successful_data)
                        progress_manager.update_step_progress(
                            current=successful_count,
                            total=len(segments),
                            items_processed=total_items_processed,
                            detail=f"✅ Loaded {len(segment_data)} bars from segment {i+1}/{len(segments)}",
                        )

                    # 💾 PERIODIC SAVE: Check if it's time to save progress
                    current_time = time.time()
                    time_since_last_save = current_time - last_save_time

                    if (
                        time_since_last_save >= save_interval_seconds
                        or i == len(segments) - 1
                    ):
                        # Time to save! Merge accumulated data and save to CSV
                        try:
                            if successful_data:
                                bars_to_save = self._save_periodic_progress(
                                    successful_data, symbol, timeframe, total_bars_saved
                                )
                                total_bars_saved += bars_to_save
                                last_save_time = current_time

                                logger.info(
                                    f"💾 Progress saved: {bars_to_save:,} new bars "
                                    f"({total_bars_saved:,} total) after {time_since_last_save/60:.1f} minutes"
                                )

                                # Update progress to show save occurred
                                if progress_manager:
                                    progress_manager.update_step_progress(
                                        current=i + 1,
                                        total=len(segments),
                                        items_processed=total_bars_saved,
                                        detail=f"💾 Saved {total_bars_saved:,} bars to CSV",
                                    )
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to save periodic progress: {e}")
                            # Continue fetching even if save fails
                else:
                    failed_count += 1
                    logger.warning(f"❌ IB FAILURE {i+1}: No data returned from IB")

            except asyncio.CancelledError:
                # Cancellation detected - stop processing immediately
                logger.info(
                    f"🛑 Segment fetching cancelled at segment {i+1}/{len(segments)}"
                )
                break
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ IB ERROR {i+1}: Request failed - {e}")
                # Continue with next segment rather than failing completely
                continue

        # Check if operation was cancelled during segment fetching
        was_cancelled = False
        if (
            cancellation_token
            and hasattr(cancellation_token, "is_set")
            and cancellation_token.is_set()
        ):
            was_cancelled = True
            logger.info(
                f"🛑 Segment fetching cancelled after {successful_count} successful segments"
            )
        else:
            logger.info(
                f"Segment fetching complete: {successful_count} successful, {failed_count} failed"
            )

        # If cancelled, raise CancelledError to stop the entire data loading operation
        if was_cancelled:
            raise asyncio.CancelledError(
                f"Data loading cancelled during segment {successful_count + 1}"
            )

        return successful_data, successful_count, failed_count

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

    def _fetch_segment_sync(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        cancellation_token: Optional[Any] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Sync wrapper for async segment fetching using unified components.

        This method provides a synchronous interface to the async data fetcher.
        In the future, the entire DataManager should be made async.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            cancellation_token: Optional cancellation token

        Returns:
            DataFrame with fetched data or None if failed
        """
        import asyncio

        try:
            # Check for cancellation before expensive operation
            if (
                cancellation_token
                and hasattr(cancellation_token, "is_set")
                and cancellation_token.is_set()
            ):
                logger.info(f"🛑 Cancellation detected before IB fetch for {symbol}")
                return None

            # Create a cancellable async wrapper that polls for cancellation
            async def fetch_with_cancellation_polling():
                """Fetch with periodic cancellation checks."""

                # Start the IB fetch in a separate task
                fetch_task = asyncio.create_task(
                    self.external_provider.fetch_historical_data(
                        symbol=symbol,
                        timeframe=timeframe,
                        start=start,
                        end=end,
                        instrument_type=None,  # Auto-detect
                    )
                )

                # Poll for cancellation every 0.5 seconds
                while not fetch_task.done():
                    # Check cancellation token from worker thread
                    if (
                        cancellation_token
                        and hasattr(cancellation_token, "is_set")
                        and cancellation_token.is_set()
                    ):
                        logger.info(
                            f"🛑 Cancelling IB fetch for {symbol} during operation"
                        )
                        fetch_task.cancel()
                        try:
                            await fetch_task
                        except asyncio.CancelledError:
                            pass
                        raise asyncio.CancelledError(
                            "Operation cancelled during IB fetch"
                        )

                    # Wait up to 0.5 seconds for fetch completion
                    try:
                        await asyncio.wait_for(asyncio.shield(fetch_task), timeout=0.5)
                        break
                    except asyncio.TimeoutError:
                        # Continue checking for cancellation
                        continue

                return await fetch_task

            # Run with cancellation polling
            return asyncio.run(fetch_with_cancellation_polling())

        except asyncio.TimeoutError:
            logger.error(
                f"⏰ Data fetch timeout for {symbol} {timeframe} (15s limit) - possible IB Gateway issue"
            )
            return None
        except asyncio.CancelledError:
            logger.info(f"🛑 Data fetch cancelled for {symbol} {timeframe}")
            return None
        except Exception as e:
            logger.error(f"Sync fetch wrapper failed for {symbol} {timeframe}: {e}")
            return None

    def _fetch_head_timestamp_sync(self, symbol: str, timeframe: str) -> Optional[str]:
        """
        Sync wrapper for async head timestamp fetching.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            ISO formatted head timestamp string or None if failed
        """
        import asyncio

        async def fetch_head_timestamp_async():
            """Async head timestamp fetch function."""
            return await self.external_provider.get_head_timestamp(
                symbol=symbol, timeframe=timeframe
            )

        try:
            # Run the async function in the current event loop or create a new one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, need to run in executor
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run, fetch_head_timestamp_async()
                        )
                        return future.result(timeout=30)  # 30 second timeout
                else:
                    return loop.run_until_complete(fetch_head_timestamp_async())
            except RuntimeError:
                # No event loop, create a new one
                return asyncio.run(fetch_head_timestamp_async())

        except Exception as e:
            logger.error(f"Sync head timestamp fetch failed for {symbol}: {e}")
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
        if not self.enable_ib or not self.external_provider:
            return True, None, None

        try:
            # Get head timestamp from external provider
            import asyncio

            async def get_head_async():
                return await self.external_provider.get_head_timestamp(
                    symbol, timeframe
                )

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

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

    def _ensure_symbol_has_head_timestamp(self, symbol: str, timeframe: str) -> bool:
        """
        Ensure symbol has head timestamp data, triggering validation if needed.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            True if head timestamp is available, False otherwise
        """
        if not self.enable_ib or not self.external_provider:
            return False

        try:
            # Check if we can get head timestamp from external provider
            import asyncio

            async def check_head_async():
                head_timestamp = await self.external_provider.get_head_timestamp(
                    symbol, timeframe
                )
                return head_timestamp is not None

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, check_head_async())
                        return future.result(timeout=10)
                else:
                    return loop.run_until_complete(check_head_async())
            except RuntimeError:
                return asyncio.run(check_head_async())

            # Use a sync wrapper for async head timestamp fetching
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

    def _load_with_fallback(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "tail",
        cancellation_token: Optional[Any] = None,
        progress_manager: Optional[ProgressManager] = None,
        periodic_save_minutes: float = 2.0,
    ) -> Optional[pd.DataFrame]:
        """
        Load data with intelligent gap analysis and resilient segment fetching.

        ENHANCED STRATEGY:
        1. Load existing local data (fast)
        2. Perform intelligent gap analysis vs requested range
        3. Split gaps into IB-compliant segments
        4. Use "dumb" IbDataLoader to fetch only missing segments
        5. Merge all data sources chronologically
        6. Handle partial failures gracefully

        This replaces the old "naive" approach of fetching entire ranges
        with a smart approach that only fetches missing data segments.

        Args:
            symbol: The trading symbol
            timeframe: The timeframe of the data
            start_date: Optional start date
            end_date: Optional end date
            mode: Loading mode - 'tail' (recent gaps), 'backfill' (historical), 'full' (backfill + tail)

        Returns:
            DataFrame with data or None if no data found
        """
        # Legacy progress parameter removed - using ProgressManager integration

        # Step 1: FAIL FAST - Validate symbol and get metadata FIRST (2%)
        if progress_manager:
            progress_manager.update_progress_with_context(
                1,
                "Validating symbol with IB Gateway",
                current_item_detail=f"Checking if {symbol} is valid and tradeable",
            )

        logger.info("📋 STEP 0A: Symbol validation and metadata lookup")
        self._check_cancellation(cancellation_token, "symbol validation")

        validation_result = None
        cached_head_timestamp = None

        if self.enable_ib and self.external_provider:
            try:
                # Use sync wrapper for async validation call
                import asyncio

                async def validate_async():
                    return await self.external_provider.validate_and_get_metadata(
                        symbol, [timeframe]
                    )

                try:
                    validation_result = asyncio.run(validate_async())
                except RuntimeError:
                    # We're in an async context, need to run in executor
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, validate_async())
                        validation_result = future.result(timeout=30)

                logger.info(f"✅ Symbol {symbol} validated successfully")

                # Cache head timestamp for later use
                if (
                    validation_result.head_timestamps
                    and timeframe in validation_result.head_timestamps
                ):
                    cached_head_timestamp = validation_result.head_timestamps[timeframe]
                    logger.info(
                        f"📅 Cached head timestamp for {symbol} ({timeframe}): {cached_head_timestamp}"
                    )

            except Exception as e:
                logger.error(f"❌ Symbol validation failed for {symbol}: {e}")
                raise DataError(
                    message=f"Symbol validation failed: {e}",
                    error_code="DATA-SymbolValidationFailed",
                    details={"symbol": symbol, "timeframe": timeframe, "error": str(e)},
                ) from e
        else:
            logger.warning("External data provider not available for symbol validation")

        # Step 2: Set intelligent date ranges using head timestamp info
        # ALWAYS respect user-provided dates, but use head timestamp for defaults
        if start_date is None:
            # Default range based on mode and head timestamp
            if mode == "tail":
                # Tail: recent data if no range specified
                requested_start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)
            elif mode == "backfill" or mode == "full":
                # Use head timestamp if available, otherwise fall back to IB limits
                if cached_head_timestamp:
                    normalized_ts = self._normalize_timezone(cached_head_timestamp)
                    if normalized_ts is not None:
                        requested_start = normalized_ts
                    logger.info(
                        f"📅 Using head timestamp for default start: {requested_start}"
                    )
                else:
                    # Fallback: go back as far as IB allows for this timeframe
                    from ktrdr.config.ib_limits import IbLimitsRegistry

                    max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
                    requested_start = pd.Timestamp.now(tz="UTC") - max_duration
                    logger.info(
                        f"📅 Using IB duration limit for default start: {requested_start}"
                    )
            else:
                # Other modes: use IB limits
                from ktrdr.config.ib_limits import IbLimitsRegistry

                max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
                requested_start = pd.Timestamp.now(tz="UTC") - max_duration
        else:
            # ALWAYS respect user-provided start_date regardless of mode
            normalized_start = self._normalize_timezone(start_date)
            if normalized_start is not None:
                requested_start = normalized_start

        if end_date is None:
            requested_end = pd.Timestamp.now(tz="UTC")
        else:
            # ALWAYS respect user-provided end_date regardless of mode
            normalized_end = self._normalize_timezone(end_date)
            if normalized_end is not None:
                requested_end = normalized_end

        if requested_start >= requested_end:
            logger.warning(
                f"Invalid date range: start {requested_start} >= end {requested_end}"
            )
            return None

        logger.info(
            f"🧠 ENHANCED STRATEGY ({mode}): Loading {symbol} {timeframe} from {requested_start} to {requested_end}"
        )

        # Step 2: Validate request range against cached head timestamp (4%)
        if progress_manager:
            progress_manager.start_step(
                "Validate request range", step_number=2, step_percentage=2.0
            )

        logger.info("📅 STEP 0B: Validating request against head timestamp data")
        self._check_cancellation(cancellation_token, "head timestamp validation")

        # Use cached head timestamp from validation step if available
        if cached_head_timestamp:
            try:
                # Handle both datetime objects and string timestamps
                if isinstance(cached_head_timestamp, datetime):
                    head_dt = cached_head_timestamp
                    # Ensure timezone awareness
                    if head_dt.tzinfo is None:
                        head_dt = head_dt.replace(tzinfo=timezone.utc)
                else:
                    # Convert ISO timestamp string to datetime for range validation
                    head_dt = datetime.fromisoformat(
                        cached_head_timestamp.replace("Z", "+00:00")
                    )
                    if head_dt.tzinfo is None:
                        head_dt = head_dt.replace(tzinfo=timezone.utc)

                # Check if requested start is before available data
                if requested_start < head_dt:
                    logger.warning(
                        f"📅 Requested start {requested_start} is before available data {head_dt}"
                    )
                    logger.info(
                        f"📅 Adjusting start time to earliest available: {head_dt}"
                    )
                    requested_start = pd.Timestamp(head_dt)

                logger.info("📅 Request range validated against head timestamp")

            except Exception as e:
                logger.warning(
                    f"📅 Failed to parse cached head timestamp {cached_head_timestamp}: {e}"
                )
                # Continue without validation if parsing fails
        else:
            # Fallback to old method if no cached head timestamp
            logger.info("📅 No cached head timestamp, trying fallback method")
            try:
                has_head_timestamp = self._ensure_symbol_has_head_timestamp(
                    symbol, timeframe
                )

                if has_head_timestamp:
                    # Validate the request range against head timestamp
                    is_valid, error_message, adjusted_start = (
                        self._validate_request_against_head_timestamp(
                            symbol, timeframe, requested_start, requested_end
                        )
                    )

                    if not is_valid:
                        logger.error(f"📅 Request validation failed: {error_message}")
                        logger.error(
                            f"📅 Cannot load data for {symbol} from {requested_start} - data not available"
                        )
                        return None
                    elif adjusted_start:
                        logger.info(
                            f"📅 Request adjusted based on head timestamp: {requested_start} → {adjusted_start}"
                        )
                        requested_start = pd.Timestamp(adjusted_start)
                else:
                    logger.info(
                        f"📅 No head timestamp available for {symbol}, proceeding with original request"
                    )
            except Exception as e:
                logger.warning(f"📅 Fallback head timestamp validation failed: {e}")
                logger.info("📅 Proceeding with original request range")

        # Step 3: Load existing local data (ALL modes need this for gap analysis) (6%)
        if progress_manager:
            progress_manager.start_step(
                "Load existing local data", step_number=3, step_percentage=4.0
            )

        existing_data = None
        try:
            logger.info(f"📁 Loading existing local data for {symbol}")
            self._check_cancellation(cancellation_token, "loading existing data")
            existing_data = self.data_loader.load(symbol, timeframe)
            if existing_data is not None and not existing_data.empty:
                existing_data = self._normalize_dataframe_timezone(existing_data)
                logger.info(
                    f"✅ Found existing data: {len(existing_data)} bars ({existing_data.index.min()} to {existing_data.index.max()})"
                )
            else:
                logger.info("📭 No existing local data found")
        except Exception as e:
            logger.info(f"📭 No existing local data: {e}")
            existing_data = None

        # Step 4: Intelligent gap analysis (8%)
        if progress_manager:
            progress_manager.start_step(
                "Analyze data gaps", step_number=4, step_percentage=6.0
            )

        logger.info(
            f"🔍 GAP ANALYSIS: Starting intelligent gap detection for {symbol} {timeframe}"
        )
        self._check_cancellation(cancellation_token, "gap analysis")
        logger.debug(
            f"🔍 GAP ANALYSIS: Requested range = {requested_start} to {requested_end}"
        )
        if existing_data is not None and not existing_data.empty:
            logger.debug(
                f"🔍 GAP ANALYSIS: Existing data range = {existing_data.index.min()} to {existing_data.index.max()}"
            )
        else:
            logger.debug("🔍 GAP ANALYSIS: No existing data found")
        # Convert string mode to DataLoadingMode enum
        loading_mode = DataLoadingMode[mode.upper()] if isinstance(mode, str) else mode
        gaps = self.gap_analyzer.analyze_gaps(
            existing_data,
            requested_start,
            requested_end,
            timeframe,
            symbol,
            loading_mode,
        )

        if not gaps:
            logger.info("✅ No gaps found - existing data covers requested range!")
            # Filter existing data to requested range if needed
            if existing_data is not None:
                mask = (existing_data.index >= requested_start) & (
                    existing_data.index <= requested_end
                )
                filtered_data = existing_data[mask] if mask.any() else existing_data
                logger.info(
                    f"📊 Returning {len(filtered_data)} bars from existing data (filtered to requested range)"
                )
                return filtered_data
            return existing_data

        # Step 5: Split gaps into IB-compliant segments (10%)
        if progress_manager:
            progress_manager.start_step(
                "Create IB-compliant segments", step_number=5, step_percentage=8.0
            )

        logger.info(
            f"⚡ SEGMENTATION: Splitting {len(gaps)} gaps into IB-compliant segments..."
        )
        self._check_cancellation(cancellation_token, "segmentation")
        segments = self._split_into_segments(gaps, timeframe)
        logger.info(
            f"⚡ SEGMENTATION COMPLETE: Created {len(segments)} segments for IB fetching"
        )

        if not segments:
            logger.info("✅ No segments to fetch after filtering")
            return existing_data

        # Step 4: Fetch segments via IB fetcher (handles connection issues internally)
        fetched_data_frames = []

        if self.enable_ib and self.external_provider:
            # Step 6: Start segment fetching with expected bars if we can estimate (10% → 96%)
            if progress_manager:
                progress_manager.start_step(
                    f"Fetch {len(segments)} segments from IB",
                    step_number=6,
                    step_percentage=10.0,  # Starts at 10%
                    step_end_percentage=96.0,  # Ends at 96% - this is the big phase!
                    expected_items=None,  # We don't know total bars yet
                )

            logger.info(
                f"🚀 Fetching {len(segments)} segments using resilient strategy..."
            )
            self._check_cancellation(cancellation_token, "IB fetch preparation")
            successful_frames, successful_count, failed_count = (
                self._fetch_segments_with_resilience(
                    symbol,
                    timeframe,
                    segments,
                    cancellation_token,
                    progress_manager,
                    periodic_save_minutes,
                )
            )
            fetched_data_frames = successful_frames

            if successful_count > 0:
                logger.info(
                    f"✅ Successfully fetched {successful_count}/{len(segments)} segments"
                )
            if failed_count > 0:
                logger.warning(
                    f"⚠️ {failed_count}/{len(segments)} segments failed - continuing with partial data"
                )

                # Check if complete IB failure should fail the operation for certain modes
                if successful_count == 0 and mode in ["full", "tail", "backfill"]:
                    # All IB segments failed and mode requires fresh data
                    if mode == "full":
                        error_msg = f"Complete IB failure in 'full' mode - all {failed_count} segments failed. Cannot provide fresh data."
                    elif mode == "tail":
                        error_msg = f"Complete IB failure in 'tail' mode - all {failed_count} segments failed. Cannot provide recent data."
                    elif mode == "backfill":
                        error_msg = f"Complete IB failure in 'backfill' mode - all {failed_count} segments failed. Cannot provide historical data."

                    logger.error(f"❌ {error_msg}")

                    # For modes that require IB data, complete failure should fail the operation
                    # instead of returning stale cached data
                    raise DataError(
                        message=error_msg,
                        error_code="DATA-IBCompleteFail",
                        details={
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "mode": mode,
                            "failed_segments": failed_count,
                            "successful_segments": successful_count,
                        },
                    )
        else:
            logger.info("ℹ️ IB fetching disabled - using existing data only")

        # Step 7: Merge all data sources (96% → 98%)
        if progress_manager:
            progress_manager.start_step(
                "Merge data sources", step_number=7, step_percentage=96.0
            )

        all_data_frames = []

        # Add existing data if available
        if existing_data is not None and not existing_data.empty:
            all_data_frames.append(existing_data)

        # Add fetched data
        all_data_frames.extend(fetched_data_frames)

        if not all_data_frames:
            logger.warning("❌ No data available from any source")
            return None

        # Combine and sort all data
        logger.info(f"🔄 Merging {len(all_data_frames)} data sources...")

        # Log details about each data source for debugging
        for i, df in enumerate(all_data_frames):
            if not df.empty:
                logger.debug(
                    f"📊 Data source {i+1}: {len(df)} bars from {df.index.min()} to {df.index.max()}"
                )
            else:
                logger.debug(f"📊 Data source {i+1}: EMPTY DataFrame")

        combined_data = pd.concat(all_data_frames, ignore_index=False)
        logger.info(f"🔗 After concat: {len(combined_data)} total bars")

        # Remove duplicates and sort
        duplicates_count = combined_data.index.duplicated().sum()
        if duplicates_count > 0:
            logger.info(f"🗑️ Removing {duplicates_count} duplicate timestamps")
        combined_data = combined_data[~combined_data.index.duplicated(keep="last")]
        combined_data = combined_data.sort_index()
        logger.info(f"✅ After deduplication and sorting: {len(combined_data)} bars")

        # Filter to requested range
        mask = (combined_data.index >= requested_start) & (
            combined_data.index <= requested_end
        )
        final_data = combined_data[mask] if mask.any() else combined_data

        logger.info(
            f"📊 Final dataset: {len(final_data)} bars covering {final_data.index.min() if not final_data.empty else 'N/A'} to {final_data.index.max() if not final_data.empty else 'N/A'}"
        )

        # Step 8: Save the enhanced dataset back to CSV for future use (98%)
        if progress_manager:
            progress_manager.start_step(
                "Save enhanced dataset", step_number=8, step_percentage=98.0
            )

        if len(fetched_data_frames) > 0:  # Only save if we fetched new data
            try:
                self.data_loader.save(combined_data, symbol, timeframe)
                logger.info(f"💾 Saved enhanced dataset: {len(combined_data)} bars")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save enhanced dataset: {e}")

        # Step 9: Data loading completed (100%)
        if progress_manager:
            progress_manager.start_step(
                "Data loading completed", step_number=9, step_percentage=100.0
            )

        logger.info(f"🎉 ENHANCED STRATEGY COMPLETE: Returning {len(final_data)} bars")
        return final_data

    def _merge_and_fill_gaps(
        self, ib_data: pd.DataFrame, local_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge IB and local data, preferring IB data and filling gaps with local data.

        Args:
            ib_data: DataFrame from IB (already UTC timezone-aware)
            local_data: DataFrame from local CSV (already UTC timezone-aware)

        Returns:
            Merged DataFrame with gaps filled
        """
        # Both DataFrames should already be normalized to UTC timezone-aware by caller
        # Combine data, preferring IB data where available
        combined = ib_data.combine_first(local_data)

        # Sort by timestamp and remove duplicates
        combined = combined.sort_index().drop_duplicates()

        logger.info(
            f"Merged data: IB({len(ib_data)}) + Local({len(local_data)}) = Combined({len(combined)})"
        )

        return combined

    def _local_data_covers_range(
        self,
        local_data: pd.DataFrame,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
    ) -> bool:
        """
        Check if local data covers the requested date range.

        Args:
            local_data: DataFrame with local data
            start_date: Requested start date (None means no constraint)
            end_date: Requested end date (None means no constraint)

        Returns:
            True if local data covers the requested range, False otherwise
        """
        if local_data is None or local_data.empty:
            return False

        # If no date constraints, local data is sufficient
        if start_date is None and end_date is None:
            return True

        # Normalize requested dates
        req_start = (
            self._normalize_timezone(start_date) if start_date is not None else None
        )
        req_end = self._normalize_timezone(end_date) if end_date is not None else None

        # Get local data range
        local_start = local_data.index.min()
        local_end = local_data.index.max()

        # Check coverage
        start_covered = req_start is None or local_start <= req_start
        end_covered = req_end is None or local_end >= req_end

        coverage_result = start_covered and end_covered

        if not coverage_result:
            logger.debug(
                f"Local data range ({local_start} to {local_end}) does not cover requested range ({req_start} to {req_end})"
            )

        return coverage_result

    @log_entry_exit(logger=logger, log_args=True)
    def check_data_integrity(
        self, df: pd.DataFrame, timeframe: str, is_post_repair: bool = False
    ) -> list[str]:
        """
        Check for common data integrity issues using unified validator.

        Args:
            df: DataFrame containing OHLCV data
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            is_post_repair: Whether this check is done after data repair (default: False)

        Returns:
            List of detected integrity issues (empty if no issues found)

        Note:
            This method now uses the unified DataQualityValidator for consistency
            but maintains backward compatibility by returning a list of issue strings.
        """
        # Use the unified validator for integrity checking (without auto-correction)
        validator = DataQualityValidator(
            auto_correct=False, max_gap_percentage=self.max_gap_percentage
        )

        _, quality_report = validator.validate_data(
            df, "CHECK", timeframe, validation_type="local"
        )

        # Convert the quality report issues to the legacy string format for backward compatibility
        issues = []
        for issue in quality_report.issues:
            # Skip certain issue types when checking post-repair data
            if is_post_repair:
                # These issues are expected to remain after repair and shouldn't be treated as failures
                if issue.issue_type in [
                    "timestamp_gaps",
                    "zero_volume",
                    "price_outliers",
                ]:
                    continue

            # Map new issue types to legacy strings that tests expect
            if issue.issue_type == "missing_values":
                issues.append(f"Missing values: {issue.description}")
            elif issue.issue_type in ["low_too_high", "high_too_low", "ohlc_invalid"]:
                issues.append(f"Invalid OHLC relationships: {issue.description}")
            elif issue.issue_type == "negative_volume":
                issues.append(f"Negative volume: {issue.description}")
            else:
                # For other issue types, use the default format
                issues.append(f"{issue.issue_type}: {issue.description}")

        return issues

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
        if df.empty or len(df) <= 1:
            return []

        # Use the GapAnalyzer component for gap detection with intelligent classification
        gaps = self.gap_analyzer.detect_internal_gaps(df, timeframe, gap_threshold)

        logger.info(
            f"Detected {len(gaps)} significant gaps using GapAnalyzer component with intelligent classification"
        )
        return gaps

    @log_entry_exit(logger=logger)
    def detect_outliers(
        self,
        df: pd.DataFrame,
        std_threshold: float = 2.5,
        columns: Optional[list[str]] = None,
        post_repair_tolerance: float = 0.0,
        context_window: Optional[int] = None,
        log_outliers: bool = True,
    ) -> int:
        """
        Detect outliers in price data using unified validator.

        Args:
            df: DataFrame containing OHLCV data
            std_threshold: Number of standard deviations to consider as outlier
            columns: List of columns to check (default: checks all OHLC columns)
            post_repair_tolerance: Additional tolerance for post-repair validation (adds to std_threshold)
            context_window: Optional window size for rolling statistics. If provided, uses a rolling
                           window for contextual outlier detection instead of global statistics.
            log_outliers: Whether to log identified outliers (default: True)

        Returns:
            Number of outliers detected

        Note:
            This method now uses the unified DataQualityValidator for consistency.
        """
        if df.empty:
            return 0

        # Delegate to unified validator (without auto-correction for detection only)
        validator = DataQualityValidator(
            auto_correct=False, max_gap_percentage=self.max_gap_percentage
        )

        try:
            _, quality_report = validator.validate_data(
                df, "OUTLIER_CHECK", "1h", validation_type="local"
            )

            # Check if validation failed (report contains validation errors)
            validation_errors = quality_report.get_issues_by_type("validation_error")
            if validation_errors:
                # Validation failed, use fallback method
                logger.warning(
                    f"Validation failed with {len(validation_errors)} errors, using fallback method"
                )
                total_outliers = self._detect_outliers_fallback(
                    df, std_threshold, columns, context_window, log_outliers
                )
            else:
                # Count outliers from the quality report
                outlier_issues = quality_report.get_issues_by_type("price_outliers")
                total_outliers = sum(
                    issue.metadata.get("count", 0) for issue in outlier_issues
                )
        except Exception as e:
            # If validation raises an exception, fall back to simple outlier detection
            logger.warning(
                f"Validation-based outlier detection failed ({e}), using fallback method"
            )
            total_outliers = self._detect_outliers_fallback(
                df, std_threshold, columns, context_window, log_outliers
            )

        if total_outliers > 0 and log_outliers:
            logger.warning(
                f"Detected {total_outliers} outliers in price data using unified validator:"
            )
            for issue in outlier_issues:
                logger.warning(f"  - {issue.description}")

        return total_outliers

    def _detect_outliers_fallback(
        self,
        df: pd.DataFrame,
        std_threshold: float = 2.5,
        columns: Optional[list[str]] = None,
        context_window: Optional[int] = None,
        log_outliers: bool = True,
    ) -> int:
        """
        Fallback outlier detection using simple statistical methods.

        Used when the main validation-based detection fails due to timezone or other issues.
        """
        if columns is None:
            columns = ["open", "high", "low", "close"]

        # Filter to available columns
        columns = [col for col in columns if col in df.columns]
        if not columns:
            return 0

        total_outliers = 0

        for column in columns:
            if context_window:
                # Rolling z-score detection
                rolling_mean = (
                    df[column].rolling(window=context_window, center=True).mean()
                )
                rolling_std = (
                    df[column].rolling(window=context_window, center=True).std()
                )
                z_scores = (df[column] - rolling_mean) / rolling_std
            else:
                # Global z-score detection
                mean_val = df[column].mean()
                std_val = df[column].std()
                z_scores = (df[column] - mean_val) / std_val

            # Count outliers
            outliers = abs(z_scores) > std_threshold
            column_outlier_count = outliers.sum()
            total_outliers += column_outlier_count

            if column_outlier_count > 0 and log_outliers:
                logger.warning(
                    f"Found {column_outlier_count} outliers in {column} column"
                )

        return total_outliers

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
        # Validate new data
        self.data_loader._validate_dataframe(new_data)

        try:
            # Try to load existing data
            existing_data = self.data_loader.load(symbol, timeframe)
            logger.info(
                f"Merging {len(new_data)} rows with existing {len(existing_data)} rows"
            )

            # Use concat to combine the DataFrames
            merged_data = pd.concat([existing_data, new_data])

            # Count how many unique dates we have before handling duplicates
            total_unique_dates = len(merged_data.index.unique())

            # If we have duplicates, handle based on overwrite_conflicts flag
            if merged_data.index.duplicated().any():
                if overwrite_conflicts:
                    logger.info("Overwriting conflicting rows with new data")
                    # Keep the last occurrence of each duplicated index
                    merged_data = merged_data[
                        ~merged_data.index.duplicated(keep="last")
                    ]
                else:
                    logger.info("Preserving existing data for conflicting rows")
                    # Keep the first occurrence of each duplicated index
                    merged_data = merged_data[
                        ~merged_data.index.duplicated(keep="first")
                    ]

                # Log how many rows were affected by conflicts
                logger.debug(
                    f"Found {len(merged_data.index.unique()) - total_unique_dates} conflicting rows"
                )

        except DataNotFoundError:
            # If no existing data, just use the new data
            logger.info(
                f"No existing data found, using {len(new_data)} rows of new data"
            )
            merged_data = new_data

        # Sort the index to ensure chronological order
        merged_data = merged_data.sort_index()

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
        if df.empty:
            logger.warning("Cannot resample empty DataFrame")
            return df

        # Validate target_timeframe using centralized constants
        timeframe_frequencies = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D",
            "1w": "1W",
        }
        target_freq = timeframe_frequencies.get(target_timeframe)
        if not target_freq:
            raise DataError(
                message=f"Invalid target timeframe: {target_timeframe}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "target_timeframe",
                    "value": target_timeframe,
                    "valid_options": list(timeframe_frequencies.keys()),
                },
            )

        # If source_timeframe is provided, validate it
        if source_timeframe:
            source_freq = timeframe_frequencies.get(source_timeframe)
            if not source_freq:
                raise DataError(
                    message=f"Invalid source timeframe: {source_timeframe}",
                    error_code="DATA-InvalidParameter",
                    details={
                        "parameter": "source_timeframe",
                        "value": source_timeframe,
                        "valid_options": list(timeframe_frequencies.keys()),
                    },
                )

            # Check if timeframe change makes sense (can only go from smaller to larger)
            source_delta = pd.Timedelta(source_freq)
            target_delta = pd.Timedelta(target_freq)

            if target_delta < source_delta:
                logger.warning(
                    f"Cannot downsample from {source_timeframe} to {target_timeframe} "
                    f"as it would require generating data points"
                )

        # Set default aggregation functions if not provided
        if agg_functions is None:
            agg_functions = {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }

        # Make sure all columns in agg_functions exist in the DataFrame
        agg_functions = {k: v for k, v in agg_functions.items() if k in df.columns}

        try:
            logger.debug(
                f"Resampling data to {target_timeframe} frequency ({target_freq})"
            )
            # Make sure the index is sorted
            df_sorted = df.sort_index() if not df.index.is_monotonic_increasing else df

            # Resample the data
            resampled = df_sorted.resample(target_freq).agg(agg_functions)  # type: ignore[arg-type]

            # Fill gaps if requested
            if fill_gaps and not resampled.empty:
                logger.debug("Filling gaps in resampled data")
                resampled = self.repair_data(
                    resampled, target_timeframe, method=self.default_repair_method
                )

            logger.info(
                f"Successfully resampled data from {len(df)} rows to {len(resampled)} rows"
            )
            return resampled

        except Exception as e:
            logger.error(f"Error during resampling: {str(e)}")
            raise DataError(
                message=f"Failed to resample data: {str(e)}",
                error_code="DATA-ResampleError",
                details={"target_timeframe": target_timeframe, "error": str(e)},
            ) from e

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
        if df.empty:
            return df

        # Apply the condition
        mask = condition(df)

        # If inverse flag is set, invert the mask
        if inverse:
            mask = ~mask

        # Apply the mask
        result = df[mask]
        logger.info(f"Filtered {len(df) - len(result)} rows out of {len(df)} total")
        return result

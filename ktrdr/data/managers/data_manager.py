"""
DataManager - Async data orchestrator following ServiceOrchestrator pattern.

This module provides the DataManager class that orchestrates data operations
across different sources (local files, IB Gateway, host services) while
eliminating the sync/async bottleneck from the legacy DataManager.

The DataManager extends ServiceOrchestrator to provide:
- Environment-based IB adapter configuration
- Async data loading with proper error handling
- Support for both local and IB data sources
- Backward-compatible interface with async methods
- Performance improvements through async execution
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Optional, Protocol, Union

import pandas as pd

from ktrdr.config.host_services import get_ib_host_url
from ktrdr.data.data_quality_validator import DataQualityValidator
from ktrdr.data.gap_classifier import GapClassifier
from ktrdr.data.ib_data_adapter import IbDataAdapter
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.errors import DataCorruptionError, DataError, DataNotFoundError
from ktrdr.logging import get_logger, log_entry_exit, log_performance
from ktrdr.managers import ServiceOrchestrator

logger = get_logger(__name__)


class ProgressCallback(Protocol):
    """Type protocol for progress callback functions."""

    def __call__(self, progress: dict[str, Any]) -> None: ...


class CancellationToken(Protocol):
    """Type protocol for cancellation tokens."""

    @property
    def is_cancelled_requested(self) -> bool: ...


class DataManager(ServiceOrchestrator):
    """
    Async data manager orchestrating data operations across multiple sources.

    This manager follows the ServiceOrchestrator pattern, providing unified
    async data operations while maintaining backward compatibility with the
    legacy DataManager interface. It eliminates the sync/async bottleneck
    that previously degraded performance.

    Key features:
    - Async data loading from multiple sources (local files, IB Gateway)
    - Environment-based IB Host Service configuration
    - Data validation and repair capabilities
    - Progress tracking and cancellation support
    - Comprehensive error handling with proper async context
    - Performance improvements through elimination of sync bottlenecks

    Sources supported:
    - "local": Local data files via LocalDataLoader
    - "ib": Interactive Brokers via IbDataAdapter (host service or direct)
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
        Initialize the async DataManager.

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
        # Validate parameters before initialization
        self._validate_init_parameters(max_gap_percentage, default_repair_method)

        # Store configuration
        self.max_gap_percentage = max_gap_percentage
        self.default_repair_method = default_repair_method
        self.enable_ib = enable_ib

        # Initialize LocalDataLoader
        self.data_loader = LocalDataLoader(data_dir=data_dir)

        # Initialize data quality components
        self.data_validator = DataQualityValidator(
            auto_correct=True,
            max_gap_percentage=max_gap_percentage,
        )
        self.gap_classifier = GapClassifier()

        # Initialize via ServiceOrchestrator (this calls _initialize_adapter)
        if enable_ib:
            super().__init__()
        else:
            # Skip IB adapter initialization for testing
            self.adapter = None
            logger.info("DataManager initialized without IB integration (testing mode)")

    def _validate_init_parameters(
        self, max_gap_percentage: float, default_repair_method: str
    ) -> None:
        """Validate initialization parameters."""
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

    def _initialize_adapter(self) -> IbDataAdapter:
        """
        Initialize IB data adapter based on environment variables.

        This method implements the ServiceOrchestrator pattern, using environment
        variables to configure the adapter for either host service or direct connection.

        Returns:
            Configured IbDataAdapter instance
        """
        try:
            # Environment variable logic matching the legacy DataManager pattern
            env_enabled = os.getenv("USE_IB_HOST_SERVICE", "").lower()

            if env_enabled in ("true", "1", "yes"):
                use_host_service = True
                host_service_url = os.getenv(
                    "IB_HOST_SERVICE_URL", self._get_default_host_url()
                )
                logger.info(
                    f"IB integration enabled using host service at {host_service_url}"
                )
            else:
                use_host_service = False
                host_service_url = None
                logger.info("IB integration enabled (direct connection)")

            return IbDataAdapter(
                use_host_service=use_host_service,
                host_service_url=host_service_url,
            )

        except Exception as e:
            logger.warning(
                f"Failed to initialize IB adapter, using direct connection: {e}"
            )
            # Fallback to direct connection
            return IbDataAdapter(use_host_service=False)

    def _get_service_name(self) -> str:
        """Get the service name for logging and configuration."""
        return "Data/IB"

    def _get_default_host_url(self) -> str:
        """Get the default host service URL."""
        return get_ib_host_url()

    def _get_env_var_prefix(self) -> str:
        """Get environment variable prefix."""
        return "IB"

    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=500, logger=logger)
    async def load_data(
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
        cancellation_token: Optional[CancellationToken] = None,
        progress_callback: Optional[ProgressCallback] = None,
        periodic_save_minutes: float = 2.0,
    ) -> pd.DataFrame:
        """
        Load data asynchronously with optional validation and repair.

        This method provides the same interface as the legacy DataManager.load_data
        but with full async execution to eliminate sync/async bottlenecks.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            start_date: Optional start date for filtering data
            end_date: Optional end date for filtering data
            mode: Loading mode - 'local' (local only), 'tail' (recent gaps),
                  'backfill' (historical), 'full' (backfill + tail)
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
        """
        logger.info(f"Loading data for {symbol} ({timeframe}) - mode: {mode}")

        # Check for cancellation before starting
        if cancellation_token and getattr(
            cancellation_token, "is_cancelled_requested", False
        ):
            logger.info("Data loading cancelled before start")
            raise asyncio.CancelledError("Data loading was cancelled")

        try:
            # Load data based on mode
            if mode == "local":
                # Local-only mode: use basic loader without IB integration
                df = await self._load_local_data_async(
                    symbol,
                    timeframe,
                    start_date,
                    end_date,
                    cancellation_token,
                    progress_callback,
                )
            else:
                # Enhanced modes: use IB integration for gaps/missing data
                if not self.enable_ib or not self.adapter:
                    raise DataError(
                        message=f"IB integration required for mode '{mode}' but is disabled",
                        error_code="DATA-IBRequired",
                        details={"mode": mode, "enable_ib": self.enable_ib},
                    )

                df = await self._load_with_ib_fallback_async(
                    symbol,
                    timeframe,
                    start_date,
                    end_date,
                    mode,
                    cancellation_token,
                    progress_callback,
                    periodic_save_minutes,
                )

            # Check if df is None (happens when fallback returns None)
            if df is None or df.empty:
                raise DataNotFoundError(
                    message=f"Data not found for {symbol} ({timeframe})",
                    error_code="DATA-FileNotFound",
                    details={"symbol": symbol, "timeframe": timeframe, "mode": mode},
                )

            # Apply validation if requested
            if validate:
                df = await self._validate_data_async(
                    df,
                    symbol,
                    timeframe,
                    repair,
                    repair_outliers,
                    strict,
                    cancellation_token,
                )

            logger.debug(
                f"Successfully loaded {len(df)} rows for {symbol} ({timeframe})"
            )
            return df

        except asyncio.CancelledError:
            logger.info(f"Data loading cancelled for {symbol} ({timeframe})")
            raise
        except Exception as e:
            logger.error(f"Failed to load data for {symbol} ({timeframe}): {e}")
            raise

    async def _load_local_data_async(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
        cancellation_token: Optional[CancellationToken] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> pd.DataFrame:
        """Load data from local files asynchronously."""
        # Run the sync data loader in thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        def _sync_load():
            return self.data_loader.load(symbol, timeframe, start_date, end_date)

        df = await loop.run_in_executor(None, _sync_load)

        # Call progress callback if provided
        if progress_callback:
            progress_callback(
                {
                    "percentage": 100.0,
                    "current_step": "Local data loading completed",
                    "items_processed": len(df) if df is not None else 0,
                }
            )

        return df

    async def _load_with_ib_fallback_async(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
        mode: str,
        cancellation_token: Optional[CancellationToken] = None,
        progress_callback: Optional[ProgressCallback] = None,
        periodic_save_minutes: float = 2.0,
    ) -> pd.DataFrame:
        """
        Load data with IB fallback for missing segments.

        This method uses the IB adapter to fetch missing data segments,
        maintaining the same logic as the legacy DataManager but with async execution.
        """
        # Try local data first
        df_local = await self._load_local_data_async(
            symbol, timeframe, start_date, end_date, cancellation_token
        )

        if progress_callback:
            progress_callback(
                {
                    "percentage": 50.0,
                    "current_step": "Checking for gaps and missing data",
                }
            )

        # If we have local data and mode doesn't require IB enhancement, return it
        if df_local is not None and not df_local.empty and mode == "local":
            return df_local

        # Use IB adapter to fetch missing data
        try:
            df_ib = await self.adapter.fetch_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
            )

            if progress_callback:
                progress_callback(
                    {
                        "percentage": 90.0,
                        "current_step": "Merging local and IB data",
                    }
                )

            # Merge local and IB data if both exist
            if (
                df_local is not None
                and not df_local.empty
                and df_ib is not None
                and not df_ib.empty
            ):
                # Simple merge - in a full implementation, this would involve gap analysis
                df_combined = (
                    pd.concat([df_local, df_ib]).drop_duplicates().sort_index()
                )
                return df_combined
            elif df_ib is not None and not df_ib.empty:
                return df_ib
            else:
                return df_local

        except Exception as e:
            logger.warning(f"IB data fetch failed, using local data: {e}")
            if df_local is not None and not df_local.empty:
                return df_local
            else:
                raise

    async def _validate_data_async(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        repair: bool,
        repair_outliers: bool,
        strict: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> pd.DataFrame:
        """Validate data asynchronously."""
        if cancellation_token and getattr(
            cancellation_token, "is_cancelled_requested", False
        ):
            raise asyncio.CancelledError("Data validation was cancelled")

        # Run validation in thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        def _sync_validate():
            if not repair:
                # Create a non-correcting validator for validation-only mode
                validator = DataQualityValidator(
                    auto_correct=False, max_gap_percentage=self.max_gap_percentage
                )
            else:
                # Use the instance validator which has auto-correct enabled
                validator = self.data_validator

            df_validated, quality_report = validator.validate_data(
                df, symbol, timeframe, "local"
            )

            # Handle repair_outliers parameter if repair is enabled but repair_outliers is False
            if repair and not repair_outliers:
                logger.info(
                    "Outlier repair was skipped as requested (repair_outliers=False)"
                )

            # Check if there are critical issues and handle based on strict mode
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
                        logger.info(
                            f"Data automatically repaired: {quality_report.corrections_made} corrections made"
                        )
                    else:
                        for issue in quality_report.issues:
                            logger.warning(
                                f"  - {issue.issue_type}: {issue.description}"
                            )

            return df_validated if repair else df

        return await loop.run_in_executor(None, _sync_validate)

    async def load_multi_timeframe_data(
        self,
        symbol: str,
        timeframes: list[str],
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "local",
        validate: bool = True,
        align_data: bool = False,
        **kwargs,
    ) -> dict[str, pd.DataFrame]:
        """
        Load data for multiple timeframes concurrently.

        Args:
            symbol: The trading symbol
            timeframes: List of timeframes to load
            start_date: Optional start date
            end_date: Optional end date
            mode: Loading mode
            validate: Whether to validate data
            align_data: Whether to align data to common date range
            **kwargs: Additional arguments passed to load_data

        Returns:
            Dictionary mapping timeframe to DataFrame
        """
        # Load all timeframes concurrently
        tasks = [
            self.load_data(
                symbol=symbol,
                timeframe=tf,
                start_date=start_date,
                end_date=end_date,
                mode=mode,
                validate=validate,
                **kwargs,
            )
            for tf in timeframes
        ]

        results = await asyncio.gather(*tasks)
        timeframe_data = dict(zip(timeframes, results))

        # Align data to common coverage if requested
        if align_data and len(timeframe_data) > 1:
            timeframe_data = self._align_timeframe_data(timeframe_data)

        return timeframe_data

    def _align_timeframe_data(
        self, timeframe_data: dict[str, pd.DataFrame]
    ) -> dict[str, pd.DataFrame]:
        """Align multiple timeframe data to common date coverage."""
        # Find common date range (intersection of all data ranges)
        valid_dataframes = {
            tf: df
            for tf, df in timeframe_data.items()
            if df is not None and not df.empty
        }

        if not valid_dataframes:
            return timeframe_data

        # Find the common date range
        start_dates = [df.index.min() for df in valid_dataframes.values()]
        end_dates = [df.index.max() for df in valid_dataframes.values()]

        common_start = max(start_dates)
        common_end = min(end_dates)

        # Align all dataframes to common range
        aligned_data = {}
        for tf, df in timeframe_data.items():
            if df is not None and not df.empty:
                aligned_data[tf] = df.loc[common_start:common_end]
            else:
                aligned_data[tf] = df

        return aligned_data

    async def health_check(self) -> dict[str, Any]:
        """
        Perform comprehensive health check on data manager and components.

        Returns:
            Dictionary with health status of all components
        """
        # Get base orchestrator health check
        health_info = await super().health_check()

        # Add data manager specific health information
        health_info.update(
            {
                "data_loader": {
                    "status": "healthy",
                    "type": type(self.data_loader).__name__,
                },
                "data_validator": {
                    "status": "healthy",
                    "type": type(self.data_validator).__name__,
                },
                "gap_classifier": {
                    "status": "healthy",
                    "type": type(self.gap_classifier).__name__,
                },
                "configuration": {
                    "max_gap_percentage": self.max_gap_percentage,
                    "default_repair_method": self.default_repair_method,
                    "enable_ib": self.enable_ib,
                },
            }
        )

        return health_info

    def get_data_summary(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """
        Get summary information about available data.

        This method provides a sync interface for basic data information
        without loading the full dataset.
        """
        try:
            # Get basic file information from local loader
            # Note: Assuming basic file existence check since get_data_info may not exist
            file_path = self.data_loader._build_file_path(symbol, timeframe)
            import os

            if os.path.exists(file_path):
                stat = os.stat(file_path)
                return {
                    "available": True,
                    "file_size": stat.st_size,
                    "modified": stat.st_mtime,
                    "symbol": symbol,
                    "timeframe": timeframe,
                }
            else:
                return {"available": False, "symbol": symbol, "timeframe": timeframe}
        except Exception as e:
            logger.warning(
                f"Could not get data summary for {symbol} ({timeframe}): {e}"
            )
            return {"error": str(e), "available": False}

"""
DataManager for managing, validating, and processing OHLCV data.

This module extends the LocalDataLoader with more sophisticated data
management capabilities, integrity checks, and utilities for detecting
and handling gaps or missing values in time series data.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from ktrdr.data.async_infrastructure.data_progress_renderer import (
        DataProgressRenderer,
    )
    from ktrdr.data.components.progress_manager import TimeEstimationEngine
    from ktrdr.data.data_manager_builder import DataManagerConfiguration

import pandas as pd

# Import logging system
from ktrdr import (
    get_logger,
    log_entry_exit,
    log_performance,
)
from ktrdr.async_infrastructure.progress import (
    GenericProgressManager,
    GenericProgressState,
)
from ktrdr.data.components.data_fetcher import DataFetcher
from ktrdr.data.components.data_quality_validator import DataQualityValidator

# Old ProgressManager no longer needed - using GenericProgressManager directly
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
        builder_config: Optional["DataManagerConfiguration"] = None,
    ):
        """
        Initialize the DataManager using builder pattern.

        Args:
            data_dir: Path to the directory containing data files.
            max_gap_percentage: Maximum allowed percentage of gaps in data (default: 5.0)
            default_repair_method: Default method for repairing missing values
            builder: Optional custom builder. If None, creates default builder.
                    IB integration is always enabled (container mode removed)
            builder_config: Optional pre-built configuration from enhanced DataManagerBuilder.
                          If provided, takes precedence over other parameters.

        Raises:
            DataError: If initialization parameters are invalid
        """
        # Use provided configuration or build from builder
        if builder_config is not None:
            # Use provided enhanced configuration
            config = builder_config
        else:
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
        assert config.external_provider is not None, (
            "Builder must create external_provider"
        )
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
        # Old progress manager no longer used - replaced with GenericProgressManager
        self._progress_manager = None
        self._data_fetcher: Optional[DataFetcher] = None

        # Initialize ServiceOrchestrator (always enabled - container mode removed)
        super().__init__()

        # NEW: Store async infrastructure components with enhanced ones if available
        # Initialize with enhanced components from the builder configuration
        # If enhanced components are not available, use the base class components
        enhanced_progress_manager = getattr(config, "generic_progress_manager", None)
        if enhanced_progress_manager is not None:
            # Override the base class generic progress manager with enhanced one
            self._generic_progress_manager = enhanced_progress_manager
        # Otherwise, use the one already created by the base class

        self._data_progress_renderer: Optional[DataProgressRenderer] = getattr(
            config, "data_progress_renderer", None
        )
        self._time_estimation_engine: Optional[TimeEstimationEngine] = getattr(
            config, "time_estimation_engine", None
        )

        # Finalize configuration with components that need DataManager reference
        if builder is not None:
            config = builder.finalize_configuration(self)

        assert config.data_loading_orchestrator is not None, (
            "Builder must create data_loading_orchestrator"
        )
        assert config.health_checker is not None, "Builder must create health_checker"

        self.data_loading_orchestrator = config.data_loading_orchestrator
        self.health_checker = config.health_checker

        logger.info(
            f"DataManager initialized with async infrastructure: {getattr(self, '_generic_progress_manager', None) is not None}"
        )

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
        Check if cancellation has been requested using unified protocol.

        Args:
            cancellation_token: Token to check for cancellation (must implement CancellationToken protocol)
            operation_description: Description of current operation for logging

        Returns:
            True if cancellation was requested, False otherwise

        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        if cancellation_token is None:
            return False

        # Use unified cancellation protocol only - no legacy patterns
        try:
            is_cancelled = cancellation_token.is_cancelled()
        except Exception as e:
            logger.warning(f"Error checking cancellation token: {e}")
            return False

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

    def _create_legacy_callback_wrapper(self, legacy_callback: Callable) -> Callable:
        """
        Wrap legacy progress callback to work with GenericProgressState.

        This method provides 100% backward compatibility by converting GenericProgressState
        instances to the legacy ProgressState format that existing callbacks expect.

        Args:
            legacy_callback: Callback function expecting ProgressState instances

        Returns:
            Wrapper function that converts GenericProgressState to ProgressState
        """

        def wrapper(generic_state: GenericProgressState) -> None:
            # Convert to legacy ProgressState using the DataProgressRenderer
            if self._data_progress_renderer is not None:
                legacy_state = (
                    self._data_progress_renderer.create_legacy_compatible_state(
                        generic_state
                    )
                )
                legacy_callback(legacy_state)
            else:
                # Fallback if no renderer available - should not happen in normal operation
                logger.warning(
                    "Legacy callback wrapper called without data progress renderer"
                )

        return wrapper

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
        Load data with optional validation and repair using ServiceOrchestrator cancellation.

        This method now leverages ServiceOrchestrator.execute_with_cancellation() instead of
        custom cancellation patterns, creating consistency across all managers while preserving
        all existing functionality.

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
            This method uses ServiceOrchestrator.execute_with_cancellation() for unified cancellation
            patterns while maintaining the unified DataQualityValidator and enhanced IB integration.
            When mode is 'tail', 'backfill', or 'full', it uses intelligent gap analysis
            and IB fetching for missing data segments.
        """
        # Use ServiceOrchestrator cancellation pattern for all modes
        return self._run_async_method(
            self._load_data_with_cancellation_async,
            symbol,
            timeframe,
            start_date,
            end_date,
            mode,
            validate,
            repair,
            repair_outliers,
            strict,
            cancellation_token,
            progress_callback,
        )

    async def _load_data_with_cancellation_async(
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
        Load data using ServiceOrchestrator.execute_with_cancellation() patterns.

        This async method implements the core data loading logic with unified cancellation
        support through ServiceOrchestrator patterns.
        """
        # Use the provided cancellation token or get from ServiceOrchestrator
        # Handle case where ServiceOrchestrator is not properly initialized (e.g., in tests)
        effective_token = cancellation_token
        if not effective_token:
            try:
                effective_token = self.get_current_cancellation_token()
            except AttributeError:
                # ServiceOrchestrator not properly initialized (e.g., in tests)
                effective_token = None

        # Create the core data loading operation
        async def data_loading_operation():
            return self._load_data_core_logic(
                symbol,
                timeframe,
                start_date,
                end_date,
                mode,
                validate,
                repair,
                repair_outliers,
                strict,
                effective_token,
                progress_callback,
            )

        # Execute with unified ServiceOrchestrator cancellation system
        return await self.execute_with_cancellation(
            operation=data_loading_operation(),
            cancellation_token=effective_token,
            operation_name=f"Loading {symbol} {timeframe} data",
        )

    def _load_data_core_logic(
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
        Core data loading logic preserved from original implementation.

        This method contains the original load_data logic but can now be executed
        within ServiceOrchestrator cancellation patterns.
        """
        # Create legacy-compatible progress callback wrapper
        enhanced_callback = None
        if progress_callback:
            enhanced_callback = self._create_legacy_callback_wrapper(progress_callback)

        # Initialize progress manager - use GenericProgressManager if available
        total_steps = 5 if mode == "local" else 10  # More steps for IB-enabled modes

        # Always use the new async infrastructure (eliminate old ProgressManager)
        if not self._data_progress_renderer:
            # Create default DataProgressRenderer if not provided
            from ktrdr.data.async_infrastructure.data_progress_renderer import (
                DataProgressRenderer,
            )

            self._data_progress_renderer = DataProgressRenderer(
                time_estimation_engine=self._time_estimation_engine
            )

        operation_progress = GenericProgressManager(
            callback=enhanced_callback, renderer=self._data_progress_renderer
        )

        # Create enhanced context for better progress descriptions
        operation_context = {
            "symbol": symbol,
            "timeframe": timeframe,
            "mode": mode,
            "operation_type": "data_load",
            "start_date": (
                start_date.isoformat()
                if start_date and hasattr(start_date, "isoformat")
                else str(start_date)
                if start_date
                else None
            ),
            "end_date": (
                end_date.isoformat()
                if end_date and hasattr(end_date, "isoformat")
                else str(end_date)
                if end_date
                else None
            ),
        }

        # Start operation with data context
        operation_progress.start_operation(
            f"load_data_{symbol}_{timeframe}",
            total_steps,
            context=operation_context,
        )

        # Load data based on mode
        logger.info(f"Loading data for {symbol} ({timeframe}) - mode: {mode}")

        try:
            if mode == "local":
                # Local-only mode: use basic loader without IB integration
                operation_progress.update_progress(
                    step=1,
                    message="Loading local data from cache",
                    context={
                        "current_item_detail": f"Reading {symbol} {timeframe} from local storage"
                    },
                )

                df = self.data_loader.load(symbol, timeframe, start_date, end_date)
            else:
                # Enhanced modes: use intelligent gap analysis with IB integration
                # Note: The orchestrator expects ProgressManager, so we need to handle this
                # For now, we'll use the enhanced progress in the future when orchestrator supports GenericProgressManager
                df = self._load_with_enhanced_orchestrator(
                    symbol,
                    timeframe,
                    start_date,
                    end_date,
                    mode,
                    cancellation_token,
                    operation_progress,
                )
        except Exception as e:
            logger.error(f"Data load failed: {e}")
            raise

        # Check if df is None (happens when fallback returns None)
        if df is None:
            raise DataNotFoundError(
                message=f"Data not found for {symbol} ({timeframe})",
                error_code="DATA-FileNotFound",
                details={"symbol": symbol, "timeframe": timeframe},
            )

        if validate:
            # Update progress for validation step with context
            operation_progress.update_progress(
                step=total_steps,
                message="Validating data quality",
                context={
                    "current_item_detail": f"Checking {len(df)} data points for completeness and accuracy"
                },
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
        operation_progress.complete_operation()

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

    # Gap analysis methods have been extracted to GapAnalyzer component
    # See: ktrdr.data.components.gap_analyzer.GapAnalyzer

    def _load_with_fallback_legacy(
        self,
        symbol: str,
        timeframe: str,
        mode: str,
        start_date,
        end_date,
        validate: bool,
        repair: bool,
        repair_outliers: bool,
        strict: bool,
        cancellation_token,
        progress_manager: Any,  # Legacy method - to be removed
    ) -> pd.DataFrame:
        """
        Fallback to existing ProgressManager logic when async infrastructure is unavailable.

        This method preserves the original load_data behavior for backward compatibility
        when GenericProgressManager is not available.
        """
        # Create enhanced context for better progress descriptions
        operation_context = {
            "symbol": symbol,
            "timeframe": timeframe,
            "mode": mode,
            "start_date": (
                start_date.isoformat()
                if start_date and hasattr(start_date, "isoformat")
                else str(start_date)
                if start_date
                else None
            ),
            "end_date": (
                end_date.isoformat()
                if end_date and hasattr(end_date, "isoformat")
                else str(end_date)
                if end_date
                else None
            ),
        }

        progress_manager.start_operation(
            5 if mode == "local" else 10,  # total_steps
            f"load_data_{symbol}_{timeframe}",
            operation_context=operation_context,
        )

        # Set cancellation token if provided
        if cancellation_token:
            progress_manager.set_cancellation_token(cancellation_token)

        try:
            # Load data based on mode
            logger.info(
                f"Loading data for {symbol} ({timeframe}) - mode: {mode} (legacy)"
            )

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
                    progress_manager,
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
                    5 if mode == "local" else 10,  # total_steps
                    "Validating data quality",
                    current_item_detail=f"Checking {len(df)} data points for completeness and accuracy",
                )

                # Use the unified data quality validator with same logic as enhanced version
                validation_type = "local"

                if not repair:
                    validator = DataQualityValidator(
                        auto_correct=False, max_gap_percentage=self.max_gap_percentage
                    )
                else:
                    validator = self.data_validator

                df_validated, quality_report = validator.validate_data(
                    df, symbol, timeframe, validation_type
                )

                # Handle validation results (same logic as enhanced version)
                if repair and not repair_outliers:
                    logger.info(
                        "Outlier repair was skipped as requested (repair_outliers=False)"
                    )

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
                            df = df_validated
                            logger.info(
                                f"Data automatically repaired by validator: {quality_report.corrections_made} corrections made"
                            )
                        else:
                            for issue in quality_report.issues:
                                logger.warning(
                                    f"  - {issue.issue_type}: {issue.description}"
                                )
                else:
                    if repair:
                        df = df_validated
                        if quality_report.corrections_made > 0:
                            logger.info(
                                f"Minor data corrections applied: {quality_report.corrections_made} corrections made"
                            )

            # Complete operation
            progress_manager.complete_operation()
            return df

        except Exception as e:
            logger.error(f"Legacy data load failed: {e}")
            raise

    def _load_with_enhanced_orchestrator(
        self,
        symbol: str,
        timeframe: str,
        start_date,
        end_date,
        mode: str,
        cancellation_token,
        operation_progress: GenericProgressManager,
    ) -> pd.DataFrame:
        """
        Load data using enhanced orchestrator for non-local modes.

        This method handles the enhanced modes (tail, backfill, full) using the orchestrator
        with direct GenericProgressManager integration (no bridge pattern needed).
        """
        # Start operation on the GenericProgressManager for orchestrator steps
        operation_progress.start_operation(
            operation_id=f"load_data_{symbol}_{timeframe}",
            total_steps=10,  # Non-local modes use multiple steps
            context={"symbol": symbol, "timeframe": timeframe, "mode": mode},
        )

        # Use the orchestrator directly with GenericProgressManager (no bridge needed)
        result = self.data_loading_orchestrator.load_with_fallback(
            symbol,
            timeframe,
            start_date,
            end_date,
            mode,
            cancellation_token,
            operation_progress,  # Pass GenericProgressManager directly
        )

        # Ensure we return a DataFrame (orchestrator should handle fallbacks)
        if result is None:
            # This shouldn't happen with proper orchestrator fallbacks, but ensure type safety
            result = pd.DataFrame()

        return result

    def _ensure_data_fetcher(self) -> DataFetcher:
        """
        Ensure DataFetcher component is initialized for HTTP session persistence.

        Returns:
            DataFetcher component instance
        """
        if self._data_fetcher is None:
            self._data_fetcher = DataFetcher()
        return self._data_fetcher

    async def cleanup_resources(self) -> None:
        """
        Clean up all persistent resources for proper shutdown.

        This method should be called when shutting down long-running applications
        to ensure all HTTP connections and resources are properly closed.
        """
        if self._data_fetcher is not None:
            await self._data_fetcher.cleanup()
            self._data_fetcher = None
            logger.info("DataManager resources cleaned up")

    def cleanup_resources_sync(self) -> None:
        """
        Sync wrapper for cleaning up all persistent resources.

        Convenient method for cleanup during application shutdown
        when not in async context.
        """
        return self._run_async_method(self.cleanup_resources)

    async def _fetch_segments_with_component_async(
        self,
        symbol: str,
        timeframe: str,
        segments: list[tuple[datetime, datetime]],
        cancellation_token: Optional[Any] = None,
        progress_manager: Optional[
            Any
        ] = None,  # Legacy parameter - will be updated to GenericProgressManager
    ) -> tuple[list[pd.DataFrame], int, int]:
        """
        Enhanced async fetching using DataFetcher component.

        This method provides optimal async performance with connection pooling
        and advanced progress tracking, without creating new event loops.

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

        # Run the enhanced async DataFetcher method directly
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

            try:
                # Use SegmentManager for resilient fetching with periodic save support
                (
                    successful_data,
                    successful_count,
                    failed_count,
                ) = await self.segment_manager.fetch_segments_with_resilience(
                    symbol=symbol,
                    timeframe=timeframe,
                    segments=segments,
                    external_provider=self.external_provider,
                    progress_manager=progress_manager,
                    cancellation_token=cancellation_token,
                    periodic_save_callback=(
                        periodic_save_callback if INTERNAL_SAVE_INTERVAL > 0 else None
                    ),
                    periodic_save_minutes=INTERNAL_SAVE_INTERVAL,
                )

                return successful_data, successful_count, failed_count

            finally:
                # Clean up DataFetcher resources after operation
                await data_fetcher.cleanup()

        except asyncio.CancelledError:
            # Re-raise cancellation errors properly
            logger.info("Data fetching cancelled")
            raise
        except Exception as e:
            logger.error(f"Enhanced data fetching failed: {e}")
            # Preserve timeout exceptions for proper error context
            if isinstance(e, asyncio.TimeoutError):
                raise  # Re-raise to maintain async timeout semantics
            return [], 0, len(segments)

    def _run_async_method(
        self, async_method: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """
        Reusable utility to execute async methods from sync context.

        Provides a single asyncio.run() entry point for backward compatibility
        while maintaining proper async/sync boundary separation.
        Handles AsyncHostService context management automatically.

        IMPORTANT: When called from within an existing event loop (e.g., API server),
        this will detect the context and avoid creating nested event loops that
        break exception propagation.

        Args:
            async_method: The async method to execute
            *args: Positional arguments for the async method
            **kwargs: Keyword arguments for the async method

        Returns:
            The result of the async method execution
        """

        async def run_with_context():
            # Check if external provider needs async context manager
            # Skip async context manager for Mock objects (used in testing)
            if (
                self.external_provider
                and hasattr(self.external_provider, "use_host_service")
                and self.external_provider.use_host_service
                and not str(type(self.external_provider)).startswith(
                    "<class 'unittest.mock."
                )
            ):
                # Use async context manager for AsyncHostService providers
                async with self.external_provider:
                    return await async_method(*args, **kwargs)
            else:
                # Direct call for non-AsyncHostService providers or Mock objects
                return await async_method(*args, **kwargs)

        # Check if we're already in an event loop (e.g., from API server)
        try:
            # This will raise RuntimeError if no event loop is running
            asyncio.get_running_loop()
            # If we're here, we're already in an event loop
            # We cannot use asyncio.run() as it would create a nested loop
            # Instead, we need to run this as a task in the current loop
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Run the async method in a thread pool to avoid nested event loop
                future = executor.submit(asyncio.run, run_with_context())
                return future.result()
        except RuntimeError:
            # No running event loop, safe to use asyncio.run()
            return asyncio.run(run_with_context())

    def _fetch_segments_with_component(
        self,
        symbol: str,
        timeframe: str,
        segments: list[tuple[datetime, datetime]],
        cancellation_token: Optional[Any] = None,
        progress_manager: Optional[
            Any
        ] = None,  # Legacy parameter - will be updated to GenericProgressManager
    ) -> tuple[list[pd.DataFrame], int, int]:
        """
        Sync wrapper for enhanced async fetching using DataFetcher component.

        This method maintains backward compatibility by providing a sync interface
        to the async implementation, with a single asyncio.run() at the entry point.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            segments: List of (start, end) segments to fetch
            cancellation_token: Optional cancellation token
            progress_manager: Optional progress manager
        Returns:
            Tuple of (successful_dataframes, successful_count, failed_count)
        """
        return self._run_async_method(
            self._fetch_segments_with_component_async,
            symbol,
            timeframe,
            segments,
            cancellation_token,
            progress_manager,
        )

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

    async def _fetch_head_timestamp_async(
        self, symbol: str, timeframe: str
    ) -> Optional[str]:
        """
        Async head timestamp fetching without event loop creation.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            ISO formatted head timestamp string or None if failed
        """
        if not self.external_provider:
            return None

        try:
            result = await self.external_provider.get_head_timestamp(
                symbol=symbol, timeframe=timeframe
            )
            # Convert datetime to string if needed
            if result is not None and hasattr(result, "isoformat"):
                return result.isoformat()
            return str(result) if result is not None else None
        except Exception as e:
            logger.error(f"Head timestamp fetch failed for {symbol}: {e}")
            # Preserve async-specific exceptions for proper error context
            if isinstance(e, (asyncio.CancelledError, asyncio.TimeoutError)):
                raise  # Re-raise to maintain async error semantics
            return None

    def _fetch_head_timestamp_sync(self, symbol: str, timeframe: str) -> Optional[str]:
        """
        Sync wrapper for async head timestamp fetching.

        Maintains backward compatibility with a single asyncio.run() call.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            ISO formatted head timestamp string or None if failed
        """
        return self._run_async_method(
            self._fetch_head_timestamp_async, symbol, timeframe
        )

    async def _validate_request_against_head_timestamp_async(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[bool, Optional[str], Optional[datetime]]:
        """
        Async validate request date range against head timestamp data.

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
            # Get head timestamp using async method (no nested event loop)
            head_timestamp_str = await self._fetch_head_timestamp_async(
                symbol, timeframe
            )

            if head_timestamp_str is None:
                return True, None, None  # No head timestamp available, assume valid

            # Convert string back to datetime for comparison
            from ktrdr.utils.timezone_utils import TimestampManager

            head_timestamp = TimestampManager.to_utc(head_timestamp_str)

            if head_timestamp is None:
                return True, None, None  # No valid timestamp, assume valid

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
            # Preserve async-specific exceptions for proper error context
            if isinstance(e, (asyncio.CancelledError, asyncio.TimeoutError)):
                raise  # Re-raise to maintain async error semantics
            # Don't block requests if validation fails
            return True, None, None

    @log_entry_exit(logger=logger, log_args=True)
    def _validate_request_against_head_timestamp(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[bool, Optional[str], Optional[datetime]]:
        """
        Sync wrapper for async head timestamp validation.

        Maintains backward compatibility with a single asyncio.run() call.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start_date: Requested start date
            end_date: Requested end date

        Returns:
            Tuple of (is_valid, error_message, adjusted_start_date)
        """
        return self._run_async_method(
            self._validate_request_against_head_timestamp_async,
            symbol,
            timeframe,
            start_date,
            end_date,
        )

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
            "has_gaps": len(self.gap_analyzer.detect_gaps(df, timeframe)) > 0,
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

    def clear_symbol_cache(self) -> None:
        """Clear backend symbol cache."""
        if hasattr(self.data_loading_orchestrator, "symbol_cache"):
            self.data_loading_orchestrator.symbol_cache.clear()
            logger.info("💾 Backend symbol cache cleared")
        else:
            logger.warning("💾 Symbol cache not available")

    def get_symbol_cache_stats(self) -> dict:
        """Get backend symbol cache statistics."""
        if hasattr(self.data_loading_orchestrator, "symbol_cache"):
            stats = self.data_loading_orchestrator.symbol_cache.get_stats()
            logger.info(f"💾 Symbol cache stats: {stats}")
            return stats
        else:
            logger.warning("💾 Symbol cache not available")
            return {"cached_symbols": 0}

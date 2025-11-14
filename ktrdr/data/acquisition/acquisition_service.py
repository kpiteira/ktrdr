"""
Data Acquisition Service.

Orchestrates external data acquisition from providers (IB) with progress tracking,
gap analysis, and intelligent segmentation.

This service composes DataRepository for cache operations and uses IbDataProvider
for external data fetching via HTTP.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Union

import pandas as pd

from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator
from ktrdr.data.acquisition.gap_analyzer import GapAnalyzer
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider
from ktrdr.data.acquisition.segment_manager import SegmentManager
from ktrdr.data.async_infrastructure.data_progress_renderer import DataProgressRenderer
from ktrdr.data.components.symbol_cache import SymbolCache
from ktrdr.data.repository import DataRepository
from ktrdr.errors.exceptions import DataNotFoundError
from ktrdr.monitoring.service_telemetry import trace_service_method

logger = logging.getLogger(__name__)


class DataAcquisitionService(ServiceOrchestrator[IbDataProvider]):
    """
    External data acquisition orchestrator.

    Orchestrates complex data acquisition operations:
    - Checks cache for existing data (via DataRepository)
    - Analyzes gaps in cached data
    - Downloads missing data from external providers (IB)
    - Saves downloaded data to cache (via DataRepository)
    - Tracks progress via Operations service
    - Supports cancellation

    This service composes DataRepository (has-a relationship) for cache operations
    rather than inheriting from it, maintaining clean separation of concerns.

    Architecture Pattern:
    - Inherits from ServiceOrchestrator for async operations infrastructure
    - Composes DataRepository for cache operations
    - Uses IbDataProvider for external data fetching
    """

    # Configuration constants with environment variable overrides (Task 4.4)
    MAX_SEGMENT_SIZE = int(os.getenv("DATA_MAX_SEGMENT_SIZE", "5000"))
    PERIODIC_SAVE_INTERVAL = float(os.getenv("DATA_PERIODIC_SAVE_MIN", "0.5"))

    def __init__(
        self,
        repository: Optional[DataRepository] = None,
        provider: Optional[IbDataProvider] = None,
        gap_analyzer: Optional[GapAnalyzer] = None,
        symbol_cache: Optional[SymbolCache] = None,
        segment_manager: Optional[SegmentManager] = None,
    ) -> None:
        """
        Initialize data acquisition service.

        Args:
            repository: Optional DataRepository instance for cache operations.
                       If None, creates default instance.
            provider: Optional IbDataProvider instance for external data.
                     If None, creates default instance.
            gap_analyzer: Optional GapAnalyzer for gap analysis.
                         If None, creates default instance.
            symbol_cache: Optional SymbolCache for caching head timestamps.
                         If None, creates default instance.
            segment_manager: Optional SegmentManager for resilient segment fetching.
                           If None, creates default instance.
        """
        # Store dependencies BEFORE calling super().__init__
        # because _initialize_adapter() will be called during super().__init__
        # and it needs these to be available
        self._repository_instance = repository
        self._provider_instance = provider

        # Initialize ServiceOrchestrator (calls _initialize_adapter)
        super().__init__()

        # Composition: DataRepository for cache operations
        self.repository = self._repository_instance or DataRepository()

        # Gap analysis components (Task 4.3)
        self.gap_analyzer = gap_analyzer or GapAnalyzer()
        self.symbol_cache = symbol_cache or SymbolCache()

        # Segment management for resilient downloads (Task 4.4)
        self.segment_manager = segment_manager or SegmentManager()

        # Configuration constants as instance attributes (Task 4.4)
        self.max_segment_size = self.MAX_SEGMENT_SIZE
        self.periodic_save_interval = self.PERIODIC_SAVE_INTERVAL

        # Initialize data-specific progress renderer (Task 4.6)
        # This provides the same progress UX as DataManager
        self._progress_renderer = DataProgressRenderer()

        logger.info(
            f"DataAcquisitionService initialized "
            f"(repository: {type(self.repository).__name__}, "
            f"provider: {type(self.provider).__name__}, "
            f"gap_analyzer: {type(self.gap_analyzer).__name__}, "
            f"symbol_cache: {type(self.symbol_cache).__name__}, "
            f"segment_manager: {type(self.segment_manager).__name__}, "
            f"progress_renderer: {type(self._progress_renderer).__name__})"
        )

    def _initialize_adapter(self) -> IbDataProvider:
        """
        Initialize the data provider adapter.

        Returns:
            IbDataProvider instance for external data fetching
        """
        # Use provided instance or create default
        if self._provider_instance is not None:
            provider = self._provider_instance
        else:
            # Read IB_HOST_SERVICE_URL from environment (critical for Docker)
            import os

            host_service_url = os.getenv("IB_HOST_SERVICE_URL")
            provider = IbDataProvider(host_service_url=host_service_url)

        # Store provider as instance attribute for easy access
        self.provider = provider

        # Return provider as adapter (ServiceOrchestrator requirement)
        return provider

    def _get_service_name(self) -> str:
        """
        Get service name for logging and configuration.

        Returns:
            Human-readable service name
        """
        return "Data/Acquisition"

    def _get_default_host_url(self) -> str:
        """
        Get default host service URL.

        Returns:
            Default IB host service URL
        """
        return "http://localhost:5001"

    def _get_env_var_prefix(self) -> str:
        """
        Get environment variable prefix for configuration.

        Uses IB prefix since acquisition service uses IB provider.

        Returns:
            Environment variable prefix (uppercase)
        """
        return "IB"

    async def _fetch_head_timestamp(
        self, symbol: str, timeframe: str
    ) -> Optional[datetime]:
        """
        Fetch head timestamp from provider with caching.

        Extracted from DataManager (Task 4.3).

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            Head timestamp datetime or None if failed
        """
        # Check cache first
        cached_info = self.symbol_cache.get(symbol)
        if cached_info and cached_info.validation_result:
            # Check if head_timestamps exists and is not None
            head_timestamps = cached_info.validation_result.get("head_timestamps")
            if (
                head_timestamps
                and isinstance(head_timestamps, dict)
                and timeframe in head_timestamps
            ):
                timestamp_str = head_timestamps[timeframe]
                logger.debug(
                    f"📅 Cache hit for {symbol} head timestamp: {timestamp_str}"
                )
                # Convert string to datetime if needed
                if isinstance(timestamp_str, str):
                    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                return timestamp_str

        # Fetch from provider
        try:
            result = await self.provider.get_head_timestamp(
                symbol=symbol, timeframe=timeframe
            )
            logger.debug(f"📅 Fetched head timestamp for {symbol}: {result}")

            # Cache the result if successful
            if result is not None:
                from ktrdr.data.components.symbol_cache import ValidationResult

                # Get existing cache or create new
                cached_info = self.symbol_cache.get(symbol)

                if cached_info and cached_info.validation_result:
                    # Update existing cache entry
                    vr = cached_info.validation_result
                    head_timestamps = vr.get("head_timestamps") or {}
                    head_timestamps[timeframe] = (
                        result.isoformat() if isinstance(result, datetime) else result
                    )

                    validation_result = ValidationResult(
                        is_valid=vr.get("is_valid", True),
                        symbol=symbol,
                        error_message=vr.get("error_message"),
                        contract_info=vr.get("contract_info"),
                        head_timestamps=head_timestamps,
                        suggested_symbol=vr.get("suggested_symbol"),
                    )
                else:
                    # Create new cache entry with just head timestamp
                    validation_result = ValidationResult(
                        is_valid=True,
                        symbol=symbol,
                        head_timestamps={
                            timeframe: (
                                result.isoformat()
                                if isinstance(result, datetime)
                                else result
                            )
                        },
                    )

                self.symbol_cache.store(symbol, validation_result)

            return result
        except Exception as e:
            logger.error(f"Head timestamp fetch failed for {symbol}: {e}")
            return None

    async def _validate_request_against_head_timestamp(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[bool, Optional[str], Optional[datetime]]:
        """
        Validate request date range against head timestamp data.

        Extracted from DataManager (Task 4.3).

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start_date: Requested start date
            end_date: Requested end date

        Returns:
            Tuple of (is_valid, error_message, adjusted_start_date)
        """
        try:
            # Get head timestamp
            head_timestamp = await self._fetch_head_timestamp(symbol, timeframe)

            if head_timestamp is None:
                return True, None, None  # No head timestamp available, assume valid

            # Ensure timezone consistency
            if head_timestamp.tzinfo is None:
                head_timestamp = head_timestamp.replace(tzinfo=start_date.tzinfo)
            elif start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=head_timestamp.tzinfo)

            # Check if start_date is before head timestamp
            if start_date < head_timestamp:
                error_message = (
                    f"Requested start date {start_date} is before "
                    f"earliest available data {head_timestamp}"
                )
                logger.warning(f"📅 HEAD TIMESTAMP VALIDATION FAILED: {error_message}")
                return False, error_message, head_timestamp
            else:
                logger.debug(
                    f"📅 HEAD TIMESTAMP VALIDATION PASSED: {symbol} from {start_date}"
                )
                return True, None, None

        except Exception as e:
            logger.warning(f"Head timestamp validation failed for {symbol}: {e}")
            # Don't block requests if validation fails
            return True, None, None

    async def _ensure_symbol_has_head_timestamp(
        self, symbol: str, timeframe: str
    ) -> bool:
        """
        Ensure symbol has head timestamp data, triggering validation if needed.

        Extracted from DataManager (Task 4.3).

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            True if head timestamp is available, False otherwise
        """
        try:
            # Fetch head timestamp (will use cache if available)
            head_timestamp = await self._fetch_head_timestamp(symbol, timeframe)

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

    def _save_periodic_progress(
        self,
        successful_data: list[pd.DataFrame],
        symbol: str,
        timeframe: str,
        previous_bars_saved: int,
    ) -> int:
        """
        Save accumulated data progress to cache.

        Extracted from DataManager (Task 4.4).

        This merges the new data with any existing data and saves to cache,
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
                existing_data = self.repository.load_from_cache(symbol, timeframe)
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
            self.repository.save_to_cache(symbol, timeframe, combined_data)

            return new_bars_count

        except Exception as e:
            logger.error(f"Failed to save periodic progress: {e}")
            raise

    def _create_periodic_save_callback(
        self, symbol: str, timeframe: str
    ) -> Callable[[list[pd.DataFrame]], int]:
        """
        Create periodic save callback closure.

        Creates a callback that captures symbol/timeframe context
        for use by SegmentManager during resilient fetching.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            Callback function for periodic saves
        """

        def periodic_save_callback(successful_data_list: list[pd.DataFrame]) -> int:
            """Callback for periodic progress saving during fetch."""
            return self._save_periodic_progress(
                successful_data_list,
                symbol,
                timeframe,
                0,  # TODO: Track previous bars properly if needed
            )

        return periodic_save_callback

    @trace_service_method("data.download")
    async def download_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "tail",
    ) -> dict[str, Any]:
        """
        Download data from external provider (IB) with gap analysis.

        Enhanced download flow (Task 4.3):
        1. Check cache for existing data
        2. Validate head timestamp
        3. Analyze gaps based on mode
        4. Download missing data
        5. Save to cache

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EURUSD')
            timeframe: Data timeframe (e.g., '1h', '1d')
            start_date: Optional start date for data range
            end_date: Optional end date for data range
            mode: Download mode - 'tail' (recent), 'backfill' (historical), 'full' (all gaps)

        Returns:
            Dictionary with operation tracking information:
            {
                "operation_id": str,
                "status": str,
                "message": str
            }

        Note:
            Uses ServiceOrchestrator.start_managed_operation() for
            background execution with progress tracking and cancellation support.
        """
        logger.info(
            f"Starting data download for {symbol} {timeframe} "
            f"(mode: {mode}, start: {start_date}, end: {end_date})"
        )

        # Validate mode
        if mode not in ["tail", "backfill", "full"]:
            raise ValueError(
                f"Invalid mode: {mode}. Must be 'tail', 'backfill', or 'full'"
            )

        # Define the download operation function
        async def _download_operation() -> dict[str, Any]:
            """Internal download operation with gap analysis flow."""
            # Get progress_manager from ServiceOrchestrator context for step tracking
            progress_manager = self._current_operation_progress

            # Step 0: Validate symbol (Task 4.7 - Bug Fix)
            if progress_manager:
                progress_manager.start_step(
                    f"Validating symbol {symbol}",
                    step_number=0,
                    step_percentage=0.0,
                    step_end_percentage=5.0,
                )

            # Validate symbol and get metadata
            # This will raise DataProviderDataError if symbol is invalid
            logger.info(f"📋 Validating symbol {symbol} via provider")
            validation_result = await self.provider.validate_and_get_metadata(
                symbol, [timeframe]
            )
            logger.info(f"✅ Symbol {symbol} validated successfully")

            # Cache validation result for future use
            self.symbol_cache.store(symbol, validation_result)

            # Step 1: Check cache
            if progress_manager:
                progress_manager.start_step(
                    f"Loading cached data for {symbol} {timeframe}",
                    step_number=1,
                    step_percentage=5.0,
                    step_end_percentage=15.0,
                )

            try:
                logger.debug(f"Checking cache for {symbol} {timeframe}")
                existing_data = self.repository.load_from_cache(
                    symbol, timeframe, start_date, end_date
                )
                logger.info(
                    f"Found {len(existing_data)} rows in cache for {symbol} {timeframe}"
                )
                cache_exists = True
            except DataNotFoundError:
                logger.debug(f"No cached data found for {symbol} {timeframe}")
                cache_exists = False
                existing_data = None

            # Convert dates if needed and handle defaults
            # CRITICAL: Smart defaults based on mode (matches DataManager behavior)
            if start_date is not None:
                if isinstance(start_date, str):
                    start_dt: datetime = datetime.fromisoformat(start_date)
                else:
                    start_dt = start_date
            else:
                # Smart default based on mode
                if mode == "tail":
                    # Tail mode: recent data (last 30 days)
                    start_dt = datetime.now() - timedelta(days=30)
                    logger.debug(
                        f"📅 TAIL mode: Using default start (last 30 days): {start_dt}"
                    )
                elif mode in ["backfill", "full"]:
                    # Backfill/Full mode: Use head timestamp if available, otherwise IB limits
                    head_timestamp_used = False

                    # Try to get head timestamp from validation result
                    if validation_result and validation_result.head_timestamps:
                        if timeframe in validation_result.head_timestamps:
                            head_ts_str = validation_result.head_timestamps[timeframe]
                            if head_ts_str:
                                try:
                                    start_dt = datetime.fromisoformat(
                                        head_ts_str.replace("Z", "+00:00")
                                    )
                                    head_timestamp_used = True
                                    logger.info(
                                        f"📅 {mode.upper()} mode: Using head timestamp for default start: {start_dt}"
                                    )
                                except (ValueError, AttributeError) as e:
                                    logger.warning(
                                        f"Failed to parse head timestamp '{head_ts_str}': {e}"
                                    )

                    # Fallback to IB duration limits if no head timestamp
                    if not head_timestamp_used:
                        from ktrdr.config.ib_limits import IbLimitsRegistry

                        max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
                        start_dt = datetime.now() - max_duration
                        logger.info(
                            f"📅 {mode.upper()} mode: Using IB duration limit for default start: {start_dt}"
                        )
                else:
                    # Other modes: default to 30 days
                    start_dt = datetime.now() - timedelta(days=30)

            if end_date is not None:
                if isinstance(end_date, str):
                    end_dt: datetime = datetime.fromisoformat(end_date)
                else:
                    end_dt = end_date
            else:
                # Default: now
                end_dt = datetime.now()

            # Ensure timezone awareness
            if start_dt.tzinfo is None:
                from datetime import timezone

                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                from datetime import timezone

                end_dt = end_dt.replace(tzinfo=timezone.utc)

            # CRITICAL: Cap end_dt at current time (never load future data)
            current_time = datetime.now(tz=end_dt.tzinfo)
            if end_dt > current_time:
                logger.warning(
                    f"⚠️ Requested end_date {end_dt} is in the future. "
                    f"Capping at current time {current_time}"
                )
                end_dt = current_time

            # Step 2: Validate against head timestamp (with error handling)
            if progress_manager:
                progress_manager.start_step(
                    f"Validating date range for {symbol}",
                    step_number=2,
                    step_percentage=15.0,
                    step_end_percentage=20.0,
                )

            try:
                is_valid, error_msg, adjusted_start = (
                    await self._validate_request_against_head_timestamp(
                        symbol, timeframe, start_dt, end_dt
                    )
                )
                if not is_valid and adjusted_start:
                    logger.warning(
                        f"Adjusting start date from {start_dt} to {adjusted_start}"
                    )
                    start_dt = adjusted_start
            except Exception as e:
                logger.warning(
                    f"Head timestamp validation failed: {e}, continuing with requested dates"
                )

            # Step 3: Analyze gaps based on mode (with error handling)
            if progress_manager:
                progress_manager.start_step(
                    f"Analyzing data gaps for {symbol} ({mode} mode)",
                    step_number=3,
                    step_percentage=20.0,
                    step_end_percentage=25.0,
                )

            try:
                # Convert mode string to DataLoadingMode enum
                from ktrdr.data.loading_modes import DataLoadingMode  # type: ignore

                mode_enum = {
                    "tail": DataLoadingMode.TAIL,
                    "backfill": DataLoadingMode.BACKFILL,
                    "full": DataLoadingMode.FULL,
                }[mode]

                # Use analyze_gaps() - same method as DataManager
                # This correctly skips internal gap analysis for FULL/BACKFILL modes
                gaps = self.gap_analyzer.analyze_gaps(
                    existing_data=existing_data,
                    requested_start=start_dt,
                    requested_end=end_dt,
                    timeframe=timeframe,
                    symbol=symbol,
                    mode=mode_enum,
                )
                logger.info(
                    f"Gap analysis found {len(gaps)} gaps to fill in {mode} mode"
                )
            except Exception as e:
                logger.error(
                    f"Gap analysis failed: {e}, falling back to full range download"
                )
                gaps = [(start_dt, end_dt)]

            # Step 4: Create download segments (Task 4.4)
            if not gaps:
                logger.info("No gaps to fill, using cached data")
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "rows_downloaded": 0,
                    "cache_hit": cache_exists,
                    "gaps_filled": 0,
                }

            if progress_manager:
                progress_manager.start_step(
                    f"Creating {len(gaps)} download segments",
                    step_number=4,
                    step_percentage=25.0,
                    step_end_percentage=30.0,
                )

            # Create segments from gaps
            segments = self.segment_manager.create_segments(
                gaps=gaps,
                mode=mode_enum,
                timeframe=timeframe,
            )
            logger.info(f"Created {len(segments)} segments from {len(gaps)} gaps")

            # Prioritize segments based on mode
            segments = self.segment_manager.prioritize_segments(
                segments=segments,
                mode=mode_enum,
            )

            # Step 5: Download segments with resilience (Task 4.4)
            if progress_manager:
                progress_manager.start_step(
                    f"Downloading {len(segments)} segments from IB",
                    step_number=5,
                    step_percentage=30.0,
                    step_end_percentage=90.0,  # This is the longest step
                )

            # Create periodic save callback
            periodic_save_callback = self._create_periodic_save_callback(
                symbol, timeframe
            )

            # Get cancellation_token from ServiceOrchestrator context
            # (progress_manager already accessed at start of function)
            cancellation_token = self._current_cancellation_token

            # Use SegmentManager for resilient fetching with progress tracking
            successful_data, successful_count, failed_count = (
                await self.segment_manager.fetch_segments_with_resilience(
                    symbol=symbol,
                    timeframe=timeframe,
                    segments=segments,
                    external_provider=self.provider,
                    progress_manager=progress_manager,  # From ServiceOrchestrator context
                    cancellation_token=cancellation_token,  # From ServiceOrchestrator context
                    periodic_save_callback=periodic_save_callback,
                    periodic_save_minutes=self.periodic_save_interval,
                )
            )

            # Step 6: Merge and save final data
            if progress_manager:
                progress_manager.start_step(
                    f"Merging and saving {symbol} {timeframe} data",
                    step_number=6,
                    step_percentage=90.0,
                    step_end_percentage=100.0,
                )

            total_rows = 0
            if successful_data:
                # Combine all downloaded segments
                combined = pd.concat(successful_data, ignore_index=False)
                combined = combined[~combined.index.duplicated(keep="last")]
                combined = combined.sort_index()
                total_rows = len(combined)

                # Merge with existing cache if present
                if existing_data is not None and not existing_data.empty:
                    merged_data = pd.concat(
                        [existing_data, combined], ignore_index=False
                    )
                    merged_data = merged_data[
                        ~merged_data.index.duplicated(keep="last")
                    ]
                    merged_data = merged_data.sort_index()
                else:
                    merged_data = combined

                # Final save to cache
                self.repository.save_to_cache(symbol, timeframe, merged_data)

            logger.info(
                f"Downloaded {total_rows} rows across {successful_count}/{len(segments)} segments "
                f"({failed_count} failed)"
            )

            # Return summary
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "rows_downloaded": total_rows,
                "cache_hit": cache_exists,
                "gaps_filled": len(gaps),
                "mode": mode,
            }

        # Use ServiceOrchestrator's start_managed_operation for background execution
        return await self.start_managed_operation(
            operation_name=f"Download {symbol} {timeframe} ({mode} mode)",
            operation_type="data_load",
            operation_func=_download_operation,
            metadata={
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
                "mode": mode,
            },
            total_steps=7,  # 0:validate_symbol, 1:cache, 2:validate_dates, 3:gaps, 4:segments, 5:download, 6:save
        )

    def __repr__(self) -> str:
        """
        String representation for debugging.

        Returns:
            Informative string representation
        """
        return (
            f"DataAcquisitionService("
            f"repository={type(self.repository).__name__}, "
            f"provider={type(self.provider).__name__}, "
            f"mode={'host_service' if self.is_using_host_service() else 'local'})"
        )

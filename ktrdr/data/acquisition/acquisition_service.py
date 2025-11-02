"""
Data Acquisition Service.

Orchestrates external data acquisition from providers (IB) with progress tracking,
gap analysis, and intelligent segmentation.

This service composes DataRepository for cache operations and uses IbDataProvider
for external data fetching via HTTP.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Union

from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator
from ktrdr.data.acquisition.gap_analyzer import GapAnalyzer
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider
from ktrdr.data.components.symbol_cache import SymbolCache
from ktrdr.data.repository import DataRepository
from ktrdr.errors.exceptions import DataNotFoundError

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

    def __init__(
        self,
        repository: Optional[DataRepository] = None,
        provider: Optional[IbDataProvider] = None,
        gap_analyzer: Optional[GapAnalyzer] = None,
        symbol_cache: Optional[SymbolCache] = None,
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

        logger.info(
            f"DataAcquisitionService initialized "
            f"(repository: {type(self.repository).__name__}, "
            f"provider: {type(self.provider).__name__}, "
            f"gap_analyzer: {type(self.gap_analyzer).__name__}, "
            f"symbol_cache: {type(self.symbol_cache).__name__})"
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
            provider = IbDataProvider()

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
            # Step 1: Check cache
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
            if start_date is not None:
                if isinstance(start_date, str):
                    start_dt: datetime = datetime.fromisoformat(start_date)
                else:
                    start_dt = start_date
            else:
                # Default: last 30 days
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

            # Step 2: Validate against head timestamp (with error handling)
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
            try:
                # Convert mode string to DataLoadingMode enum
                from ktrdr.data.data_loading_mode import DataLoadingMode  # type: ignore

                mode_enum = {
                    "tail": DataLoadingMode.TAIL,
                    "backfill": DataLoadingMode.BACKFILL,
                    "full": DataLoadingMode.FULL,
                }[mode]

                gaps = self.gap_analyzer.analyze_gaps_by_mode(
                    mode=mode_enum,
                    existing_data=existing_data,
                    requested_start=start_dt,
                    requested_end=end_dt,
                    timeframe=timeframe,
                    symbol=symbol,
                )
                logger.info(
                    f"Gap analysis found {len(gaps)} gaps to fill in {mode} mode"
                )
            except Exception as e:
                logger.error(
                    f"Gap analysis failed: {e}, falling back to full range download"
                )
                gaps = [(start_dt, end_dt)]

            # Step 4: Download missing data
            if not gaps:
                logger.info("No gaps to fill, using cached data")
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "rows_downloaded": 0,
                    "cache_hit": cache_exists,
                    "gaps_filled": 0,
                }

            # Download each gap
            total_rows = 0
            import pandas as pd

            for gap_start, gap_end in gaps:
                logger.info(f"Downloading gap: {gap_start} to {gap_end}")
                gap_data = await self.provider.fetch_historical_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=gap_start,
                    end=gap_end,
                )
                total_rows += len(gap_data)

                # Merge with existing and save (simple concat + drop duplicates)
                if existing_data is not None and not existing_data.empty:
                    merged_data = pd.concat([existing_data, gap_data])
                    merged_data = merged_data[
                        ~merged_data.index.duplicated(keep="last")
                    ]
                    merged_data = merged_data.sort_index()
                else:
                    merged_data = gap_data

                # Save to cache
                self.repository.save_to_cache(symbol, timeframe, merged_data)
                existing_data = merged_data

            logger.info(f"Downloaded {total_rows} rows across {len(gaps)} gaps")

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
            total_steps=5,  # Check cache, validate head, analyze gaps, download, save
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

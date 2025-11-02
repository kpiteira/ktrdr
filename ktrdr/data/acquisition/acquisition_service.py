"""
Data Acquisition Service.

Orchestrates external data acquisition from providers (IB) with progress tracking,
gap analysis, and intelligent segmentation.

This service composes DataRepository for cache operations and uses IbDataProvider
for external data fetching via HTTP.
"""

import logging
from datetime import datetime
from typing import Any, Optional, Union

from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider
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
    ) -> None:
        """
        Initialize data acquisition service.

        Args:
            repository: Optional DataRepository instance for cache operations.
                       If None, creates default instance.
            provider: Optional IbDataProvider instance for external data.
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

        logger.info(
            f"DataAcquisitionService initialized "
            f"(repository: {type(self.repository).__name__}, "
            f"provider: {type(self.provider).__name__})"
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

    async def download_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
    ) -> dict[str, Any]:
        """
        Download data from external provider (IB).

        Basic download flow:
        1. Check cache for existing data
        2. Download from provider (IB)
        3. Save to cache

        This is a simplified version. Gap analysis and segmentation
        will be added in future tasks.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EURUSD')
            timeframe: Data timeframe (e.g., '1h', '1d')
            start_date: Optional start date for data range
            end_date: Optional end date for data range

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
            f"(start: {start_date}, end: {end_date})"
        )

        # Define the download operation function
        async def _download_operation() -> dict[str, Any]:
            """Internal download operation with cache-check → download → save flow."""
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

            # Step 2: Download from provider
            # For now, always download (gap analysis comes in later tasks)
            logger.info(f"Downloading {symbol} {timeframe} from provider")

            # Convert dates if needed and handle defaults
            if start_date is not None:
                if isinstance(start_date, str):
                    start_dt: datetime = datetime.fromisoformat(start_date)
                else:
                    start_dt = start_date
            else:
                # Default: last 30 days
                from datetime import timedelta

                start_dt = datetime.now() - timedelta(days=30)

            if end_date is not None:
                if isinstance(end_date, str):
                    end_dt: datetime = datetime.fromisoformat(end_date)
                else:
                    end_dt = end_date
            else:
                # Default: now
                end_dt = datetime.now()

            # Fetch from provider (uses 'start' and 'end', not 'start_date' and 'end_date')
            downloaded_data = await self.provider.fetch_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start=start_dt,
                end=end_dt,
            )

            logger.info(
                f"Downloaded {len(downloaded_data)} rows for {symbol} {timeframe}"
            )

            # Step 3: Save to cache
            logger.debug(f"Saving data to cache for {symbol} {timeframe}")
            self.repository.save_to_cache(symbol, timeframe, downloaded_data)
            logger.info(f"Data saved to cache for {symbol} {timeframe}")

            # Return summary
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "rows_downloaded": len(downloaded_data),
                "cache_hit": cache_exists,
            }

        # Use ServiceOrchestrator's start_managed_operation for background execution
        return await self.start_managed_operation(
            operation_name=f"Download {symbol} {timeframe}",
            operation_type="data_load",
            operation_func=_download_operation,
            metadata={
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
            },
            total_steps=3,  # Check cache, download, save
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

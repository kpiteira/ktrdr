"""
Data Acquisition Service.

Orchestrates external data acquisition from providers (IB) with progress tracking,
gap analysis, and intelligent segmentation.

This service composes DataRepository for cache operations and uses IbDataProvider
for external data fetching via HTTP.
"""

import logging
from typing import Optional

from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider
from ktrdr.data.repository import DataRepository

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

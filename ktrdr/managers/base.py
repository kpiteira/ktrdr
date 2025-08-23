"""
ServiceOrchestrator base class for unified service management patterns.

This module provides the ServiceOrchestrator abstract base class that standardizes
environment-based configuration, adapter initialization, and common management
patterns across all service managers (Data, Training, Backtesting, etc.).
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar

from ktrdr.logging import get_logger

logger = get_logger(__name__)

# Generic type for the adapter
T = TypeVar("T")


class ServiceOrchestrator(ABC):
    """
    Base class for all service managers (Data, Training, Backtesting, etc.).

    This class orchestrates complex operations across multiple backend services,
    providing unified environment-based configuration, adapter initialization,
    and common management patterns.

    Key responsibilities:
    - Environment-based adapter configuration (host service vs local)
    - Standardized configuration interface across all managers
    - Common patterns for health checks and statistics
    - Unified error handling and logging patterns

    Subclasses must implement:
    - _initialize_adapter(): Create and configure the appropriate adapter
    - _get_service_name(): Return human-readable service name for logging
    - _get_default_host_url(): Return default host service URL
    - _get_env_var_prefix(): Return environment variable prefix (e.g., 'IB', 'TRAINING')
    """

    def __init__(self) -> None:
        """
        Initialize service orchestrator with environment-based configuration.

        This constructor automatically initializes the appropriate adapter based
        on environment variables specific to each service type.
        """
        logger.debug(f"Initializing {self._get_service_name()} orchestrator")
        self.adapter: T = self._initialize_adapter()
        logger.info(
            f"{self._get_service_name()} orchestrator initialized "
            f"(mode: {'host_service' if self.is_using_host_service() else 'local'})"
        )

    @abstractmethod
    def _initialize_adapter(self) -> T:
        """
        Initialize the appropriate adapter based on environment variables.

        This method should:
        1. Check environment variables for host service configuration
        2. Create and configure the adapter with appropriate settings
        3. Return the initialized adapter instance

        Returns:
            Initialized adapter instance specific to the service type
        """
        pass

    @abstractmethod
    def _get_service_name(self) -> str:
        """
        Get the human-readable service name for logging and configuration.

        Examples:
        - "Data/IB"
        - "Training"
        - "Backtesting"

        Returns:
            Service name string for display and logging
        """
        pass

    @abstractmethod
    def _get_default_host_url(self) -> str:
        """
        Get the default host service URL for this service type.

        Examples:
        - "http://localhost:8001" for IB Host Service
        - "http://localhost:8002" for Training Host Service

        Returns:
            Default URL string for host service
        """
        pass

    @abstractmethod
    def _get_env_var_prefix(self) -> str:
        """
        Get environment variable prefix for this service type.

        Used to construct environment variable names:
        - USE_{PREFIX}_HOST_SERVICE
        - {PREFIX}_HOST_SERVICE_URL

        Examples:
        - "IB" -> USE_IB_HOST_SERVICE, IB_HOST_SERVICE_URL
        - "TRAINING" -> USE_TRAINING_HOST_SERVICE, TRAINING_HOST_SERVICE_URL

        Returns:
            Environment variable prefix string (uppercase)
        """
        pass

    def is_using_host_service(self) -> bool:
        """
        Check if orchestrator is configured to use host service.

        Returns:
            True if using host service, False if using local/direct connection
        """
        return getattr(self.adapter, "use_host_service", False)

    def get_host_service_url(self) -> Optional[str]:
        """
        Get host service URL if using host service.

        Returns:
            Host service URL if using host service, None if using local mode
        """
        if self.is_using_host_service():
            return getattr(self.adapter, "host_service_url", None)
        return None

    def get_configuration_info(self) -> Dict[str, Any]:
        """
        Get current configuration information for diagnostics and debugging.

        Returns comprehensive configuration details including:
        - Service identification
        - Operating mode (host_service vs local)
        - Host service URL (if applicable)
        - Environment variables
        - Adapter statistics

        Returns:
            Dictionary with complete configuration information
        """
        prefix = self._get_env_var_prefix()
        use_env_var = f"USE_{prefix}_HOST_SERVICE"
        url_env_var = f"{prefix}_HOST_SERVICE_URL"

        return {
            "service": self._get_service_name(),
            "mode": "host_service" if self.is_using_host_service() else "local",
            "host_service_url": self.get_host_service_url(),
            "environment_variables": {
                use_env_var: os.getenv(use_env_var),
                url_env_var: os.getenv(url_env_var),
            },
            "adapter_info": {
                "type": type(self.adapter).__name__,
                "statistics": self.get_adapter_statistics(),
            },
        }

    def get_adapter_statistics(self) -> Dict[str, Any]:
        """
        Get adapter usage statistics if available.

        Returns:
            Dictionary with adapter statistics, or indication if not available
        """
        if hasattr(self.adapter, "get_statistics"):
            return self.adapter.get_statistics()
        elif hasattr(self.adapter, "requests_made"):
            # Basic statistics for adapters with simple counters
            return {
                "requests_made": getattr(self.adapter, "requests_made", 0),
                "errors_encountered": getattr(self.adapter, "errors_encountered", 0),
                "last_request_time": getattr(self.adapter, "last_request_time", None),
            }
        else:
            return {"statistics": "not_available"}

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the orchestrator and its adapter.

        This default implementation checks adapter health if available.
        Subclasses can override to add service-specific health checks.

        Returns:
            Dictionary with health status information
        """
        orchestrator_info = {
            "orchestrator": "healthy",
            "service": self._get_service_name(),
            "mode": "host_service" if self.is_using_host_service() else "local",
        }

        if hasattr(self.adapter, "health_check"):
            try:
                adapter_health = await self.adapter.health_check()
                return {**orchestrator_info, "adapter": adapter_health}
            except Exception as e:
                logger.warning(f"Adapter health check failed: {e}")
                return {
                    **orchestrator_info,
                    "adapter": {"status": "error", "error": str(e)},
                }
        else:
            return {
                **orchestrator_info,
                "adapter": {"status": "unknown", "health_check": "not_available"},
            }

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"service={self._get_service_name()}, "
            f"mode={'host_service' if self.is_using_host_service() else 'local'}, "
            f"adapter={type(self.adapter).__name__})"
        )

"""
IB (Interactive Brokers) service for the KTRDR API - UPDATED FOR NEW ARCHITECTURE.

This module provides service layer functionality for IB operations using the new
simplified IB architecture with dedicated threads and persistent event loops.
"""

import time
from datetime import datetime, timezone
from typing import Any, Optional

from ktrdr import get_logger
from ktrdr.api.models.ib import (
    ConnectionInfo,
    ConnectionMetrics,
    DataFetchMetrics,
    DataRangesResponse,
    IbConfigInfo,
    IbConfigUpdateRequest,
    IbConfigUpdateResponse,
    IbHealthStatus,
    IbStatusResponse,
)
from ktrdr.config.settings import clear_settings_cache, get_ib_settings
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider

logger = get_logger(__name__)


class IbService:
    """
    Service for IB infrastructure operations only.

    This service provides methods for:
    - IB connection status and health monitoring
    - IB configuration management
    - IB data range discovery
    - IB connection cleanup

    Note: Data loading operations are handled by DataManager through DataService.
    IbService is now a "dumb" service focused only on IB infrastructure.
    """

    def __init__(self, data_loader: Optional[Any] = None):
        """
        Initialize the IB service for IB infrastructure operations only.

        Args:
            data_loader: Optional IbDataLoader instance for dependency injection.

        Note:
            IbService now focuses only on IB infrastructure operations (status, health,
            config, ranges, cleanup). Data loading operations are handled by DataManager
            through the DataService.
        """

        # For backward compatibility, store data_loader if provided
        # But main operations now use unified components directly
        self.data_loader = data_loader
        self.data_dir = self._get_data_dir()

        logger.info("IbService initialized (using unified IB components)")

    def _get_data_dir(self) -> str:
        """Get data directory from configuration."""
        try:
            from ktrdr.config.loader import ConfigLoader

            config_loader = ConfigLoader()
            config = config_loader.load_from_env(default_path="config/settings.yaml")
            if hasattr(config, "data") and hasattr(config.data, "directory"):
                return config.data.directory
            return "data"
        except Exception:
            return "data"

    async def get_status(self) -> IbStatusResponse:
        """
        Get comprehensive IB status information with enhanced resilience monitoring.

        Returns:
            IbStatusResponse with connection info, metrics, and availability
        """
        # Import dependencies at top of method
        import os
        from datetime import datetime, timezone
        from pathlib import Path

        from ktrdr.config.loader import ConfigLoader
        from ktrdr.config.models import IbHostServiceConfig, KtrdrConfig
        from ktrdr.data.acquisition.ib_data_provider import IbDataProvider

        # Load host service configuration to determine connection method
        try:
            # Load host service configuration
            try:
                config_loader = ConfigLoader()
                config_path = Path("config/settings.yaml")
                if config_path.exists():
                    main_config = config_loader.load(config_path, KtrdrConfig)
                    host_service_config = main_config.ib_host_service
                else:
                    host_service_config = IbHostServiceConfig(
                        enabled=False, url="http://localhost:5001"
                    )

                # Check environment variable override (same logic as DataManager)
                env_enabled = os.getenv("USE_IB_HOST_SERVICE", "").lower()
                if env_enabled in ("true", "1", "yes"):
                    host_service_config.enabled = True
                    # Use environment URL if provided
                    env_url = os.getenv("IB_HOST_SERVICE_URL")
                    if env_url:
                        host_service_config.url = env_url
                elif env_enabled in ("false", "0", "no"):
                    host_service_config.enabled = False

                logger.info(
                    f"🔍 IB status check: host_service.enabled={host_service_config.enabled}, url={host_service_config.url}"
                )

            except Exception as e:
                logger.warning(f"Failed to load host service config: {e}")
                host_service_config = IbHostServiceConfig(
                    enabled=False, url="http://localhost:5001"
                )

            if host_service_config.enabled:
                # Use host service for status
                # Create IbDataProvider for host service communication
                adapter = IbDataProvider(
                    host_service_url=host_service_config.url,
                )

                # Get health check from host service
                health = await adapter.health_check()

                # Convert health check to IbStatusResponse format
                ib_available = health.get("healthy", False)
                connected = health.get("connected", False)

                logger.info(
                    f"🔍 IB status via host service: healthy={ib_available}, connected={connected}"
                )

                # Create response based on host service health
                return IbStatusResponse(
                    connection=ConnectionInfo(
                        connected=connected,
                        host=host_service_config.url,
                        port=5001,  # Host service port
                        client_id=0,
                        connection_time=(
                            datetime.now(timezone.utc) if connected else None
                        ),
                    ),
                    connection_metrics=ConnectionMetrics(
                        total_connections=1 if connected else 0,
                        failed_connections=health.get("error_count", 0),
                        last_connect_time=None,
                        last_disconnect_time=None,
                        uptime_seconds=None,
                    ),
                    data_metrics=DataFetchMetrics(
                        total_requests=health.get("provider_info", {}).get(
                            "requests_made", 0
                        ),
                        successful_requests=0,
                        failed_requests=health.get("error_count", 0),
                        total_bars_fetched=0,
                        success_rate=1.0 if connected else 0.0,
                    ),
                    ib_available=ib_available,
                )
            else:
                # Host service not enabled - return unavailable status
                logger.warning(
                    "IB host service not enabled - IB functionality unavailable"
                )
                return IbStatusResponse(
                    connection=ConnectionInfo(
                        connected=False,
                        host="",
                        port=0,
                        client_id=0,
                        connection_time=None,
                    ),
                    connection_metrics=ConnectionMetrics(
                        total_connections=0,
                        failed_connections=0,
                        last_connect_time=None,
                        last_disconnect_time=None,
                        uptime_seconds=None,
                    ),
                    data_metrics=DataFetchMetrics(
                        total_requests=0,
                        successful_requests=0,
                        failed_requests=0,
                        total_bars_fetched=0,
                        success_rate=0.0,
                    ),
                    ib_available=False,
                )

        except Exception as e:
            logger.warning(f"IB status check failed: {e}")
            return IbStatusResponse(
                connection=ConnectionInfo(
                    connected=False, host="", port=0, client_id=0, connection_time=None
                ),
                connection_metrics=ConnectionMetrics(
                    total_connections=0,
                    failed_connections=0,
                    last_connect_time=None,
                    last_disconnect_time=None,
                    uptime_seconds=None,
                ),
                data_metrics=DataFetchMetrics(
                    total_requests=0,
                    successful_requests=0,
                    failed_requests=0,
                    total_bars_fetched=0,
                    success_rate=0.0,
                ),
                ib_available=False,
            )

    async def get_health(self) -> IbHealthStatus:
        """
        Perform health check on IB connection via host service.

        Returns:
            IbHealthStatus indicating overall health
        """
        try:
            # Use IbDataProvider to check health via host service
            provider = IbDataProvider()
            health = await provider.health_check()

            # Extract health status from host service response
            healthy = health.get("healthy", False)
            connected = health.get("connected", False)

            return IbHealthStatus(
                healthy=healthy,
                connection_ok=connected,
                data_fetching_ok=healthy,
                last_successful_request=None,  # Host service doesn't track this yet
                error_message=None if healthy else "IB host service reports unhealthy",
            )

        except Exception as e:
            logger.warning(f"IB health check via host service failed: {e}")
            return IbHealthStatus(
                healthy=False,
                connection_ok=False,
                data_fetching_ok=False,
                last_successful_request=None,
                error_message=f"Health check failed: {str(e)}",
            )

    async def get_connection_resilience_status(self) -> dict[str, Any]:
        """
        Get connection resilience status via host service.

        Returns:
            Dictionary with basic resilience metrics from host service
        """
        logger.info("🔍 Getting resilience status from IB host service")

        try:
            # Get health status from host service
            provider = IbDataProvider()
            health = await provider.health_check()

            resilience_status = {
                "architecture": "host_service",
                "host_service_health": {
                    "healthy": health.get("healthy", False),
                    "connected": health.get("connected", False),
                    "provider_info": health.get("provider_info", {}),
                },
                "features": {
                    "http_communication": "enabled",
                    "rate_limiting": "handled_by_host_service",
                    "connection_management": "handled_by_host_service",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info("✅ Resilience status from host service retrieved successfully")
            return resilience_status

        except Exception as e:
            logger.error(f"❌ Resilience status check failed: {e}")
            return {
                "error": str(e),
                "architecture": "host_service",
                "status": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def get_config(self) -> IbConfigInfo:
        """
        Get IB configuration information.

        Returns:
            IbConfigInfo with current configuration
        """
        try:
            # Get configuration from unified settings system
            config = get_ib_settings()

            return IbConfigInfo(
                host=config.host,
                port=config.port,
                client_id_range={
                    "min": 1,
                    "max": 999,
                },
                timeout=30,  # Default timeout
                readonly=True,  # Connection pool uses read-only connections
                rate_limit={
                    "max_requests": 60,  # IB limit
                    "period_seconds": 600,  # 10 minutes
                    "pacing_delay": 0.6,
                },
            )

        except Exception as e:
            logger.warning(f"Failed to get IB config from connection pool: {e}")
            # Return default configuration
            return IbConfigInfo(
                host="127.0.0.1",
                port=7497,
                client_id_range={"min": 11, "max": 999},
                timeout=30,
                readonly=True,
                rate_limit={
                    "max_requests": 60,
                    "period_seconds": 600,
                    "pacing_delay": 0.6,
                },
            )

    async def cleanup_connections(self) -> dict[str, Any]:
        """
        Connection cleanup is handled by the IB host service.

        The backend no longer manages IB connections directly.
        Connection lifecycle is managed by the host service.

        Returns:
            Dictionary indicating cleanup is not needed
        """
        logger.info(
            "Connection cleanup not needed - connections managed by IB host service"
        )

        return {
            "success": True,
            "message": "Connection management delegated to IB host service",
            "note": "IB connections are managed by the host service and cleaned up automatically",
            "architecture": "host_service",
        }

    async def update_config(
        self, request: IbConfigUpdateRequest
    ) -> IbConfigUpdateResponse:
        """
        Update IB configuration dynamically.

        This method updates the IB configuration and determines if reconnection
        is required for the changes to take effect.

        Args:
            request: Configuration update request

        Returns:
            IbConfigUpdateResponse with previous and new configuration
        """
        # Get current configuration
        previous_config = await self.get_config()

        # Track if we need to reconnect
        reconnect_required = False

        # Update configuration values via environment variables
        if request.port is not None:
            # Port change requires reconnection
            reconnect_required = True
            import os

            os.environ["KTRDR_IB_PORT"] = str(request.port)
            logger.info(f"Updated KTRDR_IB_PORT to {request.port}")

        if request.host is not None:
            # Host change requires reconnection
            reconnect_required = True
            import os

            os.environ["KTRDR_IB_HOST"] = request.host
            logger.info(f"Updated KTRDR_IB_HOST to {request.host}")

        if request.client_id is not None:
            # Client ID changes are managed by the client ID registry
            logger.warning(
                "Client ID updates are managed by IbClientIdRegistry - ignoring direct client_id change"
            )

        # If reconnection is required, cleanup existing connections
        if reconnect_required:
            logger.info(
                "Configuration change requires reconnection - cleaning up connection pool"
            )

            try:
                # Cleanup all existing connections
                cleanup_result = await self.cleanup_connections()
                logger.info(f"Connection cleanup result: {cleanup_result}")

                # Clear settings cache to pick up new environment variables
                clear_settings_cache()
                logger.info("Cleared settings cache for new environment variables")

            except Exception as e:
                logger.error(f"Error during configuration update cleanup: {e}")

        # Get new configuration
        new_config = await self.get_config()

        return IbConfigUpdateResponse(
            previous_config=previous_config,
            new_config=new_config,
            reconnect_required=reconnect_required,
        )

    async def get_data_ranges(
        self, symbols: list[str], timeframes: list[str]
    ) -> DataRangesResponse:
        """
        Get historical data ranges for multiple symbols and timeframes.

        NOTE: This method needs to be implemented for new architecture.

        Args:
            symbols: List of symbols to check
            timeframes: List of timeframes to check (e.g., ['1d', '1h'])

        Returns:
            DataRangesResponse with range information
        """
        logger.warning("get_data_ranges not yet implemented for new architecture")

        # Return empty response indicating new architecture implementation needed
        return DataRangesResponse(
            symbols=[],
            requested_timeframes=timeframes,
            cache_stats={
                "error": "Data ranges discovery not yet implemented for new architecture",
                "cached_ranges": 0,
                "fresh_lookups": 0,
            },
        )

    async def discover_symbol(
        self, symbol: str, force_refresh: bool = False
    ) -> Optional[dict[str, Any]]:
        """
        Discover symbol information using unified IB symbol validator.

        Args:
            symbol: Symbol to discover (e.g., 'AAPL', 'EURUSD')
            force_refresh: Force re-validation even if cached

        Returns:
            Dictionary with symbol information or None if not found
        """
        try:
            # Use IB data adapter with host service support
            from pathlib import Path

            from ktrdr.config.loader import ConfigLoader
            from ktrdr.config.models import IbHostServiceConfig, KtrdrConfig

            # Load host service configuration
            try:
                config_loader = ConfigLoader()
                config_path = Path("config/settings.yaml")
                if config_path.exists():
                    main_config = config_loader.load(config_path, KtrdrConfig)
                    host_service_config = main_config.ib_host_service
                else:
                    host_service_config = IbHostServiceConfig(
                        enabled=False, url="http://localhost:5001"
                    )
            except Exception:
                host_service_config = IbHostServiceConfig(
                    enabled=False, url="http://localhost:5001"
                )

            # Initialize provider for host service communication
            adapter = IbDataProvider(
                host_service_url=host_service_config.url,
            )

            # Validate symbol using new architecture
            is_valid = await adapter.validate_symbol(symbol)

            if not is_valid:
                return None

            # For now, return simplified symbol info since the new architecture
            # doesn't have all the detailed contract info methods yet
            return {
                "symbol": symbol,
                "instrument_type": "stock",  # Default to stock for now
                "exchange": "SMART",
                "currency": "USD",
                "description": f"{symbol} - Symbol validated via new IB architecture",
                "discovered_at": time.time(),
                "last_validated": time.time(),
                "validation_count": 1,
                "is_active": True,
                "head_timestamp": None,  # Can be added later if needed
                "trading_hours": None,  # Can be added later if needed
            }

        except Exception as e:
            logger.error(f"Symbol discovery failed for {symbol}: {e}")
            return None

    def get_discovered_symbols(
        self, instrument_type: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Get all discovered symbols from the cache.

        NOTE: This method needs to be implemented for new architecture.

        Args:
            instrument_type: Filter by instrument type (optional)

        Returns:
            List of discovered symbol information
        """
        logger.warning(
            "get_discovered_symbols not yet implemented for new architecture"
        )
        return []

    def get_symbol_discovery_stats(self) -> dict[str, Any]:
        """
        Get symbol discovery cache statistics.

        NOTE: This method needs to be implemented for new architecture.

        Returns:
            Dictionary with discovery statistics
        """
        logger.warning(
            "get_symbol_discovery_stats not yet implemented for new architecture"
        )
        return {}

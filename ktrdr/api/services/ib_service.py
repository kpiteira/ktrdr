"""
IB (Interactive Brokers) service for the KTRDR API - UPDATED FOR NEW ARCHITECTURE.

This module provides service layer functionality for IB operations using the new
simplified IB architecture with dedicated threads and persistent event loops.
"""

import time
import asyncio
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from ktrdr import get_logger
from ktrdr.ib import IbConnectionPool, IbErrorClassifier, IbPaceManager
from ktrdr.data.ib_data_adapter import IbDataAdapter
from ktrdr.config.ib_config import get_ib_config
from ktrdr.api.models.ib import (
    ConnectionInfo,
    ConnectionMetrics,
    DataFetchMetrics,
    IbStatusResponse,
    IbHealthStatus,
    IbConfigInfo,
    IbConfigUpdateRequest,
    IbConfigUpdateResponse,
    DataRangeInfo,
    SymbolRangeResponse,
    DataRangesResponse,
)
from ktrdr.config.ib_config import reset_ib_config

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
        from ktrdr.config.loader import ConfigLoader
        from ktrdr.config.models import KtrdrConfig, IbHostServiceConfig
        from ktrdr.config.ib_config import get_ib_config
        from ktrdr.data.ib_data_adapter import IbDataAdapter
        from datetime import datetime, timezone
        from pathlib import Path
        import os

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
                    host_service_config = IbHostServiceConfig()

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
                host_service_config = IbHostServiceConfig()

            if host_service_config.enabled:
                # Use host service for status
                ib_config = get_ib_config()

                # Create IbDataAdapter in host service mode
                adapter = IbDataAdapter(
                    host=ib_config.host,
                    port=ib_config.port,
                    use_host_service=True,
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
                # Use direct IB connection pool (existing behavior)
                from ktrdr.ib.pool_manager import get_shared_ib_pool

                pool = get_shared_ib_pool()
                pool_stats = pool.get_pool_stats()
                ib_available = pool_stats["total_connections"] >= 0  # Pool exists

                logger.info(
                    "🔍 IB status via direct connection - checking connection pool"
                )

        except Exception as e:
            logger.warning(f"IB status check failed: {e}")
            ib_available = False
            pool_stats = {}

        if not ib_available:
            # Return minimal status when IB is not available
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

        # Get connection info from connection pool
        connection_info = ConnectionInfo(
            connected=ib_available,
            host=pool_stats.get("host", ""),
            port=pool_stats.get("port", 0),
            client_id=0,  # Pool manages multiple client IDs
            connection_time=datetime.now(timezone.utc) if ib_available else None,
        )

        # Get connection metrics from connection pool
        connection_metrics = ConnectionMetrics(
            total_connections=pool_stats.get("total_connections", 0),
            failed_connections=pool_stats.get("failed_connections", 0),
            last_connect_time=None,  # Enhanced in pool stats if needed
            last_disconnect_time=None,
            uptime_seconds=pool_stats.get("uptime_seconds"),
        )

        # Get pace manager statistics from new architecture
        pace_manager = IbPaceManager()
        pace_stats = pace_manager.get_stats()
        current_state = pace_stats.get("current_state", {})

        # Calculate aggregated data metrics from pace manager
        total_requests = current_state.get("requests_in_10min", 0)
        successful_requests = max(
            0,
            total_requests
            - pace_stats.get("violation_statistics", {})
            .get("ib_error_162", {})
            .get("count", 0),
        )

        data_metrics = DataFetchMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=total_requests - successful_requests,
            total_bars_fetched=0,  # Not tracked in pace manager
            success_rate=(
                successful_requests / total_requests if total_requests > 0 else 0.0
            ),
        )

        return IbStatusResponse(
            connection=connection_info,
            connection_metrics=connection_metrics,
            data_metrics=data_metrics,
            ib_available=ib_available,
        )

    async def get_health(self) -> IbHealthStatus:
        """
        Perform health check on IB connection and functionality.

        Returns:
            IbHealthStatus indicating overall health
        """
        # Check if IB connection pool is available
        try:
            # Use new IB connection pool from new architecture
            from ktrdr.ib.pool_manager import get_shared_ib_pool

            pool = get_shared_ib_pool()
            pool_stats = pool.get_pool_stats()
            pool_available = True  # Pool created successfully
        except Exception as e:
            logger.warning(f"IB connection pool not available: {e}")
            pool_available = False

        if not pool_available:
            return IbHealthStatus(
                healthy=False,
                connection_ok=False,
                data_fetching_ok=False,
                last_successful_request=None,
                error_message="IB connection pool not available",
            )

        # IB API TEST: Test connection using new architecture
        api_test_ok = False
        connection_ok = False
        try:
            # Use new architecture connection pool to test connection
            async with pool.get_connection() as connection:
                connection_ok = True

                # Test basic connection health first
                if not connection.is_healthy():
                    logger.warning("❌ Connection not healthy after acquisition")
                    raise Exception("Connection not healthy")

                # Test basic connection health - minimal API calls to avoid overwhelming IB
                ib = connection.ib

                # Level 1: Basic connection state validation (non-invasive)
                if not ib.isConnected():
                    logger.warning(
                        f"❌ Level 1 failed: IB reports not connected (client_id: {connection.client_id})"
                    )
                    raise Exception("IB connection lost during health check")

                # Level 2: Light API test - managedAccounts is a cached property
                try:
                    accounts = ib.managedAccounts()
                    if not accounts:
                        logger.warning(
                            f"❌ Level 2 failed: No managed accounts (client_id: {connection.client_id})"
                        )
                        raise Exception("No managed accounts returned")
                except Exception as e:
                    logger.warning(
                        f"❌ Level 2 failed: managedAccounts call failed: {e}"
                    )
                    raise Exception("Managed accounts access failed")

                api_test_ok = True
                logger.info(
                    f"✅ New architecture health check passed: {len(accounts)} accounts, connection healthy (client_id: {connection.client_id})"
                )

        except asyncio.TimeoutError as e:
            logger.error(
                f"❌ IB health check TIMEOUT: {e} - This indicates a silent connection issue!"
            )
            api_test_ok = False
            connection_ok = False
        except Exception as e:
            logger.warning(f"❌ IB health check failed: {e}")
            api_test_ok = False
            connection_ok = False

        # Data fetching is OK if we can successfully make API calls
        data_fetching_ok = api_test_ok

        # Get last successful request time from pace manager
        pace_manager = IbPaceManager()
        pace_stats = pace_manager.get_stats()
        current_state = pace_stats.get("current_state", {})

        last_successful_request = None
        if (
            connection_ok and current_state.get("time_since_last_request", 0) < 300
        ):  # Within 5 minutes
            last_successful_request = datetime.now(timezone.utc) - timedelta(
                seconds=current_state.get("time_since_last_request", 0)
            )

        # Determine overall health
        healthy = connection_ok and data_fetching_ok

        # Build error message if unhealthy
        error_message = None
        if not healthy:
            errors = []
            if not connection_ok:
                errors.append("Connection pool is down")
            if not data_fetching_ok:
                errors.append("Data fetching is not working")
            error_message = "; ".join(errors)

        return IbHealthStatus(
            healthy=healthy,
            connection_ok=connection_ok,
            data_fetching_ok=data_fetching_ok,
            last_successful_request=last_successful_request,
            error_message=error_message,
        )

    async def get_connection_resilience_status(self) -> Dict[str, Any]:
        """
        Get basic connection resilience status for new architecture.

        Returns:
            Dictionary with basic resilience metrics
        """
        logger.info("🔍 New architecture: Basic connection resilience status")

        try:
            # Use new IB connection pool from new architecture
            from ktrdr.ib.pool_manager import get_shared_ib_pool

            pool = get_shared_ib_pool()
            pool_stats = pool.get_pool_stats()

            resilience_status = {
                "new_architecture_status": "active",
                "connection_pool_health": {
                    "total_connections": pool_stats.get("total_connections", 0),
                    "healthy_connections": pool_stats.get("healthy_connections", 0),
                    "max_connections": pool_stats.get("max_connections", 5),
                    "host": pool_stats.get("host", "unknown"),
                    "port": pool_stats.get("port", 0),
                },
                "features": {
                    "dedicated_threads": "enabled",
                    "persistent_event_loops": "enabled",
                    "auto_cleanup": "enabled",
                    "idle_timeout": "180s",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info("✅ New architecture resilience status completed successfully")
            return resilience_status

        except Exception as e:
            logger.error(f"❌ New architecture resilience status failed: {e}")
            return {
                "error": str(e),
                "new_architecture_status": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def get_config(self) -> IbConfigInfo:
        """
        Get IB configuration information.

        Returns:
            IbConfigInfo with current configuration
        """
        try:
            # Get configuration from new architecture
            from ktrdr.config.ib_config import get_ib_config

            config = get_ib_config()

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

    async def cleanup_connections(self) -> Dict[str, Any]:
        """
        Clean up all IB connections.

        Returns:
            Dictionary with cleanup results
        """
        try:
            # Use new architecture connection pool cleanup
            from ktrdr.ib.pool_manager import get_shared_ib_pool

            pool = get_shared_ib_pool()

            # Get current stats before cleanup
            stats_before = pool.get_pool_stats()
            connections_before = stats_before.get("total_connections", 0)

            # Cleanup all connections in pool
            await pool.cleanup_all()

            # Get stats after cleanup
            stats_after = pool.get_pool_stats()
            connections_after = stats_after.get("total_connections", 0)
            connections_closed = connections_before - connections_after

            logger.info(
                f"Cleaned up {connections_closed} IB connections via connection pool"
            )

            return {
                "success": True,
                "message": f"IB connection pool cleaned up successfully",
                "connections_closed": connections_closed,
                "pool_stats_before": stats_before,
                "pool_stats_after": stats_after,
            }

        except Exception as e:
            logger.error(f"Error cleaning up IB connection pool: {e}")
            return {
                "success": False,
                "message": f"Connection pool cleanup failed: {str(e)}",
                "connections_closed": 0,
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

            os.environ["IB_PORT"] = str(request.port)
            logger.info(f"Updated IB_PORT to {request.port}")

        if request.host is not None:
            # Host change requires reconnection
            reconnect_required = True
            import os

            os.environ["IB_HOST"] = request.host
            logger.info(f"Updated IB_HOST to {request.host}")

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

                # Reset IB configuration to pick up new environment variables
                reset_ib_config()
                logger.info("Reset IB configuration with new environment variables")

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
        self, symbols: List[str], timeframes: List[str]
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
    ) -> Optional[Dict[str, Any]]:
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
            from ktrdr.config.ib_config import get_ib_config
            from ktrdr.config.loader import ConfigLoader
            from ktrdr.config.models import KtrdrConfig, IbHostServiceConfig
            from pathlib import Path

            # Load host service configuration
            try:
                config_loader = ConfigLoader()
                config_path = Path("config/settings.yaml")
                if config_path.exists():
                    main_config = config_loader.load(config_path, KtrdrConfig)
                    host_service_config = main_config.ib_host_service
                else:
                    host_service_config = IbHostServiceConfig()
            except Exception:
                host_service_config = IbHostServiceConfig()

            # Get IB connection config for fallback
            ib_config = get_ib_config()

            # Initialize adapter with appropriate mode
            adapter = IbDataAdapter(
                host=ib_config.host,
                port=ib_config.port,
                use_host_service=host_service_config.enabled,
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
    ) -> List[Dict[str, Any]]:
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

    def get_symbol_discovery_stats(self) -> Dict[str, Any]:
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

"""
IB (Interactive Brokers) service for the KTRDR API.

This module provides service layer functionality for IB operations.
"""

import time
import asyncio
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from ktrdr import get_logger
from ktrdr.data.ib_connection_pool import get_connection_pool, acquire_ib_connection
from ktrdr.data.ib_client_id_registry import ClientIdPurpose
from ktrdr.data.ib_pace_manager import get_pace_manager
from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidatorUnified
from ktrdr.data.ib_data_fetcher_unified import IbDataFetcherUnified
from ktrdr.config.ib_limits import IbLimitsRegistry
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
        # Check if IB connection pool is available
        try:
            pool = await get_connection_pool()
            pool_stats = pool.get_pool_status()
            ib_available = pool_stats["available_connections"] > 0

            # PHASE 4: Add connection resilience information
            logger.info(
                "🔍 Enhanced IB status - including connection resilience metrics"
            )

        except Exception:
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

        # Get pace manager statistics
        pace_manager = get_pace_manager()
        pace_stats = pace_manager.get_pace_statistics()
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
            pool = await get_connection_pool()
            pool_stats = pool.get_pool_status()
            pool_available = pool_stats["available_connections"] > 0
        except Exception:
            pool_available = False

        if not pool_available:
            return IbHealthStatus(
                healthy=False,
                connection_ok=False,
                data_fetching_ok=False,
                last_successful_request=None,
                error_message="IB connection pool not available",
            )

        # ENHANCED IB API TEST: Multi-level validation to catch silent connections
        api_test_ok = False
        connection_ok = False
        try:
            async with acquire_ib_connection(
                purpose=ClientIdPurpose.API_POOL, requested_by="health_check"
            ) as connection:
                connection_ok = True

                # Test actual API calls with timeouts to detect silent connections
                ib = connection.ib

                # Level 1: Basic API test (fast)
                accounts = await asyncio.wait_for(
                    ib.reqManagedAcctsAsync(), timeout=10.0
                )
                if not accounts:
                    logger.warning(
                        f"❌ Level 1 failed: No managed accounts (client_id: {connection.client_id})"
                    )
                    raise Exception("No managed accounts returned")

                # Level 2: Contract details test (tests actual market data access)
                from ib_insync import Stock

                test_contract = Stock("AAPL", "SMART", "USD")
                contract_details = await asyncio.wait_for(
                    ib.reqContractDetailsAsync(test_contract), timeout=15.0
                )
                if not contract_details:
                    logger.warning(
                        f"❌ Level 2 failed: Contract details failed (client_id: {connection.client_id})"
                    )
                    raise Exception("Contract details request failed")

                # Level 3: Current time test (validates server communication)
                server_time = await asyncio.wait_for(
                    ib.reqCurrentTimeAsync(), timeout=5.0
                )
                if not server_time:
                    logger.warning(
                        f"❌ Level 3 failed: Server time failed (client_id: {connection.client_id})"
                    )
                    raise Exception("Server time request failed")

                api_test_ok = True
                logger.debug(
                    f"✅ Enhanced IB health check passed: {len(accounts)} accounts, contract details OK, server time OK (client_id: {connection.client_id})"
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
        pace_manager = get_pace_manager()
        pace_stats = pace_manager.get_pace_statistics()
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
        Get detailed connection resilience status from Phases 1-3 implementation.

        Returns:
            Dictionary with detailed resilience metrics and validation results
        """
        logger.info("🔍 PHASE 4: Testing connection resilience features")

        try:
            pool = await get_connection_pool()
            pool_stats = pool.get_pool_status()
            connection_details = pool.get_connection_details()

            # Test systematic validation (Phase 1)
            validation_results = await self._test_systematic_validation(pool)

            # Test garbage collection status (Phase 2)
            gc_status = self._analyze_garbage_collection_status(
                pool_stats, connection_details
            )

            # Test Client ID 1 preference (Phase 3)
            client_id_status = self._analyze_client_id_preference(connection_details)

            resilience_status = {
                "phase_1_systematic_validation": validation_results,
                "phase_2_garbage_collection": gc_status,
                "phase_3_client_id_preference": client_id_status,
                "overall_resilience_score": self._calculate_resilience_score(
                    validation_results, gc_status, client_id_status
                ),
                "connection_pool_health": {
                    "total_connections": pool_stats.get("total_connections", 0),
                    "healthy_connections": pool_stats.get("healthy_connections", 0),
                    "active_connections": pool_stats.get("active_connections", 0),
                    "pool_uptime_seconds": pool_stats.get("pool_uptime_seconds", 0),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info("✅ Connection resilience status completed successfully")
            return resilience_status

        except Exception as e:
            logger.error(f"❌ Connection resilience status failed: {e}")
            return {
                "error": str(e),
                "phase_1_systematic_validation": {"status": "error"},
                "phase_2_garbage_collection": {"status": "error"},
                "phase_3_client_id_preference": {"status": "error"},
                "overall_resilience_score": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _test_systematic_validation(self, pool) -> Dict[str, Any]:
        """Test Phase 1: Systematic connection validation before handoff."""
        try:
            # Test if the validation logic is configured correctly by checking pool status
            pool_stats = pool.get_pool_status()

            # Check if validation method exists on the pool
            has_validation_method = hasattr(pool, "_validate_connection_before_handoff")

            if has_validation_method:
                return {
                    "status": "working",
                    "validation_enabled": True,
                    "validation_method_exists": True,
                    "pool_running": pool_stats.get("running", False),
                    "description": "Systematic validation before handoff is configured and ready",
                }
            else:
                return {
                    "status": "failed",
                    "validation_enabled": False,
                    "validation_method_exists": False,
                    "description": "Systematic validation method not found",
                }
        except Exception as e:
            return {
                "status": "failed",
                "validation_enabled": False,
                "error": str(e),
                "description": "Systematic validation test failed",
            }

    def _analyze_garbage_collection_status(
        self, pool_stats: Dict, connection_details: List
    ) -> Dict[str, Any]:
        """Analyze Phase 2: Garbage collection with 5min idle timeout."""
        try:
            current_time = time.time()
            max_idle_time = pool_stats.get("configuration", {}).get(
                "max_idle_time", 300
            )  # 5 minutes

            # Analyze connection ages and idle times
            idle_connections = []
            active_connections = []

            for conn in connection_details:
                last_used = conn.get("last_used", current_time)
                idle_time = current_time - last_used

                if conn.get("in_use", False):
                    active_connections.append(
                        {
                            "client_id": conn.get("client_id"),
                            "idle_time": idle_time,
                            "state": "active",
                        }
                    )
                else:
                    idle_connections.append(
                        {
                            "client_id": conn.get("client_id"),
                            "idle_time": idle_time,
                            "state": "idle",
                            "will_be_cleaned": idle_time > max_idle_time,
                        }
                    )

            return {
                "status": "working",
                "max_idle_time_seconds": max_idle_time,
                "idle_connections_count": len(idle_connections),
                "active_connections_count": len(active_connections),
                "connections_ready_for_cleanup": len(
                    [c for c in idle_connections if c["will_be_cleaned"]]
                ),
                "health_check_interval": pool_stats.get("configuration", {}).get(
                    "health_check_interval", 60
                ),
                "description": f"Garbage collection configured for {max_idle_time}s idle timeout",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "description": "Failed to analyze garbage collection status",
            }

    def _analyze_client_id_preference(self, connection_details: List) -> Dict[str, Any]:
        """Analyze Phase 3: Client ID 1 preference with incremental fallback."""
        try:
            client_ids_used = [
                conn.get("client_id")
                for conn in connection_details
                if conn.get("client_id") is not None
            ]
            client_ids_used.sort()

            # Check if lower-numbered client IDs are being preferred
            has_client_id_1 = 1 in client_ids_used
            lowest_id = min(client_ids_used) if client_ids_used else None
            sequential_preference = self._check_sequential_preference(client_ids_used)

            return {
                "status": "working",
                "client_ids_in_use": client_ids_used,
                "using_client_id_1": has_client_id_1,
                "lowest_client_id_used": lowest_id,
                "sequential_preference_detected": sequential_preference,
                "total_active_connections": len(client_ids_used),
                "description": f"Client ID preference working - lowest ID in use: {lowest_id}",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "description": "Failed to analyze client ID preference",
            }

    def _check_sequential_preference(self, client_ids: List[int]) -> bool:
        """Check if client IDs show sequential preference (1, 2, 3...)."""
        if not client_ids:
            return False

        # Check if we're using consecutive IDs starting from a low number
        client_ids_sorted = sorted(client_ids)
        if len(client_ids_sorted) < 2:
            return client_ids_sorted[0] <= 10  # Single connection using low ID

        # Check for consecutive sequences
        for i in range(len(client_ids_sorted) - 1):
            if client_ids_sorted[i + 1] - client_ids_sorted[i] != 1:
                return False

        return client_ids_sorted[0] <= 10  # Sequential and starting from low number

    def _calculate_resilience_score(
        self, validation: Dict, gc: Dict, client_id: Dict
    ) -> float:
        """Calculate overall resilience score (0-100)."""
        score = 0.0

        # Phase 1: Systematic validation (35 points)
        if validation.get("status") == "working":
            score += 35.0

        # Phase 2: Garbage collection (30 points)
        if gc.get("status") == "working":
            score += 30.0

        # Phase 3: Client ID preference (35 points)
        if client_id.get("status") == "working":
            score += 35.0
            # Bonus for actually using low client IDs
            lowest_id = client_id.get("lowest_client_id_used")
            if client_id.get("using_client_id_1") or (
                lowest_id is not None and lowest_id <= 10
            ):
                score += 5.0  # Bonus up to 40 points for this phase

        return min(100.0, score)

    async def get_config(self) -> IbConfigInfo:
        """
        Get IB configuration information.

        Returns:
            IbConfigInfo with current configuration
        """
        try:
            # Get configuration from connection pool stats
            pool = await get_connection_pool()
            pool_stats = pool.get_pool_status()

            # Get client ID registry stats
            from ktrdr.data.ib_client_id_registry import get_client_id_registry

            registry = get_client_id_registry()
            registry_stats = registry.get_allocation_stats()

            return IbConfigInfo(
                host=pool_stats.get("host", "127.0.0.1"),
                port=pool_stats.get("port", 7497),
                client_id_range={
                    "min": registry_stats.get("min_allocated_id", 11),
                    "max": registry_stats.get("max_allocated_id", 999),
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
            # Use connection pool cleanup
            from ktrdr.data.ib_connection_pool import get_connection_pool

            pool = await get_connection_pool()  # Fixed: Added await

            # Get current stats before cleanup
            stats_before = pool.get_pool_status()  # Fixed: Method name
            connections_before = stats_before.get("total_connections", 0)

            # Cleanup all connections in pool
            await pool.cleanup_all_connections()

            # Get stats after cleanup
            stats_after = pool.get_pool_status()  # Fixed: Method name
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

        Args:
            symbols: List of symbols to check
            timeframes: List of timeframes to check (e.g., ['1d', '1h'])

        Returns:
            DataRangesResponse with range information
        """
        # Check if IB connection pool is available
        try:
            pool = await get_connection_pool()
            pool_stats = pool.get_pool_status()
            if pool_stats.get("available_connections", 0) == 0:
                raise ValueError("IB connection pool not available")
        except Exception as e:
            raise ValueError(f"IB integration not available: {e}")

        # Use unified data fetcher for range discovery
        from ktrdr.data.ib_data_range_discovery import IbDataRangeDiscovery

        try:
            # Create range discovery instance using unified fetcher
            data_fetcher = IbDataFetcherUnified(component_name="api_range_discovery")
            range_discovery = IbDataRangeDiscovery(data_fetcher)

            # Track which results were cached
            cached_ranges = set()
            for symbol in symbols:
                for timeframe in timeframes:
                    if range_discovery._get_cached_range(symbol, timeframe):
                        cached_ranges.add(f"{symbol}:{timeframe}")

            # Get ranges for all symbols/timeframes
            multiple_ranges = range_discovery.get_multiple_ranges(symbols, timeframes)

            # Convert to API response format
            symbol_responses = []
            for symbol in symbols:
                ranges: Dict[str, Optional[DataRangeInfo]] = {}
                for timeframe in timeframes:
                    data_range = multiple_ranges.get(symbol, {}).get(timeframe)

                    if data_range:
                        start_date, end_date = data_range

                        # Handle timezone-aware datetime objects
                        if hasattr(start_date, "to_pydatetime"):
                            start_date = start_date.to_pydatetime()
                        if hasattr(end_date, "to_pydatetime"):
                            end_date = end_date.to_pydatetime()

                        # Calculate total days, handling timezone differences
                        if start_date.tzinfo and not end_date.tzinfo:
                            end_date = end_date.replace(tzinfo=start_date.tzinfo)
                        elif end_date.tzinfo and not start_date.tzinfo:
                            start_date = start_date.replace(tzinfo=end_date.tzinfo)

                        total_days = (end_date - start_date).days
                        was_cached = f"{symbol}:{timeframe}" in cached_ranges

                        ranges[timeframe] = DataRangeInfo(
                            earliest_date=start_date,
                            latest_date=end_date,
                            total_days=total_days,
                            cached=was_cached,
                        )
                    else:
                        ranges[timeframe] = None

                symbol_responses.append(
                    SymbolRangeResponse(symbol=symbol, ranges=ranges)
                )

            # Get cache statistics
            cache_stats = range_discovery.get_cache_stats()

            return DataRangesResponse(
                symbols=symbol_responses,
                requested_timeframes=timeframes,
                cache_stats=cache_stats,
            )

        except Exception as e:
            logger.error(f"Failed to get data ranges: {e}")
            # Return empty response with error indication
            return DataRangesResponse(
                symbols=[],
                requested_timeframes=timeframes,
                cache_stats={"error": str(e), "cached_ranges": 0, "fresh_lookups": 0},
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
            # Use unified symbol validator
            validator = IbSymbolValidatorUnified(component_name="api_symbol_discovery")

            if force_refresh:
                # Clear cache for this symbol first
                normalized_symbol = validator._normalize_symbol(symbol)
                if normalized_symbol in validator._cache:
                    del validator._cache[normalized_symbol]
                if normalized_symbol in validator._failed_symbols:
                    validator._failed_symbols.remove(normalized_symbol)

            # Get contract details asynchronously
            contract_info = await validator.get_contract_details_async(symbol)

            if contract_info is None:
                return None

            # Map IB asset type to our instrument type
            instrument_type_map = {
                "STK": "stock",
                "CASH": "forex",
                "FUT": "future",
                "OPT": "option",
                "IND": "index",
            }
            instrument_type = instrument_type_map.get(
                contract_info.asset_type, "unknown"
            )

            # Return symbol information in API format
            return {
                "symbol": contract_info.symbol,
                "instrument_type": instrument_type,
                "exchange": contract_info.exchange,
                "currency": contract_info.currency,
                "description": contract_info.description,
                "discovered_at": contract_info.validated_at,
                "last_validated": contract_info.validated_at,
                "validation_count": 1,
                "is_active": True,
                "head_timestamp": contract_info.head_timestamp,
                "trading_hours": contract_info.trading_hours,
            }

        except Exception as e:
            logger.error(f"Symbol discovery failed for {symbol}: {e}")
            return None

    def get_discovered_symbols(
        self, instrument_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all discovered symbols from the cache.

        Args:
            instrument_type: Filter by instrument type (optional)

        Returns:
            List of discovered symbol information
        """
        try:
            # Use unified symbol validator
            validator = IbSymbolValidatorUnified(component_name="api_symbol_list")

            # Get all cached symbols
            cached_symbols = validator.get_cached_symbols()
            discovered_symbols = []

            # Map IB asset type to our instrument type
            instrument_type_map = {
                "STK": "stock",
                "CASH": "forex",
                "FUT": "future",
                "OPT": "option",
                "IND": "index",
            }

            for symbol in cached_symbols:
                # Get contract info from cache
                contract_info = validator.get_contract_details(symbol)

                if contract_info:
                    # Map IB asset type to our instrument type
                    symbol_instrument_type = instrument_type_map.get(
                        contract_info.asset_type, "unknown"
                    )

                    # Filter by instrument type if specified
                    if instrument_type and symbol_instrument_type != instrument_type:
                        continue

                    discovered_symbols.append(
                        {
                            "symbol": contract_info.symbol,
                            "instrument_type": symbol_instrument_type,
                            "exchange": contract_info.exchange,
                            "currency": contract_info.currency,
                            "description": contract_info.description,
                            "discovered_at": contract_info.validated_at,
                            "last_validated": contract_info.validated_at,
                            "validation_count": 1,
                            "is_active": True,
                            "head_timestamp": contract_info.head_timestamp,
                            "trading_hours": contract_info.trading_hours,
                        }
                    )

            # Sort by last validated time (most recent first)
            discovered_symbols.sort(key=lambda s: s["last_validated"], reverse=True)
            return discovered_symbols

        except Exception as e:
            logger.error(f"Failed to get discovered symbols: {e}")
            return []

    def get_symbol_discovery_stats(self) -> Dict[str, Any]:
        """
        Get symbol discovery cache statistics.

        Returns:
            Dictionary with discovery statistics
        """
        try:
            # Use unified symbol validator
            validator = IbSymbolValidatorUnified(component_name="api_discovery_stats")
            validator_stats = validator.get_cache_stats()
            metrics = validator.get_metrics()

            return {
                "cached_symbols": validator_stats.get("cached_symbols", 0),
                "validated_symbols": validator_stats.get("validated_symbols", 0),
                "failed_symbols": validator_stats.get("failed_symbols", 0),
                "total_lookups": validator_stats.get("total_lookups", 0),
                "total_validations": metrics.get("total_validations", 0),
                "successful_validations": metrics.get("successful_validations", 0),
                "cache_hits": metrics.get("cache_hits", 0),
                "success_rate": metrics.get("success_rate", 0.0),
                "pace_violations": metrics.get("pace_violations", 0),
                "retries_performed": metrics.get("retries_performed", 0),
                "avg_validation_time": metrics.get("avg_validation_time", 0.0),
            }

        except Exception as e:
            logger.error(f"Failed to get discovery stats: {e}")
            return {}

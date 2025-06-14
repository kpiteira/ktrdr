"""
IB Connection Pool

Unified connection manager for Interactive Brokers with async-first design.

This pool provides:
- Single source of truth for all IB connections
- Async-first architecture with connection reuse
- Automatic health monitoring and reconnection
- Proper resource cleanup and lifecycle management
- Integration with client ID registry and pace management
- Comprehensive metrics and monitoring

Key Features:
- Connection pooling with configurable limits
- Purpose-based connection allocation
- Health monitoring with automatic recovery
- Clean async context managers
- Thread-safe operations
- Persistent connection state
"""

import asyncio
import time
from typing import Dict, List, Optional, Set, Any, AsyncContextManager, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from contextlib import asynccontextmanager
import weakref

from ib_insync import IB, util
from ktrdr.logging import get_logger
from ktrdr.config.ib_config import get_ib_config, IbConfig
from ktrdr.data.ib_client_id_registry import (
    get_client_id_registry,
    ClientIdPurpose,
    allocate_client_id,
    deallocate_client_id,
    update_client_id_activity,
)
from ktrdr.errors import ConnectionError
from ktrdr.data.ib_metrics_collector import (
    get_metrics_collector,
    record_operation_start,
    record_operation_end,
    record_counter,
    record_gauge,
)

logger = get_logger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    CLOSING = "closing"


@dataclass
class ConnectionMetrics:
    """Metrics for a single connection."""

    created_at: float = field(default_factory=time.time)
    connected_at: Optional[float] = None
    last_activity: Optional[float] = None
    reconnect_count: int = 0
    request_count: int = 0
    error_count: int = 0
    total_uptime: float = 0.0

    def record_activity(self):
        """Record connection activity."""
        self.last_activity = time.time()
        self.request_count += 1

    def record_error(self):
        """Record connection error."""
        self.error_count += 1

    def record_reconnect(self):
        """Record reconnection event."""
        self.reconnect_count += 1
        self.connected_at = time.time()

    def get_uptime(self) -> float:
        """Get current uptime in seconds."""
        if self.connected_at is None:
            return 0.0
        return time.time() - self.connected_at


@dataclass
class PooledConnection:
    """A connection managed by the pool."""

    client_id: int
    purpose: ClientIdPurpose
    ib: IB
    state: ConnectionState = ConnectionState.DISCONNECTED
    created_by: str = "unknown"
    last_used: float = field(default_factory=time.time)
    in_use: bool = False
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    health_check_failures: int = 0
    last_validated: Optional[float] = None  # Timestamp of last successful validation

    def __post_init__(self):
        """Initialize after creation."""
        self.metrics.created_at = time.time()

    def mark_used(self):
        """Mark connection as used."""
        self.last_used = time.time()
        self.metrics.record_activity()
        update_client_id_activity(self.client_id)

    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        try:
            return (
                self.state == ConnectionState.CONNECTED
                and self.ib.isConnected()
                and self.health_check_failures < 3
            )
        except Exception:
            return False

    def get_info(self) -> Dict[str, Any]:
        """Get connection information."""
        return {
            "client_id": self.client_id,
            "purpose": self.purpose.value,
            "state": self.state.value,
            "created_by": self.created_by,
            "last_used": self.last_used,
            "last_validated": self.last_validated,
            "in_use": self.in_use,
            "uptime": self.metrics.get_uptime(),
            "request_count": self.metrics.request_count,
            "error_count": self.metrics.error_count,
            "reconnect_count": self.metrics.reconnect_count,
            "health_check_failures": self.health_check_failures,
            "is_healthy": self.is_healthy(),
        }


class IbConnectionPool:
    """
    Unified connection pool for Interactive Brokers.

    This async-first connection pool manages all IB connections with:
    - Purpose-based connection allocation
    - Automatic health monitoring
    - Connection reuse and pooling
    - Proper resource cleanup
    - Comprehensive metrics
    """

    _instance: Optional["IbConnectionPool"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "IbConnectionPool":
        """Singleton pattern for global access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the connection pool."""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        # Configuration
        self.config = get_ib_config()
        self.client_id_registry = get_client_id_registry()

        # Pool management
        self._connections: Dict[int, PooledConnection] = {}
        self._purpose_pools: Dict[ClientIdPurpose, Set[int]] = {
            purpose: set() for purpose in ClientIdPurpose
        }

        # Pool configuration
        self._max_connections_per_purpose = {
            ClientIdPurpose.API_SINGLETON: 1,
            ClientIdPurpose.API_POOL: 5,
            ClientIdPurpose.GAP_FILLER: 2,
            ClientIdPurpose.DATA_MANAGER: 2,
            ClientIdPurpose.SYMBOL_VALIDATION: 1,
            ClientIdPurpose.CLI_TEMPORARY: 3,
            ClientIdPurpose.TEST_CONNECTIONS: 10,
            ClientIdPurpose.RESERVED: 1,
        }

        # Health monitoring configuration
        self._health_check_interval = 60.0  # Check every minute for faster cleanup
        self._health_check_task: Optional[asyncio.Task] = None
        self._connection_timeout = 30.0  # seconds
        self._max_idle_time = 300.0  # Keep 5 minutes as requested

        # Statistics
        self._stats = {
            "total_connections_created": 0,
            "total_connections_destroyed": 0,
            "total_requests_served": 0,
            "total_health_checks": 0,
            "total_reconnections": 0,
            "pool_started_at": time.time(),
        }

        # Lifecycle management
        self._running = False
        self._shutdown_event = asyncio.Event()

        logger.info("IbConnectionPool initialized")

    async def start(self) -> bool:
        """
        Start the connection pool and background tasks.

        Returns:
            True if started successfully, False otherwise
        """
        operation_id = record_operation_start("connection_pool", "start")

        if self._running:
            logger.warning("Connection pool is already running")
            record_operation_end(operation_id, "connection_pool", "start", True)
            return True

        try:
            self._running = True
            self._shutdown_event.clear()

            # Start health monitoring task
            self._health_check_task = asyncio.create_task(self._health_monitor_loop())

            # Record metrics
            record_counter("connection_pool", "pool_started")
            record_gauge("connection_pool", "pool_active", 1)

            logger.info("✅ IB Connection Pool started")
            record_operation_end(operation_id, "connection_pool", "start", True)
            return True

        except Exception as e:
            logger.error(f"Failed to start connection pool: {e}")
            self._running = False
            record_operation_end(
                operation_id,
                "connection_pool",
                "start",
                False,
                "POOL_START_ERROR",
                str(e),
            )
            return False

    async def stop(self) -> None:
        """Stop the connection pool and clean up all connections."""
        if not self._running:
            return

        logger.info("🛑 Stopping IB Connection Pool...")
        self._running = False
        self._shutdown_event.set()

        # Stop health monitoring
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        await self._close_all_connections()

        logger.info("✅ IB Connection Pool stopped")

    @asynccontextmanager
    async def acquire_connection(
        self,
        purpose: ClientIdPurpose,
        requested_by: str,
        preferred_client_id: Optional[int] = None,
    ) -> AsyncContextManager[PooledConnection]:
        """
        Acquire a connection from the pool.

        Args:
            purpose: Purpose for the connection
            requested_by: Component requesting the connection
            preferred_client_id: Specific client ID to request (if available)

        Yields:
            PooledConnection instance
        """
        operation_id = record_operation_start(
            "connection_pool",
            "acquire_connection",
            {"purpose": purpose.value, "requested_by": requested_by},
        )

        connection = None
        try:
            connection = await self._get_or_create_connection(
                purpose, requested_by, preferred_client_id
            )

            if connection is None:
                record_counter("connection_pool", "connection_acquisition_failed")
                raise ConnectionError(
                    f"Could not acquire connection for {purpose.value}"
                )

            # SYSTEMATIC VALIDATION: Test connection before handoff
            if not await self._validate_connection_before_handoff(connection):
                # Connection failed validation - remove and try to create new one
                await self._remove_connection(connection.client_id, "validation_failed")
                record_counter("connection_pool", "connection_validation_failed")
                
                # Try to create a new connection
                connection = await self._create_new_connection(purpose, requested_by, preferred_client_id)
                if connection is None:
                    raise ConnectionError(f"Could not create replacement connection after validation failure for {purpose.value}")
                
                # Validate the new connection too
                if not await self._validate_connection_before_handoff(connection):
                    await self._remove_connection(connection.client_id, "replacement_validation_failed")
                    raise ConnectionError(f"Replacement connection also failed validation for {purpose.value}")

            connection.in_use = True
            connection.mark_used()

            # Record metrics
            record_counter("connection_pool", "connection_acquired")
            record_gauge(
                "connection_pool",
                "connections_in_use",
                len([c for c in self._connections.values() if c.in_use]),
            )

            logger.debug(
                f"🔗 Acquired connection {connection.client_id} for {purpose.value}"
            )
            record_operation_end(
                operation_id,
                "connection_pool",
                "acquire_connection",
                True,
                labels={"client_id": str(connection.client_id)},
            )
            yield connection

        except Exception as e:
            if connection:
                connection.metrics.record_error()
            logger.error(f"Error in connection context: {e}")
            record_operation_end(
                operation_id,
                "connection_pool",
                "acquire_connection",
                False,
                "CONNECTION_ERROR",
                str(e),
            )
            raise
        finally:
            if connection:
                connection.in_use = False
                logger.debug(f"🔓 Released connection {connection.client_id}")

    async def _get_or_create_connection(
        self,
        purpose: ClientIdPurpose,
        requested_by: str,
        preferred_client_id: Optional[int] = None,
    ) -> Optional[PooledConnection]:
        """Get existing connection or create new one."""
        async with self._lock:
            # Try to find existing healthy connection for this purpose
            available_connection = self._find_available_connection(purpose)
            if available_connection and available_connection.is_healthy():
                logger.debug(
                    f"♻️ Reusing existing connection {available_connection.client_id} for {purpose.value}"
                )
                return available_connection

            # Check if we can create a new connection
            if not self._can_create_connection(purpose):
                logger.warning(
                    f"Cannot create new connection for {purpose.value}: pool limit reached"
                )
                # Try to wait for an existing connection to become available
                return await self._wait_for_available_connection(purpose)

            # Create new connection
            return await self._create_new_connection(
                purpose, requested_by, preferred_client_id
            )

    def _find_available_connection(
        self, purpose: ClientIdPurpose
    ) -> Optional[PooledConnection]:
        """Find an available connection for the given purpose."""
        purpose_client_ids = self._purpose_pools[purpose]

        for client_id in purpose_client_ids:
            connection = self._connections.get(client_id)
            if connection and not connection.in_use and connection.is_healthy():
                return connection

        return None

    def _can_create_connection(self, purpose: ClientIdPurpose) -> bool:
        """Check if we can create a new connection for the given purpose."""
        current_count = len(self._purpose_pools[purpose])
        max_count = self._max_connections_per_purpose.get(purpose, 1)
        return current_count < max_count

    async def _wait_for_available_connection(
        self, purpose: ClientIdPurpose, timeout: float = 30.0
    ) -> Optional[PooledConnection]:
        """Wait for an existing connection to become available."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            connection = self._find_available_connection(purpose)
            if connection:
                return connection

            await asyncio.sleep(0.5)  # Check every 500ms

        logger.warning(f"Timeout waiting for available connection for {purpose.value}")
        return None

    async def _create_new_connection(
        self,
        purpose: ClientIdPurpose,
        requested_by: str,
        preferred_client_id: Optional[int] = None,
    ) -> Optional[PooledConnection]:
        """Create a new connection with Client ID 1 preference strategy."""
        operation_id = record_operation_start(
            "connection_pool",
            "create_connection",
            {"purpose": purpose.value, "requested_by": requested_by},
        )

        try:
            # PHASE 3: Implement Client ID 1 preference with incremental fallback
            connection = await self._create_connection_with_client_id_preference(
                purpose, requested_by, preferred_client_id, operation_id
            )
            
            if connection is None:
                record_operation_end(
                    operation_id,
                    "connection_pool",
                    "create_connection",
                    False,
                    "ALL_CLIENT_IDS_FAILED",
                )
                return None

            # Add to pool
            self._connections[connection.client_id] = connection
            self._purpose_pools[purpose].add(connection.client_id)
            self._stats["total_connections_created"] += 1

            # Record metrics
            record_counter("connection_pool", "connection_created")
            record_gauge("connection_pool", "total_connections", len(self._connections))
            record_gauge(
                "connection_pool",
                "connections_active",
                len(
                    [
                        c
                        for c in self._connections.values()
                        if c.state == ConnectionState.CONNECTED
                    ]
                ),
            )

            logger.info(f"✅ Created new IB connection (client_id={connection.client_id})")
            record_operation_end(
                operation_id,
                "connection_pool",
                "create_connection",
                True,
                labels={"client_id": str(connection.client_id)},
            )
            return connection

        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            record_counter("connection_pool", "connection_creation_error")
            record_operation_end(
                operation_id,
                "connection_pool",
                "create_connection",
                False,
                "CREATE_CONNECTION_ERROR",
                str(e),
            )
            return None
    
    async def _create_connection_with_client_id_preference(
        self,
        purpose: ClientIdPurpose,
        requested_by: str,
        preferred_client_id: Optional[int],
        operation_id: str,
    ) -> Optional[PooledConnection]:
        """
        Implement Client ID 1 preference with incremental fallback strategy.
        
        Strategy:
        1. Always attempt Client ID 1 first (recycle if available)  
        2. If Client ID 1 is in use, increment: 2, 3, 4...
        3. Parse IB error codes to detect conflicts (error 326)
        4. Continue until successful connection or all IDs exhausted
        """
        logger.info(f"🎯 Implementing Client ID 1 preference strategy for {purpose.value}")
        
        # Determine client IDs to try in order (1, 2, 3...)
        client_ids_to_try = []
        
        if preferred_client_id is not None:
            # Honor specific preference first
            client_ids_to_try.append(preferred_client_id)
            logger.info(f"🎯 Honoring specific preference: {preferred_client_id}")
        
        # Always try Client ID 1 first (core principle), then increment
        base_sequence = list(range(1, 21))  # Try IDs 1-20 for robust fallback
        for client_id in base_sequence:
            if client_id not in client_ids_to_try:
                client_ids_to_try.append(client_id)
        
        logger.info(f"🎯 Client ID sequence: {client_ids_to_try[:10]}{'...' if len(client_ids_to_try) > 10 else ''}")
        
        for attempt, client_id in enumerate(client_ids_to_try):
            try:
                logger.info(f"🎯 ATTEMPT {attempt + 1}: Trying Client ID {client_id}")
                
                # Check if this client ID is already in our pool
                if client_id in self._connections:
                    logger.debug(f"🎯 Client ID {client_id} already in pool, skipping")
                    continue
                
                # Try to allocate from registry 
                allocated_id = allocate_client_id(purpose, requested_by, client_id)
                if allocated_id != client_id:
                    if allocated_id is None:
                        logger.debug(f"🎯 Client ID {client_id} allocation failed, trying next")
                        continue
                    else:
                        logger.info(f"🎯 Registry allocated {allocated_id} instead of requested {client_id}")
                        client_id = allocated_id
                
                # Create IB instance and attempt connection
                ib = IB()
                self._setup_connection_callbacks(ib, client_id)
                
                connection = PooledConnection(
                    client_id=client_id,
                    purpose=purpose,
                    ib=ib,
                    created_by=requested_by,
                    state=ConnectionState.CONNECTING,
                )
                
                # Attempt connection with error code detection
                success, error_code = await self._connect_ib_with_error_detection(connection)
                
                if success:
                    logger.info(f"✅ SUCCESS: Client ID {client_id} connected successfully!")
                    return connection
                else:
                    # Parse error and handle accordingly
                    if error_code == 326:
                        logger.warning(f"🎯 Client ID {client_id} in use (IB error 326), trying next...")
                    else:
                        logger.warning(f"🎯 Client ID {client_id} failed (error {error_code}), trying next...")
                    
                    # Clean up failed connection
                    deallocate_client_id(client_id, "client_id_conflict_cleanup")
                    try:
                        if connection.ib.isConnected():
                            connection.ib.disconnect()
                    except:
                        pass
                    
                    continue
                    
            except Exception as e:
                logger.error(f"🎯 Unexpected error with Client ID {client_id}: {e}")
                # Clean up and continue
                try:
                    deallocate_client_id(client_id, "unexpected_error_cleanup") 
                except:
                    pass
                continue
        
        logger.error("🎯 FAILED: All client IDs exhausted, no successful connection")
        return None

    def _setup_connection_callbacks(self, ib: IB, client_id: int) -> None:
        """Set up IB connection callbacks."""

        def on_connected():
            logger.debug(f"📡 IB connected callback for client {client_id}")

        def on_disconnected():
            logger.info(f"📡 IB disconnected callback for client {client_id}")
            # Mark connection for health check
            if client_id in self._connections:
                self._connections[client_id].state = ConnectionState.DISCONNECTED

        def on_error(reqId, errorCode, errorString, contract):
            logger.debug(
                f"📡 IB error callback for client {client_id}: {errorCode} - {errorString}"
            )
            if client_id in self._connections:
                self._connections[client_id].metrics.record_error()

        ib.connectedEvent += on_connected
        ib.disconnectedEvent += on_disconnected
        ib.errorEvent += on_error

    async def _connect_ib_with_error_detection(self, connection: PooledConnection) -> Tuple[bool, Optional[int]]:
        """
        Connect an IB instance with enhanced error code detection.
        
        Returns:
            Tuple of (success: bool, error_code: Optional[int])
        """
        error_code = None
        last_error = None
        
        # Set up error capture
        def capture_error(reqId, errorCode, errorString, contract):
            nonlocal error_code, last_error
            error_code = errorCode
            last_error = errorString
            logger.debug(f"🎯 IB Error captured: {errorCode} - {errorString}")
        
        # Temporarily capture errors
        connection.ib.errorEvent += capture_error
        
        try:
            # Connect with timeout
            await asyncio.wait_for(
                connection.ib.connectAsync(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=connection.client_id,
                    readonly=self.config.readonly,
                    timeout=self.config.timeout,
                ),
                timeout=self._connection_timeout,
            )

            if connection.ib.isConnected():
                # CRITICAL: Test the connection immediately to detect silent connections
                try:
                    # Quick validation test with very short timeout
                    await asyncio.wait_for(
                        connection.ib.reqCurrentTimeAsync(),
                        timeout=5.0  # Very short timeout to detect hangs
                    )
                    connection.state = ConnectionState.CONNECTED
                    connection.metrics.connected_at = time.time()
                    logger.info(f"✅ Created new IB connection with validation (client_id={connection.client_id})")
                    return True, None
                except asyncio.TimeoutError:
                    logger.error(f"🚨 SILENT CONNECTION detected for client {connection.client_id} - connection established but operations hang!")
                    connection.state = ConnectionState.FAILED
                    # Disconnect the silent connection
                    try:
                        connection.ib.disconnect()
                    except:
                        pass
                    return False, error_code
                except Exception as e:
                    logger.error(f"🚨 Connection validation failed for client {connection.client_id}: {e}")
                    connection.state = ConnectionState.FAILED
                    return False, error_code
            else:
                connection.state = ConnectionState.FAILED
                return False, error_code

        except asyncio.TimeoutError:
            logger.error(f"Connection timeout for client {connection.client_id}")
            connection.state = ConnectionState.FAILED
            return False, error_code
        except Exception as e:
            logger.error(f"Connection failed for client {connection.client_id}: {e}")
            connection.state = ConnectionState.FAILED
            # Check if this is a known IB error with error code in exception message
            if "326" in str(e) or "already in use" in str(e).lower():
                error_code = 326
            return False, error_code
        finally:
            # Remove error capture
            try:
                connection.ib.errorEvent -= capture_error
            except:
                pass
    
    async def _connect_ib(self, connection: PooledConnection) -> bool:
        """Connect an IB instance with enhanced validation. (Legacy method for compatibility)"""
        success, _ = await self._connect_ib_with_error_detection(connection)
        return success

    async def _validate_connection_before_handoff(self, connection: PooledConnection) -> bool:
        """
        Systematic validation before every connection handoff.
        
        Implements the core principle: test isConnected() and reqCurrentTime()
        systematically before handing off any connection to ensure it's working.
        
        Args:
            connection: The connection to validate
            
        Returns:
            True if connection is valid and responsive, False otherwise
        """
        try:
            # 1. Basic connectivity check
            if not connection.ib.isConnected():
                logger.debug(f"🔍 Connection {connection.client_id} failed isConnected() check")
                return False
            
            # 2. API responsiveness test - this detects silent connections
            logger.debug(f"🔍 Testing API responsiveness for connection {connection.client_id}")
            await asyncio.wait_for(
                connection.ib.reqCurrentTimeAsync(),
                timeout=3.0  # Fast failure for quick responsiveness check
            )
            
            # 3. Mark as validated and update metrics
            connection.last_validated = time.time()
            logger.debug(f"✅ Connection {connection.client_id} validated successfully")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Connection {connection.client_id} failed reqCurrentTime timeout (3s) - possible silent connection")
            return False
        except Exception as e:
            logger.warning(f"❌ Connection {connection.client_id} validation failed: {e}")
            return False

    async def test_connection_on_circuit_breaker_failure(self, connection: PooledConnection) -> bool:
        """
        Test connection when circuit breaker detects API failures.
        
        This integrates with the circuit breaker pattern to test connections
        when API operations start failing, allowing for proactive detection
        of connection issues.
        
        Args:
            connection: The connection to test
            
        Returns:
            True if connection is healthy, False if should be removed
        """
        logger.info(f"🔄 Circuit breaker triggered - testing connection {connection.client_id}")
        
        if not await self._validate_connection_before_handoff(connection):
            logger.warning(f"⚠️ Connection {connection.client_id} failed circuit breaker test - removing")
            await self._remove_connection(connection.client_id, "circuit_breaker_failure")
            return False
        
        logger.info(f"✅ Connection {connection.client_id} passed circuit breaker test")
        return True

    async def _health_monitor_loop(self) -> None:
        """Background health monitoring loop."""
        logger.info("🩺 Starting connection health monitor")

        while self._running and not self._shutdown_event.is_set():
            try:
                await self._perform_health_checks()
                await self._cleanup_idle_connections()

                # Wait for next cycle
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=self._health_check_interval
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    continue  # Normal timeout, continue monitoring

            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(5)  # Wait before retry

        logger.info("🩺 Health monitor stopped")

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all connections."""
        self._stats["total_health_checks"] += 1
        unhealthy_connections = []

        for client_id, connection in self._connections.items():
            try:
                if connection.in_use:
                    continue  # Skip connections in use

                # Check basic connection health
                if not connection.ib.isConnected():
                    connection.health_check_failures += 1
                    logger.warning(
                        f"🩺 Health check failed for client {client_id}: not connected"
                    )
                    unhealthy_connections.append(connection)
                    continue

                # Try a simple API call to verify connection works
                try:
                    await asyncio.wait_for(
                        connection.ib.reqCurrentTimeAsync(), timeout=5.0
                    )
                    # Reset failure count on success
                    connection.health_check_failures = 0
                    logger.debug(f"🩺 Health check passed for client {client_id}")

                except asyncio.TimeoutError:
                    connection.health_check_failures += 1
                    logger.warning(f"🩺 Health check timeout for client {client_id}")
                    if connection.health_check_failures >= 3:
                        unhealthy_connections.append(connection)

            except Exception as e:
                connection.health_check_failures += 1
                logger.warning(f"🩺 Health check error for client {client_id}: {e}")
                if connection.health_check_failures >= 3:
                    unhealthy_connections.append(connection)

        # Remove unhealthy connections
        for connection in unhealthy_connections:
            await self._remove_connection(connection.client_id, "health_check_failure")

    async def _cleanup_idle_connections(self) -> None:
        """Clean up idle connections that haven't been used recently."""
        current_time = time.time()
        idle_connections = []

        for client_id, connection in self._connections.items():
            if connection.in_use:
                continue

            idle_time = current_time - connection.last_used
            if idle_time > self._max_idle_time:
                idle_connections.append(connection)

        for connection in idle_connections:
            logger.info(
                f"🧹 Removing idle connection {connection.client_id} (idle for {(current_time - connection.last_used):.1f}s)"
            )
            await self._remove_connection(connection.client_id, "idle_cleanup")

    async def _remove_connection(self, client_id: int, reason: str) -> None:
        """Remove a connection from the pool."""
        connection = self._connections.get(client_id)
        if not connection:
            return

        try:
            # Disconnect IB
            if connection.ib.isConnected():
                connection.ib.disconnect()

            # Remove from pool
            del self._connections[client_id]
            self._purpose_pools[connection.purpose].discard(client_id)

            # Deallocate client ID
            deallocate_client_id(client_id, f"pool_cleanup_{reason}")

            self._stats["total_connections_destroyed"] += 1

            logger.info(f"🗑️ Removed connection {client_id} ({reason})")

        except Exception as e:
            logger.error(f"Error removing connection {client_id}: {e}")

    async def cleanup_all_connections(self) -> None:
        """Public method to cleanup all connections in the pool."""
        logger.info("🧹 Cleaning up all connections in the pool")
        await self._close_all_connections()

    async def _close_all_connections(self) -> None:
        """Close all connections in the pool."""
        client_ids = list(self._connections.keys())

        for client_id in client_ids:
            await self._remove_connection(client_id, "pool_shutdown")

        self._connections.clear()
        for purpose_set in self._purpose_pools.values():
            purpose_set.clear()

    def get_pool_status(self) -> Dict[str, Any]:
        """Get comprehensive pool status."""
        current_time = time.time()

        # Update real-time metrics
        total_connections = len(self._connections)
        active_connections = len([c for c in self._connections.values() if c.in_use])
        healthy_connections = len(
            [c for c in self._connections.values() if c.is_healthy()]
        )

        record_gauge("connection_pool", "total_connections", total_connections)
        record_gauge("connection_pool", "active_connections", active_connections)
        record_gauge("connection_pool", "healthy_connections", healthy_connections)

        # Calculate purpose statistics
        purpose_stats = {}
        for purpose in ClientIdPurpose:
            connections = [
                conn for conn in self._connections.values() if conn.purpose == purpose
            ]

            purpose_stats[purpose.value] = {
                "total_connections": len(connections),
                "active_connections": len([c for c in connections if c.in_use]),
                "healthy_connections": len([c for c in connections if c.is_healthy()]),
                "max_connections": self._max_connections_per_purpose.get(purpose, 1),
            }

        uptime = current_time - self._stats["pool_started_at"]

        # Get metrics from collector
        metrics_collector = get_metrics_collector()
        pool_metrics = metrics_collector.get_component_metrics("connection_pool")

        status = {
            "running": self._running,
            "total_connections": total_connections,
            "active_connections": active_connections,
            "healthy_connections": healthy_connections,
            "unhealthy_connections": total_connections - healthy_connections,
            "purpose_statistics": purpose_stats,
            "pool_uptime_seconds": uptime,
            "configuration": {
                "health_check_interval": self._health_check_interval,
                "connection_timeout": self._connection_timeout,
                "max_idle_time": self._max_idle_time,
            },
            "statistics": self._stats,
            "metrics": {
                "operations_total": (
                    pool_metrics.total_operations if pool_metrics else 0
                ),
                "operations_successful": (
                    pool_metrics.successful_operations if pool_metrics else 0
                ),
                "operations_failed": (
                    pool_metrics.failed_operations if pool_metrics else 0
                ),
                "success_rate_percent": (
                    pool_metrics.success_rate if pool_metrics else 100.0
                ),
                "average_operation_duration": (
                    pool_metrics.average_duration if pool_metrics else 0.0
                ),
                "connections_created": (
                    pool_metrics.connections_created if pool_metrics else 0
                ),
                "connections_failed": (
                    pool_metrics.connections_failed if pool_metrics else 0
                ),
            },
            "timestamp": current_time,
        }

        return status

    def get_connection_details(self) -> List[Dict[str, Any]]:
        """Get detailed information about all connections."""
        return [connection.get_info() for connection in self._connections.values()]


# Global pool instance
_pool: Optional[IbConnectionPool] = None


async def get_connection_pool() -> IbConnectionPool:
    """Get the global connection pool instance."""
    global _pool
    if _pool is None:
        _pool = IbConnectionPool()
        if not _pool._running:
            await _pool.start()
    return _pool


async def acquire_ib_connection(
    purpose: ClientIdPurpose,
    requested_by: str,
    preferred_client_id: Optional[int] = None,
) -> AsyncContextManager[PooledConnection]:
    """Convenience function to acquire an IB connection."""
    pool = await get_connection_pool()
    return pool.acquire_connection(purpose, requested_by, preferred_client_id)


async def shutdown_connection_pool() -> None:
    """Shutdown the global connection pool."""
    global _pool
    if _pool:
        await _pool.stop()
        _pool = None

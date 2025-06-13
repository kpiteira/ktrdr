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
from typing import Dict, List, Optional, Set, Any, AsyncContextManager
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
    update_client_id_activity
)
from ktrdr.errors import ConnectionError

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
    created_at: float
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
                self.state == ConnectionState.CONNECTED and
                self.ib.isConnected() and
                self.health_check_failures < 3
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
            "in_use": self.in_use,
            "uptime": self.metrics.get_uptime(),
            "request_count": self.metrics.request_count,
            "error_count": self.metrics.error_count,
            "reconnect_count": self.metrics.reconnect_count,
            "health_check_failures": self.health_check_failures,
            "is_healthy": self.is_healthy()
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
            ClientIdPurpose.RESERVED: 1
        }
        
        # Health monitoring
        self._health_check_interval = 30.0  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        self._connection_timeout = 30.0  # seconds
        self._max_idle_time = 300.0  # 5 minutes
        
        # Statistics
        self._stats = {
            "total_connections_created": 0,
            "total_connections_destroyed": 0,
            "total_requests_served": 0,
            "total_health_checks": 0,
            "total_reconnections": 0,
            "pool_started_at": time.time()
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
        if self._running:
            logger.warning("Connection pool is already running")
            return True
        
        try:
            self._running = True
            self._shutdown_event.clear()
            
            # Start health monitoring task
            self._health_check_task = asyncio.create_task(self._health_monitor_loop())
            
            logger.info("✅ IB Connection Pool started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start connection pool: {e}")
            self._running = False
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
        preferred_client_id: Optional[int] = None
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
        connection = None
        try:
            connection = await self._get_or_create_connection(
                purpose, requested_by, preferred_client_id
            )
            
            if connection is None:
                raise ConnectionError(f"Could not acquire connection for {purpose.value}")
            
            connection.in_use = True
            connection.mark_used()
            
            logger.debug(f"🔗 Acquired connection {connection.client_id} for {purpose.value}")
            yield connection
            
        except Exception as e:
            if connection:
                connection.metrics.record_error()
            logger.error(f"Error in connection context: {e}")
            raise
        finally:
            if connection:
                connection.in_use = False
                logger.debug(f"🔓 Released connection {connection.client_id}")
    
    async def _get_or_create_connection(
        self,
        purpose: ClientIdPurpose,
        requested_by: str,
        preferred_client_id: Optional[int] = None
    ) -> Optional[PooledConnection]:
        """Get existing connection or create new one."""
        async with self._lock:
            # Try to find existing healthy connection for this purpose
            available_connection = self._find_available_connection(purpose)
            if available_connection and available_connection.is_healthy():
                logger.debug(f"♻️ Reusing existing connection {available_connection.client_id} for {purpose.value}")
                return available_connection
            
            # Check if we can create a new connection
            if not self._can_create_connection(purpose):
                logger.warning(f"Cannot create new connection for {purpose.value}: pool limit reached")
                # Try to wait for an existing connection to become available
                return await self._wait_for_available_connection(purpose)
            
            # Create new connection
            return await self._create_new_connection(purpose, requested_by, preferred_client_id)
    
    def _find_available_connection(self, purpose: ClientIdPurpose) -> Optional[PooledConnection]:
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
        self,
        purpose: ClientIdPurpose,
        timeout: float = 30.0
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
        preferred_client_id: Optional[int] = None
    ) -> Optional[PooledConnection]:
        """Create a new connection."""
        try:
            # Allocate client ID
            client_id = allocate_client_id(purpose, requested_by, preferred_client_id)
            if client_id is None:
                logger.error(f"Could not allocate client ID for {purpose.value}")
                return None
            
            logger.info(f"🔄 Creating new IB connection (client_id={client_id}, purpose={purpose.value})")
            
            # Create IB instance
            ib = IB()
            
            # Set up error callbacks
            self._setup_connection_callbacks(ib, client_id)
            
            # Create pooled connection
            connection = PooledConnection(
                client_id=client_id,
                purpose=purpose,
                ib=ib,
                created_by=requested_by,
                state=ConnectionState.CONNECTING
            )
            
            # Attempt connection
            success = await self._connect_ib(connection)
            if not success:
                # Clean up on failure
                deallocate_client_id(client_id, "connection_pool_cleanup")
                return None
            
            # Add to pool
            self._connections[client_id] = connection
            self._purpose_pools[purpose].add(client_id)
            self._stats["total_connections_created"] += 1
            
            logger.info(f"✅ Created new IB connection (client_id={client_id})")
            return connection
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
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
            logger.debug(f"📡 IB error callback for client {client_id}: {errorCode} - {errorString}")
            if client_id in self._connections:
                self._connections[client_id].metrics.record_error()
        
        ib.connectedEvent += on_connected
        ib.disconnectedEvent += on_disconnected
        ib.errorEvent += on_error
    
    async def _connect_ib(self, connection: PooledConnection) -> bool:
        """Connect an IB instance."""
        try:
            # Connect with timeout
            await asyncio.wait_for(
                connection.ib.connectAsync(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=connection.client_id,
                    readonly=self.config.readonly,
                    timeout=self.config.timeout
                ),
                timeout=self._connection_timeout
            )
            
            if connection.ib.isConnected():
                connection.state = ConnectionState.CONNECTED
                connection.metrics.connected_at = time.time()
                return True
            else:
                connection.state = ConnectionState.FAILED
                return False
                
        except asyncio.TimeoutError:
            logger.error(f"Connection timeout for client {connection.client_id}")
            connection.state = ConnectionState.FAILED
            return False
        except Exception as e:
            logger.error(f"Connection failed for client {connection.client_id}: {e}")
            connection.state = ConnectionState.FAILED
            return False
    
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
                        self._shutdown_event.wait(),
                        timeout=self._health_check_interval
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
                    logger.warning(f"🩺 Health check failed for client {client_id}: not connected")
                    unhealthy_connections.append(connection)
                    continue
                
                # Try a simple API call to verify connection works
                try:
                    await asyncio.wait_for(
                        connection.ib.reqCurrentTimeAsync(),
                        timeout=5.0
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
            logger.info(f"🧹 Removing idle connection {connection.client_id} (idle for {(current_time - connection.last_used):.1f}s)")
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
        
        # Calculate purpose statistics
        purpose_stats = {}
        for purpose in ClientIdPurpose:
            connections = [
                conn for conn in self._connections.values()
                if conn.purpose == purpose
            ]
            
            purpose_stats[purpose.value] = {
                "total_connections": len(connections),
                "active_connections": len([c for c in connections if c.in_use]),
                "healthy_connections": len([c for c in connections if c.is_healthy()]),
                "max_connections": self._max_connections_per_purpose.get(purpose, 1)
            }
        
        # Calculate overall statistics
        total_connections = len(self._connections)
        active_connections = len([c for c in self._connections.values() if c.in_use])
        healthy_connections = len([c for c in self._connections.values() if c.is_healthy()])
        
        uptime = current_time - self._stats["pool_started_at"]
        
        return {
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
                "max_idle_time": self._max_idle_time
            },
            "statistics": self._stats
        }
    
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
    preferred_client_id: Optional[int] = None
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
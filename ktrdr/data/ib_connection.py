"""
IB Connection Manager

Handles connection lifecycle to Interactive Brokers Gateway/TWS with
retry logic and health monitoring.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from ib_insync import IB, util
from ktrdr.logging import get_logger
from ktrdr.errors import ConnectionError, retry_with_backoff, RetryConfig

logger = get_logger(__name__)


@dataclass
class ConnectionConfig:
    """IB connection configuration"""
    host: str = "127.0.0.1"
    port: int = 7497  # Paper trading by default
    client_id: int = 1
    timeout: int = 10
    readonly: bool = False


class IbConnectionManager:
    """
    Manages connection to Interactive Brokers with proper cleanup and state tracking.
    
    Features:
    - Automatic retry with exponential backoff
    - Connection health monitoring
    - Graceful disconnect and cleanup
    - Connection state tracking
    - Global connection registry for cleanup
    """
    
    # Class-level connection registry to track all instances
    _active_connections: Dict[str, 'IbConnectionManager'] = {}
    _connection_lock = asyncio.Lock()
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        """Initialize connection manager with config."""
        self.config = config or ConnectionConfig()
        self.ib: Optional[IB] = None
        self._connected = False
        self._last_health_check = 0
        self._connection_attempts = 0
        self.connection_id = f"{self.config.host}:{self.config.port}:{self.config.client_id}"
        self.is_closing = False
        
        # Connection metrics
        self.metrics: Dict[str, Any] = {
            "total_connections": 0,
            "failed_connections": 0,
            "last_connect_time": None,
            "last_disconnect_time": None,
        }
        
        # Register this connection
        self._register_connection()
        
    def _register_connection(self):
        """Register this connection instance."""
        self._active_connections[self.connection_id] = self
        logger.debug(f"Registered connection {self.connection_id}")
        
    def _unregister_connection(self):
        """Unregister this connection instance."""
        if self.connection_id in self._active_connections:
            del self._active_connections[self.connection_id]
            logger.debug(f"Unregistered connection {self.connection_id}")
    
    @classmethod
    async def cleanup_all_connections(cls):
        """Clean up all active connections (useful for testing and shutdown)."""
        async with cls._connection_lock:
            if cls._active_connections:
                logger.info(f"Cleaning up {len(cls._active_connections)} active connections")
                connections = list(cls._active_connections.values())
                for connection in connections:
                    try:
                        await connection.disconnect()
                    except Exception as e:
                        logger.warning(f"Error disconnecting {connection.connection_id}: {e}")
                cls._active_connections.clear()
                logger.info("All connections cleaned up")
                
    @classmethod
    def get_active_connections(cls) -> Dict[str, 'IbConnectionManager']:
        """Get all active connections."""
        return cls._active_connections.copy()
        
    @classmethod
    def get_connection_count(cls) -> int:
        """Get the number of active connections."""
        return len(cls._active_connections)
    
    def __del__(self):
        """Ensure cleanup on object deletion."""
        try:
            if self._connected and self.ib:
                logger.warning(f"Connection {self.connection_id} not properly closed, forcing cleanup")
                self.ib.disconnect()
            self._unregister_connection()
        except Exception as e:
            logger.debug(f"Error in connection destructor: {e}")
        
    @retry_with_backoff(
        retryable_exceptions=ConnectionError,
        config=RetryConfig(max_retries=3, base_delay=2.0)
    )
    async def connect(self) -> None:
        """
        Connect to IB Gateway/TWS with retry logic.
        
        Raises:
            ConnectionError: If connection fails after all retries
        """
        if self._connected:
            logger.info("Already connected to IB")
            return
            
        self._connection_attempts += 1
        logger.info(
            f"Attempting IB connection #{self._connection_attempts} to "
            f"{self.config.host}:{self.config.port}"
        )
        
        try:
            self.ib = IB()
            
            # Connect with timeout
            await asyncio.wait_for(
                self.ib.connectAsync(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=self.config.client_id,
                    readonly=self.config.readonly
                ),
                timeout=self.config.timeout
            )
            
            self._connected = True
            self._connection_attempts = 0
            self.metrics["total_connections"] += 1
            self.metrics["last_connect_time"] = time.time()
            
            logger.info(
                f"Successfully connected to IB at {self.config.host}:{self.config.port}"
            )
            
        except asyncio.TimeoutError:
            self.metrics["failed_connections"] += 1
            raise ConnectionError(
                f"Connection timeout after {self.config.timeout}s",
                details={
                    "host": self.config.host,
                    "port": self.config.port,
                    "attempt": self._connection_attempts
                }
            )
        except Exception as e:
            self.metrics["failed_connections"] += 1
            raise ConnectionError(
                f"Failed to connect to IB: {str(e)}",
                details={
                    "host": self.config.host,
                    "port": self.config.port,
                    "error_type": type(e).__name__
                }
            )
    
    def connect_sync(self) -> None:
        """Synchronous wrapper for connect()."""
        util.run(self.connect())
    
    async def disconnect(self) -> None:
        """Gracefully disconnect from IB with proper cleanup."""
        if self.is_closing:
            return  # Already disconnecting
            
        self.is_closing = True
        
        try:
            if self._connected and self.ib:
                logger.info(f"Disconnecting from IB ({self.connection_id})...")
                self.ib.disconnect()
                self._connected = False
                self.metrics["last_disconnect_time"] = time.time()
                logger.info(f"Successfully disconnected from IB ({self.connection_id})")
            else:
                logger.debug("Not connected, nothing to disconnect")
                
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
        finally:
            self.ib = None
            self._connected = False
            self._unregister_connection()
            self.is_closing = False
            
    def disconnect_sync(self) -> None:
        """Synchronous wrapper for disconnect()."""
        if self.ib:
            util.run(self.disconnect())
    
    async def is_connected(self) -> bool:
        """
        Check if connected to IB.
        
        Performs actual connection test every 5 seconds to ensure
        connection is still alive.
        """
        if not self._connected or not self.ib:
            return False
            
        # Rate limit health checks
        now = time.time()
        if now - self._last_health_check < 5.0:
            return self._connected
            
        try:
            # Test connection with a simple request
            self._last_health_check = now
            await asyncio.wait_for(
                self.ib.reqCurrentTimeAsync(),
                timeout=2.0
            )
            return True
            
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Health check failed: {e}")
            self._connected = False
            return False
    
    def is_connected_sync(self) -> bool:
        """Synchronous wrapper for is_connected()."""
        if not self.ib:
            return False
        return util.run(self.is_connected())
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection status and metrics."""
        return {
            "connected": self._connected,
            "host": self.config.host,
            "port": self.config.port,
            "client_id": self.config.client_id,
            "metrics": self.metrics,
            "connection_attempts": self._connection_attempts
        }
    
    def __enter__(self):
        """Context manager entry."""
        self.connect_sync()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect_sync()
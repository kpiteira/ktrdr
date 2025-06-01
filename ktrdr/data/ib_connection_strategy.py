"""
Smart connection allocation strategy for IB operations.

This module provides intelligent connection management that allocates IB connections
based on operation context, ensuring optimal performance and avoiding conflicts.
"""

import threading
import time
from typing import Optional, Dict, Set, Any
from datetime import datetime, timezone
from contextlib import contextmanager

from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig
from ktrdr.config.ib_limits import IbLimitsRegistry
from ktrdr.config.ib_config import get_ib_config
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class IbConnectionStrategy:
    """
    Smart connection allocation based on operation context.
    
    Connection allocation strategy:
    - API calls: Use singleton connection (fast, shared)
    - Background gap filler: Use dedicated connection (isolated) 
    - Batch operations: Use single connection for entire batch
    - CLI operations: Use temporary connection with cleanup
    """
    
    def __init__(self):
        self._connections: Dict[str, IbConnectionSync] = {}
        self._connection_locks: Dict[str, threading.Lock] = {}
        self._temporary_connections: Set[str] = set()
        self._operation_counts: Dict[str, int] = {}
        self._last_cleanup = time.time()
        self._lock = threading.Lock()
        
        # Load IB configuration
        self._ib_config = get_ib_config()
        
    def get_connection_for_operation(self, operation_type: str, operation_id: Optional[str] = None) -> IbConnectionSync:
        """
        Get appropriate connection for given operation type.
        
        Args:
            operation_type: Type of operation ('api_call', 'gap_filler', 'batch', 'cli', 'test')
            operation_id: Optional unique ID for the operation
            
        Returns:
            IB connection suitable for the operation
            
        Raises:
            ConnectionError: If unable to establish connection
        """
        with self._lock:
            # For API calls, try to use the persistent connection manager first
            if operation_type == "api_call":
                try:
                    from ktrdr.data.ib_connection_manager import get_connection_manager
                    persistent_manager = get_connection_manager()
                    persistent_connection = persistent_manager.get_connection()
                    
                    if persistent_connection and persistent_connection.is_connected():
                        logger.debug(f"Using persistent connection for {operation_type}")
                        # Store it in our connections map for consistency
                        connection_key = "api_singleton"
                        self._connections[connection_key] = persistent_connection
                        return persistent_connection
                    else:
                        logger.debug(f"Persistent connection not available for {operation_type}, creating new one")
                except Exception as e:
                    logger.warning(f"Failed to get persistent connection: {e}, creating new one")
            
            # Determine connection key based on operation type
            connection_key = self._determine_connection_key(operation_type, operation_id)
            
            # Check if we already have a connection for this key
            if connection_key in self._connections:
                connection = self._connections[connection_key]
                if connection and connection.is_connected():
                    logger.debug(f"Reusing existing connection for {operation_type}: {connection_key}")
                    return connection
                else:
                    # Connection is stale, remove it
                    logger.warning(f"Removing stale connection: {connection_key}")
                    self._cleanup_connection(connection_key)
            
            # Create new connection
            connection = self._create_connection(operation_type, connection_key)
            
            # Store connection
            self._connections[connection_key] = connection
            self._connection_locks[connection_key] = threading.Lock()
            
            # Track operation count
            self._operation_counts[operation_type] = self._operation_counts.get(operation_type, 0) + 1
            
            logger.info(f"Created new connection for {operation_type}: {connection_key}")
            return connection
    
    def _determine_connection_key(self, operation_type: str, operation_id: Optional[str]) -> str:
        """Determine connection key based on operation type."""
        if operation_type == "api_call":
            # All API calls share a singleton connection
            return "api_singleton"
            
        elif operation_type == "gap_filler":
            # Gap filler gets its own dedicated connection
            return "gap_filler_dedicated"
            
        elif operation_type == "data_manager":
            # DataManager IB fallback gets its own connection
            return "data_manager_fallback"
            
        elif operation_type == "symbol_validation":
            # Symbol validation gets its own dedicated connection to avoid event loop conflicts
            return "symbol_validation_dedicated"
            
        elif operation_type == "batch":
            # Batch operations get unique connections per batch
            if operation_id:
                return f"batch_{operation_id}"
            else:
                return f"batch_{int(time.time())}"
                
        elif operation_type == "cli":
            # CLI operations get temporary connections
            if operation_id:
                connection_key = f"cli_{operation_id}"
            else:
                connection_key = f"cli_{int(time.time())}"
            self._temporary_connections.add(connection_key)
            return connection_key
            
        elif operation_type == "test":
            # Test operations get unique temporary connections
            connection_key = f"test_{operation_id or int(time.time())}"
            self._temporary_connections.add(connection_key)
            return connection_key
            
        else:
            # Unknown operation type gets temporary connection
            connection_key = f"unknown_{operation_type}_{int(time.time())}"
            self._temporary_connections.add(connection_key)
            return connection_key
    
    def _create_connection(self, operation_type: str, connection_key: str) -> IbConnectionSync:
        """Create new IB connection with appropriate client ID."""
        # Determine client ID based on operation type
        client_id = self._get_client_id(operation_type, connection_key)
        
        # Create connection config
        connection_config = ConnectionConfig(
            host=self._ib_config.host,
            port=self._ib_config.port,
            client_id=client_id,
            timeout=self._ib_config.timeout
        )
        
        # Create and connect
        connection = IbConnectionSync(connection_config)
        
        if not connection.is_connected():
            raise ConnectionError(f"Failed to establish IB connection for {operation_type} (client_id={client_id})")
        
        logger.info(f"Established IB connection: {connection_key} (client_id={client_id})")
        return connection
    
    def _get_client_id(self, operation_type: str, connection_key: str) -> int:
        """Get appropriate client ID for operation type."""
        try:
            if operation_type == "api_call":
                return IbLimitsRegistry.get_client_id_for_purpose("api_singleton", 0)
                
            elif operation_type == "gap_filler":
                return IbLimitsRegistry.get_client_id_for_purpose("gap_filler", 0)
                
            elif operation_type == "data_manager":
                return IbLimitsRegistry.get_client_id_for_purpose("data_manager", 0)
                
            elif operation_type == "symbol_validation":
                return IbLimitsRegistry.get_client_id_for_purpose("symbol_validation", 0)
                
            elif operation_type == "batch":
                # Use API pool for batch operations
                batch_index = len([k for k in self._connections.keys() if k.startswith("batch_")]) % 40
                return IbLimitsRegistry.get_client_id_for_purpose("api_pool", batch_index)
                
            elif operation_type == "cli":
                # Use CLI temporary range
                cli_index = len([k for k in self._connections.keys() if k.startswith("cli_")]) % 50
                return IbLimitsRegistry.get_client_id_for_purpose("cli_temporary", cli_index)
                
            elif operation_type == "test":
                # Use test range
                test_index = len([k for k in self._connections.keys() if k.startswith("test_")]) % 47
                return IbLimitsRegistry.get_client_id_for_purpose("test_connections", test_index)
                
            else:
                # Fallback to API pool
                return IbLimitsRegistry.get_client_id_for_purpose("api_pool", 0)
                
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to get client ID for {operation_type}: {e}. Using fallback.")
            # Fallback to simple incremental ID
            return 100 + len(self._connections)
    
    @contextmanager
    def connection_for_operation(self, operation_type: str, operation_id: Optional[str] = None):
        """
        Context manager for getting connection with automatic cleanup for temporary connections.
        
        Usage:
            with strategy.connection_for_operation('cli', 'my_operation') as connection:
                # Use connection
                data = fetcher.fetch_data(connection, ...)
        """
        connection = self.get_connection_for_operation(operation_type, operation_id)
        try:
            yield connection
        finally:
            # Cleanup temporary connections immediately
            connection_key = self._determine_connection_key(operation_type, operation_id)
            if connection_key in self._temporary_connections:
                self._cleanup_connection(connection_key)
    
    def cleanup_temporary_connections(self):
        """Clean up all temporary connections."""
        with self._lock:
            temp_keys = list(self._temporary_connections)
            for connection_key in temp_keys:
                self._cleanup_connection(connection_key)
            
            logger.info(f"Cleaned up {len(temp_keys)} temporary connections")
    
    def cleanup_idle_connections(self, max_idle_seconds: int = 3600):
        """Clean up connections that have been idle for too long."""
        current_time = time.time()
        
        # Only run cleanup every 5 minutes to avoid overhead
        if current_time - self._last_cleanup < 300:
            return
            
        with self._lock:
            idle_keys = []
            
            for connection_key, connection in self._connections.items():
                # Skip singleton connections (they should stay persistent)
                if connection_key in ["api_singleton", "gap_filler_dedicated", "data_manager_fallback"]:
                    continue
                    
                # Check if connection is idle (implement connection last-used tracking if needed)
                # For now, just clean up temporary connections older than max_idle_seconds
                if connection_key in self._temporary_connections:
                    # Extract timestamp from connection key if possible
                    try:
                        if "_" in connection_key:
                            timestamp_str = connection_key.split("_")[-1]
                            connection_time = float(timestamp_str)
                            if current_time - connection_time > max_idle_seconds:
                                idle_keys.append(connection_key)
                    except (ValueError, IndexError):
                        # If we can't parse timestamp, consider it old
                        idle_keys.append(connection_key)
            
            # Clean up idle connections
            for connection_key in idle_keys:
                self._cleanup_connection(connection_key)
            
            self._last_cleanup = current_time
            
            if idle_keys:
                logger.info(f"Cleaned up {len(idle_keys)} idle connections")
    
    def _cleanup_connection(self, connection_key: str):
        """Clean up a specific connection."""
        if connection_key in self._connections:
            connection = self._connections[connection_key]
            try:
                if connection and connection.is_connected():
                    connection.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting {connection_key}: {e}")
            
            # Remove from tracking
            del self._connections[connection_key]
            if connection_key in self._connection_locks:
                del self._connection_locks[connection_key]
            if connection_key in self._temporary_connections:
                self._temporary_connections.remove(connection_key)
            
            logger.debug(f"Cleaned up connection: {connection_key}")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get status of all managed connections."""
        with self._lock:
            status = {
                "total_connections": len(self._connections),
                "temporary_connections": len(self._temporary_connections),
                "operation_counts": self._operation_counts.copy(),
                "connections": {}
            }
            
            for connection_key, connection in self._connections.items():
                try:
                    is_connected = connection.is_connected() if connection else False
                    status["connections"][connection_key] = {
                        "connected": is_connected,
                        "client_id": getattr(connection.config, 'client_id', None) if connection else None,
                        "is_temporary": connection_key in self._temporary_connections
                    }
                except Exception as e:
                    status["connections"][connection_key] = {
                        "connected": False,
                        "error": str(e),
                        "is_temporary": connection_key in self._temporary_connections
                    }
            
            return status
    
    def force_cleanup_all(self):
        """Force cleanup of all connections (for shutdown)."""
        with self._lock:
            connection_keys = list(self._connections.keys())
            for connection_key in connection_keys:
                self._cleanup_connection(connection_key)
            
            logger.info(f"Force cleaned up all {len(connection_keys)} connections")
    
    def __del__(self):
        """Cleanup connections on object destruction."""
        try:
            self.force_cleanup_all()
        except Exception:
            pass  # Ignore errors during cleanup


# Global connection strategy instance
_connection_strategy: Optional[IbConnectionStrategy] = None
_strategy_lock = threading.Lock()


def get_connection_strategy() -> IbConnectionStrategy:
    """Get global connection strategy instance (singleton)."""
    global _connection_strategy
    
    if _connection_strategy is None:
        with _strategy_lock:
            if _connection_strategy is None:
                _connection_strategy = IbConnectionStrategy()
    
    return _connection_strategy


def cleanup_all_connections():
    """Cleanup all connections managed by the global strategy."""
    global _connection_strategy
    
    if _connection_strategy is not None:
        _connection_strategy.force_cleanup_all()
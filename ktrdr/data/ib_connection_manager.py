"""
Persistent IB Connection Manager

Manages a persistent connection to Interactive Brokers that:
- Connects automatically on startup
- Maintains connection health 
- Auto-reconnects on failure with sequential client IDs
- Runs independently of API requests
- Provides connection status to other components
"""

import threading
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from ktrdr.logging import get_logger
from ktrdr.config.ib_config import get_ib_config, IbConfig
from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig

logger = get_logger(__name__)


@dataclass
class ConnectionStatus:
    """Connection status information"""
    connected: bool = False
    client_id: Optional[int] = None
    host: Optional[str] = None
    port: Optional[int] = None
    last_connect_time: Optional[datetime] = None
    last_disconnect_time: Optional[datetime] = None
    connection_attempts: int = 0
    failed_attempts: int = 0
    current_attempt: int = 0
    next_retry_time: Optional[datetime] = None


class PersistentIbConnectionManager:
    """
    Manages a persistent IB connection that runs in the background.
    
    This manager:
    - Attempts to connect on startup
    - Maintains the connection independently of requests
    - Auto-reconnects on failure with sequential client IDs
    - Provides connection status and access to other components
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern - only one instance allowed."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the connection manager."""
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.config: Optional[IbConfig] = None
        self.connection: Optional[IbConnectionSync] = None
        self.status = ConnectionStatus()
        
        # Connection management
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Client ID management
        self._current_client_id = 1
        self._max_client_id = 50  # Reasonable limit
        self._client_id_lock = threading.Lock()
        
        # Retry configuration
        self._retry_delays = [5, 10, 30, 60, 120, 300]  # Progressive delays in seconds
        self._max_retry_delay = 300  # 5 minutes max
        
        logger.info("Initialized PersistentIbConnectionManager")
    
    def start(self) -> bool:
        """
        Start the persistent connection manager.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            logger.warning("Connection manager is already running")
            return True
            
        try:
            # Load IB configuration
            self.config = get_ib_config()
            logger.info(f"Loaded IB config: {self.config.host}:{self.config.port}")
            
            # Start the background thread
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._connection_loop, daemon=True)
            self._thread.start()
            
            logger.info("Started persistent IB connection manager")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start connection manager: {e}")
            self._running = False
            return False
    
    def stop(self) -> None:
        """Stop the persistent connection manager."""
        if not self._running:
            return
            
        logger.info("Stopping persistent IB connection manager...")
        self._running = False
        self._stop_event.set()
        
        # Disconnect current connection
        if self.connection:
            try:
                self.connection.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting: {e}")
            self.connection = None
        
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            
        # Update status
        self.status.connected = False
        self.status.last_disconnect_time = datetime.now(timezone.utc)
        
        logger.info("Stopped persistent IB connection manager")
    
    def _connection_loop(self) -> None:
        """Main connection management loop that runs in background thread."""
        logger.info("Starting connection management loop")
        
        while self._running and not self._stop_event.is_set():
            try:
                if not self.status.connected:
                    # Attempt to connect
                    self._attempt_connection()
                else:
                    # Check connection health
                    self._check_connection_health()
                
                # Wait before next iteration
                self._stop_event.wait(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in connection loop: {e}")
                self._stop_event.wait(30)  # Wait longer on error
        
        logger.info("Connection management loop ended")
    
    def _attempt_connection(self) -> None:
        """Attempt to establish IB connection with sequential client ID."""
        if self._stop_event.is_set():
            return
            
        # Check if we should retry yet
        if (self.status.next_retry_time and 
            datetime.now(timezone.utc) < self.status.next_retry_time):
            return
        
        # Get next client ID
        client_id = self._get_next_client_id()
        if client_id is None:
            logger.error("Exhausted all client IDs, waiting before reset...")
            self._reset_client_ids()
            self._schedule_retry(300)  # Wait 5 minutes before reset
            return
        
        logger.info(f"Attempting IB connection with client ID {client_id}")
        
        try:
            # Update status
            self.status.connection_attempts += 1
            self.status.current_attempt += 1
            
            # Create connection config
            conn_config = ConnectionConfig(
                host=self.config.host,
                port=self.config.port,
                client_id=client_id,
                timeout=self.config.timeout,
                readonly=self.config.readonly
            )
            
            # Attempt connection
            logger.info(f"🔄 Creating new IbConnectionSync with client ID {client_id}")
            new_connection = IbConnectionSync(conn_config)
            
            if new_connection.is_connected():
                # Success!
                logger.info(f"🔗 Assigning successful connection with client ID {client_id}")
                self.connection = new_connection
                self.status.connected = True
                self.status.client_id = client_id
                self.status.host = self.config.host
                self.status.port = self.config.port
                self.status.last_connect_time = datetime.now(timezone.utc)
                self.status.current_attempt = 0
                self.status.next_retry_time = None
                
                logger.info(f"✅ Successfully connected to IB with client ID {client_id}")
            else:
                # Connection failed
                self._handle_connection_failure("Connection check failed")
                
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Connection attempt failed: {error_msg}")
            
            # Check for specific errors that indicate client ID conflict
            if "already in use" in error_msg.lower() or "duplicate" in error_msg.lower():
                logger.info(f"Client ID {client_id} in use, will try next ID")
                # Don't reset retry delay for client ID conflicts
            else:
                self._handle_connection_failure(error_msg)
    
    def _check_connection_health(self) -> None:
        """Check if current connection is still healthy."""
        if not self.connection:
            self.status.connected = False
            return
        
        logger.debug("🩺 Running connection health check...")
            
        try:
            # Check basic connection state
            if not self.connection.is_connected():
                logger.warning("Connection lost (basic check), will attempt reconnection")
                self._mark_as_disconnected("Basic connection check failed")
                return
            
            # Additional check: verify transport is open
            # ib.isConnected() can return True even when transport is closed
            try:
                ib = self.connection.ib
                if hasattr(ib, 'client') and hasattr(ib.client, 'conn'):
                    conn = ib.client.conn
                    if not conn:
                        logger.warning("🔌 No client connection object, marking as lost")
                        self._mark_as_disconnected("No connection object")
                        return
                    elif hasattr(conn, 'is_closing') and conn.is_closing():
                        logger.warning("🔌 Transport is closing, marking connection as lost")
                        self._mark_as_disconnected("Transport closing")
                        return
                    else:
                        logger.debug(f"🔌 Transport check OK: conn={conn}, is_closing={getattr(conn, 'is_closing', 'N/A')}")
                else:
                    logger.debug("🔌 No client.conn attribute to check")
            except Exception as transport_e:
                logger.warning(f"🔌 Transport check failed: {transport_e}")
                self._mark_as_disconnected("Transport check error")
                return
                
        except Exception as e:
            logger.warning(f"Error checking connection health: {e}")
            self._mark_as_disconnected("Health check error")
    
    def _mark_as_disconnected(self, reason: str) -> None:
        """Mark connection as disconnected and clean up."""
        logger.info(f"Marking connection as disconnected: {reason}")
        self.status.connected = False
        self.status.last_disconnect_time = datetime.now(timezone.utc)
        if self.connection:
            try:
                self.connection.disconnect()
            except Exception:
                pass  # Ignore errors during cleanup
        self.connection = None
    
    def _handle_connection_failure(self, error_msg: str) -> None:
        """Handle connection failure and schedule retry."""
        self.status.failed_attempts += 1
        
        # Calculate retry delay (progressive backoff)
        retry_index = min(self.status.current_attempt - 1, len(self._retry_delays) - 1)
        retry_delay = self._retry_delays[retry_index] if retry_index >= 0 else self._max_retry_delay
        
        self._schedule_retry(retry_delay)
        
        logger.warning(
            f"Connection failed (attempt {self.status.current_attempt}): {error_msg}. "
            f"Next retry in {retry_delay}s"
        )
    
    def _schedule_retry(self, delay_seconds: int) -> None:
        """Schedule next retry attempt."""
        self.status.next_retry_time = (
            datetime.now(timezone.utc) + 
            timedelta(seconds=delay_seconds)
        )
    
    def _get_next_client_id(self) -> Optional[int]:
        """Get next client ID to try."""
        with self._client_id_lock:
            if self._current_client_id > self._max_client_id:
                return None
            
            client_id = self._current_client_id
            self._current_client_id += 1
            return client_id
    
    def _reset_client_ids(self) -> None:
        """Reset client ID sequence."""
        with self._client_id_lock:
            self._current_client_id = 1
            logger.info("Reset client ID sequence")
    
    def get_connection(self) -> Optional[IbConnectionSync]:
        """
        Get the current IB connection if available.
        
        Returns:
            IbConnectionSync instance if connected, None otherwise
        """
        if self.status.connected and self.connection:
            return self.connection
        return None
    
    def get_status(self) -> ConnectionStatus:
        """Get current connection status."""
        return self.status
    
    def is_connected(self) -> bool:
        """Check if currently connected to IB."""
        return self.status.connected
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get connection metrics."""
        return {
            "connected": self.status.connected,
            "client_id": self.status.client_id,
            "host": self.status.host,
            "port": self.status.port,
            "total_attempts": self.status.connection_attempts,
            "failed_attempts": self.status.failed_attempts,
            "current_attempt": self.status.current_attempt,
            "last_connect_time": self.status.last_connect_time,
            "last_disconnect_time": self.status.last_disconnect_time,
            "next_retry_time": self.status.next_retry_time,
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self.status.last_connect_time).total_seconds()
                if self.status.connected and self.status.last_connect_time
                else 0
            ),
        }


# Global instance
_connection_manager = None


def get_connection_manager() -> PersistentIbConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = PersistentIbConnectionManager()
    return _connection_manager


def start_connection_manager() -> bool:
    """Start the global connection manager."""
    return get_connection_manager().start()


def stop_connection_manager() -> None:
    """Stop the global connection manager."""
    manager = get_connection_manager()
    manager.stop()
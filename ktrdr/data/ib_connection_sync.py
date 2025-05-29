"""
Synchronous IB Connection Manager based on proven working pattern.
"""

import time
import random
from typing import Optional, Dict, Any
from dataclasses import dataclass
from ib_insync import IB
from ktrdr.logging import get_logger
from ktrdr.errors import ConnectionError

logger = get_logger(__name__)


@dataclass
class ConnectionConfig:
    """IB connection configuration"""
    host: str = "127.0.0.1"
    port: int = 7497  # Paper trading by default
    client_id: Optional[int] = None  # Will be randomized if not provided
    timeout: int = 15
    readonly: bool = False


class IbConnectionSync:
    """
    Synchronous IB connection manager based on proven working pattern.
    
    This implementation avoids async/await and event loop issues by using
    synchronous connections throughout.
    """
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        """Initialize connection manager with config."""
        self.config = config or ConnectionConfig()
        
        # Generate random client ID if not provided
        if self.config.client_id is None:
            self.config.client_id = random.randint(1000, 9999)
            logger.info(f"Generated random client ID: {self.config.client_id}")
        
        self.ib = IB()
        self.connected = False
        
        # Connection metrics
        self.metrics: Dict[str, Any] = {
            "total_connections": 0,
            "failed_connections": 0,
            "last_connect_time": None,
            "last_disconnect_time": None,
        }
        
        # Try to connect on initialization
        try:
            self._connect()
        except Exception as e:
            logger.error(f"Initial connection failed: {e}")
            logger.warning("You can still use local data, but IB features will not be available.")
    
    def _connect(self, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """
        Connect to IB Gateway/TWS with retry logic.
        
        Returns:
            True if connected successfully, False otherwise
        """
        retries = 0
        logger.debug(f"Attempting to connect to IB with max_retries={max_retries}, retry_delay={retry_delay}")
        
        while retries < max_retries:
            try:
                logger.info(
                    f"Connecting to IB at {self.config.host}:{self.config.port} "
                    f"with client ID {self.config.client_id} (attempt {retries+1}/{max_retries})..."
                )
                
                # Use synchronous connect
                self.ib.connect(
                    self.config.host, 
                    self.config.port, 
                    clientId=self.config.client_id,
                    readonly=self.config.readonly,
                    timeout=self.config.timeout
                )
                
                if self.ib.isConnected():
                    logger.info("Successfully connected to IB")
                    self.connected = True
                    self.metrics["total_connections"] += 1
                    self.metrics["last_connect_time"] = time.time()
                    return True
                    
            except Exception as e:
                logger.error(f"Connection attempt failed: {e}")
                self.metrics["failed_connections"] += 1
                retries += 1
                if retries < max_retries:
                    time.sleep(retry_delay)
        
        logger.error("Failed to connect to IB after all retries")
        return False
    
    def ensure_connection(self) -> bool:
        """
        Ensure we have an active connection, reconnecting if necessary.
        
        Returns:
            True if connected, False otherwise
        """
        if self.connected and self.ib.isConnected():
            return True
        
        logger.info("Reconnecting to IB...")
        return self._connect()
    
    def is_connected(self) -> bool:
        """Check if connected to IB."""
        return self.ib.isConnected()
    
    def disconnect(self) -> None:
        """Disconnect from IB."""
        if self.ib.isConnected():
            logger.info(f"Disconnecting from IB (client ID: {self.config.client_id})...")
            self.ib.disconnect()
            self.connected = False
            self.metrics["last_disconnect_time"] = time.time()
            logger.info("Successfully disconnected from IB")
        else:
            logger.debug("Not connected, nothing to disconnect")
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection status and metrics."""
        return {
            "connected": self.is_connected(),
            "host": self.config.host,
            "port": self.config.port,
            "client_id": self.config.client_id,
            "metrics": self.metrics
        }
    
    def __enter__(self):
        """Context manager entry."""
        self.ensure_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def __del__(self):
        """Ensure cleanup on deletion."""
        try:
            if self.ib and self.ib.isConnected():
                logger.warning(f"Connection not properly closed for client ID {self.config.client_id}, forcing cleanup")
                self.ib.disconnect()
        except Exception as e:
            logger.debug(f"Error in destructor: {e}")
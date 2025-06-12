"""
Synchronous IB Connection Manager based on proven working pattern.
"""

import time
import random
from typing import Optional, Dict, Any
from dataclasses import dataclass
from ib_insync import IB, util
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
        self._event_loop: Optional[Any] = None  # Keep reference to event loop
        self._connection_thread: Optional[Any] = None  # Keep reference to connection thread

        # Connection metrics
        self.metrics: Dict[str, Any] = {
            "total_connections": 0,
            "failed_connections": 0,
            "last_connect_time": None,
            "last_disconnect_time": None,
            "last_error": None,
            "callback_events": 0,
        }

        # Set up callback handlers for error detection and pacing monitoring
        self._setup_callback_handlers()

        # Try to connect on initialization
        try:
            self._connect()
        except Exception as e:
            logger.error(f"Initial connection failed: {e}")
            logger.warning(
                "You can still use local data, but IB features will not be available."
            )

    def _setup_callback_handlers(self) -> None:
        """Set up minimal IB callback event handlers to avoid connection resets."""
        logger.debug(
            f"Setting up minimal callback handlers for client ID {self.config.client_id}"
        )

        # Minimal error event handler - with pacing detection
        def on_error(reqId, errorCode, errorString, contract):
            logger.warning(f"IB Error {errorCode} (reqId: {reqId}): {errorString}")
            self.metrics["callback_events"] += 1
            self.metrics["last_error"] = {
                "reqId": reqId,
                "errorCode": errorCode,
                "errorString": errorString,
                "time": time.time(),
            }

            # Detect pacing violations (IB error codes for rate limiting)
            if errorCode in [162, 165, 200, 354]:  # Common pacing error codes
                logger.warning(
                    f"🚦 IB pacing violation detected: {errorCode} - {errorString}"
                )
                self.metrics["pacing_violations"] = (
                    self.metrics.get("pacing_violations", 0) + 1
                )

        # Minimal connection handlers - avoid setting self.connected here
        def on_connected():
            logger.info(f"IB connection callback for client ID {self.config.client_id}")
            self.metrics["callback_events"] += 1

        def on_disconnected():
            logger.info(
                f"IB disconnection callback for client ID {self.config.client_id}"
            )
            self.metrics["callback_events"] += 1
            self.metrics["last_disconnect_time"] = time.time()

        # Register minimal event handlers
        self.ib.errorEvent += on_error
        self.ib.connectedEvent += on_connected
        self.ib.disconnectedEvent += on_disconnected

        logger.debug("Minimal callback handlers registered")

    def _connect(self, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """
        Connect to IB Gateway/TWS with retry logic.

        Returns:
            True if connected successfully, False otherwise
        """
        retries = 0
        logger.debug(
            f"Attempting to connect to IB with max_retries={max_retries}, retry_delay={retry_delay}"
        )

        while retries < max_retries:
            try:
                logger.info(
                    f"Connecting to IB at {self.config.host}:{self.config.port} "
                    f"with client ID {self.config.client_id} (attempt {retries+1}/{max_retries})..."
                )

                # Use ib_insync's recommended approach for event loop handling
                self._connect_simple()

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

    def _connect_simple(self) -> None:
        """Simple connection using thread-based approach for all contexts."""
        # Always use thread-based connection to avoid event loop conflicts
        # This works reliably in all contexts: FastAPI, background threads, etc.
        logger.debug("Using thread-based IB connection for maximum compatibility")
        self._connect_in_thread()

    def _connect_in_thread(self) -> None:
        """Connect to IB in a separate thread to avoid event loop conflicts."""
        import threading
        import asyncio
        from ib_insync import util
        
        connection_result = {"success": False, "error": None, "loop": None}
        
        def thread_connect():
            """Connection function to run in thread."""
            try:
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                connection_result["loop"] = loop
                
                async def _do_connect():
                    """Async connect function."""
                    await self.ib.connectAsync(
                        self.config.host,
                        self.config.port,
                        clientId=self.config.client_id,
                        readonly=self.config.readonly,
                        timeout=self.config.timeout,
                    )
                
                # Run the connection in the new event loop
                loop.run_until_complete(_do_connect())
                connection_result["success"] = True
                
                # Keep the loop running for ongoing operations
                logger.debug(f"Connection established, keeping event loop running for client {self.config.client_id}")
                
                # Run the event loop forever to keep the connection alive
                # This is what ib_insync needs - a running event loop
                loop.run_forever()
                
            except Exception as e:
                connection_result["error"] = str(e)
                # Only close loop on error
                try:
                    if "loop" in locals():
                        loop.close()
                        asyncio.set_event_loop(None)
                except:
                    pass
        
        # Run connection in separate thread as daemon so it doesn't block shutdown
        thread = threading.Thread(target=thread_connect, daemon=True)
        thread.start()
        
        # Wait for connection to complete, but don't join the thread (let it run)
        import time
        timeout = self.config.timeout + 5
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if connection_result["success"] or connection_result["error"]:
                break
            time.sleep(0.1)
        
        if not connection_result["success"] and not connection_result["error"]:
            raise ConnectionError("Connection timed out in thread")
            
        if not connection_result["success"]:
            error = connection_result.get("error", "Unknown thread connection error")
            raise ConnectionError(f"Thread connection failed: {error}")
            
        # Store the event loop reference for later use
        self._event_loop = connection_result["loop"]
        self._connection_thread = thread  # Store thread reference for cleanup
        logger.debug(f"Stored event loop and thread references for client {self.config.client_id}")

    def _connect_with_event_loop(self) -> None:
        """Connect to IB with simplified event loop handling."""
        import asyncio

        async def _do_connect_async():
            """Async function to connect to IB."""
            await self.ib.connectAsync(
                self.config.host,
                self.config.port,
                clientId=self.config.client_id,
                readonly=self.config.readonly,
                timeout=self.config.timeout,
            )

        # Create event loop for this connection attempt only
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Connect using the loop
            loop.run_until_complete(_do_connect_async())

            # Keep loop reference but don't close it yet - ib_insync needs it
            self._event_loop = loop
            logger.debug(f"Event loop created for client ID {self.config.client_id}")

        except Exception as e:
            # Clean up loop on failure
            try:
                if "loop" in locals():
                    loop.close()
                asyncio.set_event_loop(None)
            except:
                pass
            # Re-raise with more context
            raise ConnectionError(f"IB connection failed: {e}")

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
        """Disconnect from IB and clean up event loop."""
        if self.ib.isConnected():
            logger.info(
                f"Disconnecting from IB (client ID: {self.config.client_id})..."
            )
            self.ib.disconnect()
            self.connected = False
            self.metrics["last_disconnect_time"] = time.time()
            logger.info("Successfully disconnected from IB")
        else:
            logger.debug("Not connected, nothing to disconnect")

        # Clean up event loop and thread
        if self._event_loop and not self._event_loop.is_closed():
            try:
                logger.info(
                    f"Stopping event loop for client ID {self.config.client_id}"
                )
                # Stop the event loop if it's running
                self._event_loop.call_soon_threadsafe(self._event_loop.stop)
                
                # Wait a bit for the loop to stop, then close it
                import time as time_module
                time_module.sleep(0.1)
                
                if not self._event_loop.is_closed():
                    self._event_loop.close()
                self._event_loop = None
                
                logger.info(f"Event loop stopped for client ID {self.config.client_id}")
            except Exception as e:
                logger.warning(f"Error cleaning up event loop: {e}")
                self._event_loop = None
                
        # Clean up thread reference
        self._connection_thread = None

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection status and metrics."""
        return {
            "connected": self.is_connected(),
            "host": self.config.host,
            "port": self.config.port,
            "client_id": self.config.client_id,
            "metrics": self.metrics,
        }

    def __enter__(self):
        """Context manager entry."""
        self.ensure_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def __del__(self):
        """Ensure cleanup on deletion to prevent connection leaks."""
        try:
            if self.ib and self.ib.isConnected():
                logger.warning(
                    f"🧹 Cleaning up leaked connection for client ID {self.config.client_id}"
                )
                # Re-enabled: We MUST disconnect to prevent connection leaks in IB Gateway
                try:
                    self.ib.disconnect()
                    logger.info(
                        f"✅ Successfully cleaned up connection for client ID {self.config.client_id}"
                    )
                except Exception as disconnect_error:
                    logger.error(
                        f"❌ Error during destructor disconnect for client ID {self.config.client_id}: {disconnect_error}"
                    )
            else:
                logger.debug(
                    f"🧹 Clean destructor for client ID {self.config.client_id} (was already disconnected)"
                )
        except Exception as e:
            logger.debug(f"Error in destructor: {e}")

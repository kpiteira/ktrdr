"""
IB Connection with Dedicated Thread

This module provides the IbConnection class that maintains a persistent connection
to Interactive Brokers Gateway/TWS using a dedicated thread with its own event loop.

Key Features:
- Dedicated thread with persistent event loop (solves async context destruction issue)
- 3-minute idle timeout with automatic cleanup
- Thread-safe request execution using asyncio communication
- Proper connection lifecycle management
- Comprehensive error handling and logging

This design solves the core issue where IB connections were dying silently because
async API contexts would destroy event loops and TCP transports when they ended.
"""

import threading
import asyncio
import time
import queue
import concurrent.futures
from typing import Any, Callable, Optional, Tuple
from concurrent.futures import Future
from dataclasses import dataclass

from ib_insync import IB

from ktrdr.logging import get_logger
from ktrdr.logging.config import should_sample_log
from .error_classifier import IbErrorClassifier, IbErrorType

logger = get_logger(__name__)


@dataclass
class ConnectionRequest:
    """Request to be executed by IB connection thread"""

    func: Callable
    args: tuple
    kwargs: dict
    request_id: str
    result_future: Optional[Future] = None
    timestamp: Optional[float] = None

    def __post_init__(self):
        if self.result_future is None:
            import concurrent.futures

            self.result_future = concurrent.futures.Future()
        if self.timestamp is None:
            self.timestamp = time.time()


class IbConnection:
    """
    IB connection with dedicated thread and persistent event loop.

    This class maintains a persistent connection to IB Gateway/TWS by running
    the connection in its own dedicated thread with a persistent event loop.
    This prevents the connection from being destroyed when async API contexts end.

    Features:
    - Dedicated thread prevents event loop destruction
    - 3-minute idle timeout with automatic cleanup
    - Thread-safe request execution
    - Proper error handling and retry logic
    - Connection health monitoring
    """

    def __init__(self, client_id: int, host: str = "localhost", port: int = 4002):
        """
        Initialize IB connection.

        Args:
            client_id: Unique client ID for IB connection
            host: IB Gateway/TWS host
            port: IB Gateway/TWS port
        """
        self.client_id = client_id
        self.host = host
        self.port = port

        # IB connection instance
        self.ib = IB()

        # Threading components
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.stop_event = threading.Event()

        # Request queue for thread-safe communication
        self.request_queue: queue.Queue[ConnectionRequest] = queue.Queue()

        # Connection state
        self.connected = False
        self.last_activity = time.time()
        self.idle_timeout = 180.0  # 3 minutes
        self.connection_timeout = 15.0  # IB connection timeout

        # Statistics
        self.requests_processed = 0
        self.errors_encountered = 0

        # Sleep/wake detection
        self.last_health_check = time.time()

        logger.info(f"IbConnection {self.client_id} initialized for {host}:{port}")

    def start(self) -> bool:
        """
        Start connection thread with persistent event loop.

        Returns:
            True if thread started successfully, False otherwise
        """
        if self.thread and self.thread.is_alive():
            logger.warning(f"Connection {self.client_id} already running")
            return True

        try:
            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self._run_sync_loop,
                name=f"IbConnection-{self.client_id}",
                daemon=True,
            )
            self.thread.start()

            # Wait briefly for thread to start
            time.sleep(0.1)

            logger.info(f"IbConnection {self.client_id} thread started")
            return True

        except Exception as e:
            logger.error(f"Failed to start IbConnection {self.client_id}: {e}")
            return False

    def _run_sync_loop(self):
        """
        Run synchronous connection loop in dedicated thread.

        This method runs a purely synchronous loop without asyncio,
        allowing ib_insync to create its own event loop for connections.
        """
        logger.debug(f"_run_sync_loop starting for connection {self.client_id}")

        # No event loop! Let ib_insync handle its own event loop
        self.loop = None

        try:
            logger.debug(f"Starting synchronous connection loop for {self.client_id}")
            self._sync_connection_loop()
            logger.debug(f"Synchronous connection loop completed for {self.client_id}")

        except Exception as e:
            logger.error(f"Connection {self.client_id} sync loop failed: {e}")
            logger.error(f"Exception type: {type(e)}")
            self.errors_encountered += 1

        finally:
            logger.debug(f"Sync loop ending for {self.client_id}")
            self.loop = None

    def _sync_connection_loop(self):
        """
        Main synchronous connection loop - connect to IB and process requests.

        This is the core loop that maintains the IB connection and processes
        incoming requests from other threads in a thread-safe manner.
        No event loops - purely synchronous operation.
        """
        logger.debug(f" _sync_connection_loop starting for {self.client_id}")

        try:
            # Establish IB connection
            logger.debug(f" Connecting to IB for {self.client_id}")
            self._connect_to_ib_sync()
            logger.debug(f" IB connection established for {self.client_id}")

            # Process requests until stop is requested
            logger.debug(f" Starting request processing for {self.client_id}")
            self._process_requests_sync()
            logger.debug(f" Request processing ended for {self.client_id}")

        except Exception as e:
            logger.error(f"Connection {self.client_id} loop failed: {e}")
            logger.error(f"Exception type: {type(e)}")
            self.errors_encountered += 1

        finally:
            # Always disconnect cleanly
            logger.debug(f" Disconnecting from IB for {self.client_id}")
            self._disconnect_from_ib_sync()

    def _connect_to_ib_sync(self):
        """Connect to IB Gateway/TWS synchronously with dedicated event loop"""
        logger.debug(f" Connecting to IB (client_id={self.client_id})")

        try:
            # Create fresh event loop for this thread - ib_insync needs one
            import asyncio

            try:
                # Try to get existing loop (should be None in sync thread)
                loop = asyncio.get_event_loop()
                logger.debug(f" {loop}")
            except RuntimeError:
                # No event loop in this thread - create one
                logger.debug(f" No event loop found, creating new one")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Use synchronous connect - ib_insync will use the event loop we just created
            self.ib.connect(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=10.0,
                readonly=False,
            )

            # Wait for connection to stabilize
            time.sleep(2.0)

            if self.ib.isConnected():
                self.connected = True
                self.last_activity = time.time()
                logger.debug(
                    f" IB connection {self.client_id} established successfully"
                )
            else:
                raise ConnectionError(
                    f"Failed to establish IB connection {self.client_id}"
                )

        except Exception as e:
            logger.error(f"Failed to connect to IB (client_id={self.client_id}): {e}")
            logger.debug(
                f"DEBUG: Connection attempt failed - host={self.host}, port={self.port}, client_id={self.client_id}"
            )
            logger.debug(
                f"DEBUG: IB instance state - connected={self.ib.isConnected() if self.ib else 'No IB instance'}"
            )
            raise

    def _disconnect_from_ib_sync(self):
        """Disconnect from IB Gateway/TWS synchronously"""
        import asyncio

        try:
            if self.ib:
                # ALWAYS attempt disconnect, regardless of isConnected() state
                # isConnected() can lie about connection state, leaving zombies on IB Gateway
                logger.debug(f" Disconnecting from IB (client_id={self.client_id})")
                self.ib.disconnect()
                logger.debug(f" Disconnected from IB (client_id={self.client_id})")

                # Give disconnect time to complete
                time.sleep(0.5)
            else:
                logger.debug(
                    f" No IB instance to disconnect (client_id={self.client_id})"
                )
        except Exception as e:
            logger.error(
                f"Error disconnecting from IB (client_id={self.client_id}): {e}"
            )
        finally:
            self.connected = False

            # CRITICAL: Properly close the event loop to ensure clean TCP disconnection
            # This matches what happens during container shutdown and ensures
            # IB Gateway sees the connection as properly closed
            try:
                loop = asyncio.get_event_loop()
                if loop and not loop.is_closed():
                    logger.debug(f" Closing event loop for connection {self.client_id}")
                    loop.close()
                    logger.debug(f" Event loop closed for connection {self.client_id}")
            except Exception as e:
                logger.debug(
                    f" Event loop cleanup error for connection {self.client_id}: {e}"
                )
                # Not critical - continue cleanup

    def _process_requests_sync(self):
        """Process incoming requests synchronously"""
        logger.debug(
            f" Connection {self.client_id} entering synchronous request processing loop"
        )

        while not self.stop_event.is_set():
            try:
                # Check for idle timeout
                if time.time() - self.last_activity > self.idle_timeout:
                    logger.debug(
                        f" Connection {self.client_id} idle timeout ({self.idle_timeout}s)"
                    )
                    break

                # Check for pending requests (blocking with timeout)
                try:
                    request = self.request_queue.get(timeout=1.0)
                    logger.debug(f" {request.request_id}")
                    self.last_activity = time.time()
                    self._execute_request_sync(request)

                except queue.Empty:
                    continue  # Normal timeout, check idle and loop again

            except Exception as e:
                logger.error(
                    f"Request processing error in connection {self.client_id}: {e}"
                )
                self.errors_encountered += 1
                time.sleep(1.0)  # Brief pause on error

        logger.debug(
            f" Connection {self.client_id} exiting synchronous request processing loop"
        )

    def _execute_request_sync(self, request: ConnectionRequest):
        """Execute a single request synchronously"""
        logger.debug(
            f"Executing sync request {request.request_id} for connection {self.client_id}: {request.func.__name__}"
        )

        try:
            # Ensure event loop is available for ib_insync calls
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                logger.debug(f"Using existing event loop: {loop}")
            except RuntimeError:
                logger.debug(f"Creating event loop for request execution")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Execute the function with provided arguments - purely synchronous
            logger.debug(f"Calling sync function {request.func.__name__}")
            result = request.func(*request.args, **request.kwargs)

            logger.debug(f"Function {request.func.__name__} completed successfully")

            # Return successful result
            request.result_future.set_result(result)
            self.requests_processed += 1

            logger.debug(f"Request {request.request_id} completed successfully")

        except Exception as e:
            # Return error to caller
            logger.error(f"Sync request {request.request_id} execution failed: {e}")
            logger.error(f"Exception type: {type(e)}")
            request.result_future.set_exception(e)
            self.errors_encountered += 1

    async def _connect_to_ib(self):
        """Connect to IB Gateway/TWS with proper error handling"""
        max_retries = 1  # Reduced from 3 - fail fast

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Connecting to IB (client_id={self.client_id}, attempt={attempt + 1})"
                )

                await self.ib.connectAsync(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    timeout=self.connection_timeout,
                )

                # Wait for IB synchronization to complete before marking as ready
                logger.debug(
                    f"IB connection {self.client_id} connected, waiting for sync..."
                )

                # Give IB time to fully synchronize (API ready + market data farms)
                await asyncio.sleep(2.0)  # Conservative wait for synchronization

                self.connected = True
                self.last_activity = time.time()

                logger.info(f"IB connection {self.client_id} established successfully")
                return

            except Exception as e:
                self.errors_encountered += 1
                error_type, wait_time = IbErrorClassifier.classify(0, str(e))

                logger.warning(
                    f"IB connection {self.client_id} attempt {attempt + 1} failed: {e}"
                )

                if attempt < max_retries - 1:
                    if wait_time > 0:
                        logger.info(f"Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to connect after {max_retries} attempts")
                    raise

    async def _process_requests(self):
        """
        Process incoming requests and handle idle timeout.

        This method runs the main request processing loop, handling both
        incoming requests and idle timeout monitoring.
        """
        logger.debug(f" Connection {self.client_id} entering request processing loop")

        loop_iteration = 0
        while not self.stop_event.is_set():
            loop_iteration += 1

            # Use log sampling to reduce noise (log every 500th iteration)
            if should_sample_log(f"processing_loop_{self.client_id}", 500):
                logger.debug(
                    f"Connection {self.client_id} processing loop iteration {loop_iteration}"
                )

            try:
                # Check for idle timeout
                if time.time() - self.last_activity > self.idle_timeout:
                    logger.debug(
                        f"Connection {self.client_id} idle timeout ({self.idle_timeout}s)"
                    )
                    break

                # Check for pending requests (non-blocking with timeout)
                # Removed verbose queue checking log to reduce noise
                try:
                    request = self.request_queue.get(timeout=1.0)
                    logger.debug(
                        f"Connection {self.client_id} processing request: {request.func.__name__}"
                    )
                    self.last_activity = time.time()
                    await self._execute_request(request)

                except queue.Empty:
                    continue  # Normal timeout, check idle and loop again

            except Exception as e:
                logger.error(
                    f"Request processing error in connection {self.client_id}: {e}"
                )
                self.errors_encountered += 1
                await asyncio.sleep(1.0)  # Brief pause on error

        logger.debug(f"Connection {self.client_id} exiting request processing loop")

    async def _execute_request(self, request: ConnectionRequest):
        """
        Execute a single request and return result to caller.

        Args:
            request: Request object containing function and parameters
        """
        logger.debug(
            f"Executing request {request.request_id} for connection {self.client_id}: {request.func.__name__}"
        )

        try:
            # Execute the function with provided arguments
            if asyncio.iscoroutinefunction(request.func):
                logger.debug(f" Calling async function {request.func.__name__}")
                result = await request.func(*request.args, **request.kwargs)
            else:
                logger.debug(f" Calling sync function {request.func.__name__}")
                result = request.func(*request.args, **request.kwargs)

            logger.debug(f" Function {request.func.__name__} completed successfully")

            # Return successful result
            request.result_future.set_result(result)
            self.requests_processed += 1

            logger.debug(f" Request {request.request_id} completed successfully")

        except Exception as e:
            # Return error to caller
            logger.error(f"Async request {request.request_id} execution failed: {e}")
            logger.error(f"Exception type: {type(e)}")
            request.result_future.set_exception(e)
            self.errors_encountered += 1

    async def _disconnect_from_ib(self):
        """Disconnect from IB Gateway/TWS cleanly"""
        try:
            if self.ib and self.ib.isConnected():
                logger.info(f"Disconnecting IB connection {self.client_id}")
                self.ib.disconnect()
                await asyncio.sleep(0.5)  # Allow clean disconnect

        except Exception as e:
            logger.warning(
                f"Error during IB disconnect for connection {self.client_id}: {e}"
            )

        finally:
            self.connected = False
            logger.info(f"IB connection {self.client_id} disconnected")

    def execute_sync_request(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute synchronous IB request in the connection's dedicated thread.

        Uses the queue-based system to submit requests to the connection thread
        for proper thread isolation and synchronous execution.

        Args:
            func: Function to execute with IB connection
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result of function execution
        """
        logger.debug(
            f" Starting execute_sync_request for {func.__name__} on connection {self.client_id}"
        )

        # Health check (simplified for sync approach)
        if not self.thread or not self.thread.is_alive():
            logger.error(f"Connection {self.client_id} thread not alive")
            raise ConnectionError("Connection thread not alive")

        if not self.ib or not self.ib.isConnected():
            logger.error(f"Connection {self.client_id} not connected to IB")
            raise ConnectionError("Connection not connected to IB")

        logger.debug(f" Connection {self.client_id} health check passed")

        # Create a ConnectionRequest and submit to queue
        request = ConnectionRequest(
            func=func,
            args=(self.ib,) + args,  # Prepend self.ib to args
            kwargs=kwargs,
            request_id=f"{func.__name__}_{int(time.time() * 1000)}",
        )

        logger.debug(f" Created request {request.request_id}, submitting to queue")

        try:
            # Submit request to the connection thread's queue
            self.request_queue.put(request, timeout=5.0)
            logger.debug(
                f" Request {request.request_id} submitted to queue successfully"
            )

            # Wait for result from the connection thread
            logger.debug(f" Waiting for result from request {request.request_id}")
            result = request.result_future.result(timeout=30.0)
            logger.debug(f" Got result from request {request.request_id} successfully")
            return result

        except queue.Full:
            logger.error(f"Request queue full for connection {self.client_id}")
            raise ConnectionError(f"Request queue full for connection {self.client_id}")
        except concurrent.futures.TimeoutError:
            logger.error(
                f"Timeout waiting for result from request {request.request_id}"
            )
            raise ConnectionError(f"Request timeout for connection {self.client_id}")
        except Exception as e:
            logger.error(f"Request {request.request_id} failed: {e}")
            raise

    async def execute_request(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute IB request in connection thread (thread-safe).

        This method allows other threads to safely execute IB API calls
        by submitting them to the connection's dedicated thread.

        Args:
            func: Function to execute with IB connection
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result of function execution

        Raises:
            ConnectionError: If connection is not healthy
            Exception: Any exception raised by the executed function
        """
        if not self.is_healthy():
            raise ConnectionError(f"IB connection {self.client_id} is not healthy")

        # Create future for result
        result_future = Future()

        # Create request object
        request = ConnectionRequest(
            func=func,
            args=args,
            kwargs=kwargs,
            result_future=result_future,
            timestamp=time.time(),
        )

        # Submit to connection thread
        try:
            self.request_queue.put(request, timeout=5.0)
            logger.debug(f"Request queued for connection {self.client_id}")

        except queue.Full:
            raise ConnectionError(f"Request queue full for connection {self.client_id}")

        # Wait for result with timeout
        try:
            result = result_future.result(timeout=30.0)  # 30 second timeout
            return result

        except TimeoutError:
            raise ConnectionError(f"Request timeout for connection {self.client_id}")

    def _detect_potential_sleep_wake(self) -> bool:
        """
        Detect if system may have entered sleep mode since last health check.

        This uses wall clock time comparison to detect significant time jumps
        that typically indicate system sleep/wake cycles.

        Returns:
            True if potential sleep/wake detected, False otherwise
        """
        current_time = time.time()
        time_since_last_check = current_time - self.last_health_check

        # If more than 2 minutes have passed since last health check,
        # system may have slept (normal health checks happen more frequently)
        potential_sleep = time_since_last_check > 120  # 2 minutes threshold

        if potential_sleep:
            logger.warning(
                f"Connection {self.client_id}: Potential sleep/wake detected "
                f"({time_since_last_check:.1f}s since last health check)"
            )

        self.last_health_check = current_time
        return potential_sleep

    def is_healthy(self) -> bool:
        """
        Check if connection is healthy and operational.

        Performs both basic health checks and active validation to detect
        sleep-corrupted connections where ib.isConnected() returns True
        but the connection is actually dead.

        Returns:
            True if connection is healthy, False otherwise
        """
        # Basic health checks
        basic_health = (
            self.thread is not None
            and self.thread.is_alive()
            and not self.stop_event.is_set()
            and self.connected
            and self.ib is not None
            and self.ib.isConnected()
            and time.time() - self.last_activity < self.idle_timeout
        )

        if not basic_health:
            return False

        # Check for potential sleep/wake cycle
        potential_sleep = self._detect_potential_sleep_wake()

        # Active validation to detect sleep-corrupted connections
        # This is especially important after potential sleep/wake cycles
        # where ib.isConnected() returns True but connection is actually dead
        try:
            # Quick validation: managedAccounts() is lightweight and cached
            # If this succeeds, the connection is truly functional
            accounts = self.ib.managedAccounts()

            if potential_sleep:
                logger.info(
                    f"Connection {self.client_id}: Active validation passed after potential sleep/wake"
                )

            return True  # Connection is genuinely healthy
        except Exception as e:
            # Connection appears connected but is actually corrupted
            # This commonly happens after system sleep/wake cycles
            if potential_sleep:
                logger.warning(
                    f"Connection {self.client_id}: Active validation failed after potential sleep/wake: {e}"
                )
            else:
                logger.debug(
                    f"Connection {self.client_id}: Active validation failed: {e}"
                )
            return False

    def stop(self, timeout: float = 5.0):
        """
        Stop connection gracefully.

        Args:
            timeout: Maximum time to wait for clean shutdown
        """
        logger.info(f"Stopping IB connection {self.client_id}")

        # Signal stop
        self.stop_event.set()

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)

            if self.thread.is_alive():
                logger.warning(
                    f"Connection {self.client_id} thread did not stop gracefully"
                )
            else:
                logger.info(f"Connection {self.client_id} stopped cleanly")

        self.thread = None

    def get_stats(self) -> dict:
        """
        Get connection statistics.

        Returns:
            Dictionary with connection statistics
        """
        return {
            "client_id": self.client_id,
            "connected": self.connected,
            "healthy": self.is_healthy(),
            "requests_processed": self.requests_processed,
            "errors_encountered": self.errors_encountered,
            "last_activity": self.last_activity,
            "seconds_since_activity": time.time() - self.last_activity,
            "idle_timeout": self.idle_timeout,
            "thread_alive": self.thread.is_alive() if self.thread else False,
            "ib_connected": self.ib.isConnected() if self.ib else False,
            "queue_size": self.request_queue.qsize(),
        }

    def __str__(self) -> str:
        """String representation of connection"""
        return f"IbConnection(client_id={self.client_id}, healthy={self.is_healthy()})"

    def __repr__(self) -> str:
        """Detailed string representation"""
        return (
            f"IbConnection(client_id={self.client_id}, host={self.host}, "
            f"port={self.port}, healthy={self.is_healthy()})"
        )

"""
IB Connection Pool

Simple connection pool that manages IbConnection instances without complex
client ID registries or purpose enums. Uses a straightforward approach:
- Try sequential client IDs on conflicts
- Remove unhealthy connections automatically
- Create new connections on demand
- Thread-safe operations with asyncio locks

This design prioritizes simplicity and reliability over complex optimization.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Optional

from ktrdr.logging import get_logger

from .connection import IbConnection
from .error_classifier import IbErrorClassifier, IbErrorType

logger = get_logger(__name__)


class IbConnectionPool:
    """
    Simple connection pool that manages IbConnection instances.

    Features:
    - No client ID registry - just try sequential IDs on conflicts
    - Automatic cleanup of unhealthy connections
    - Thread-safe operations using asyncio locks
    - Simple connection acquisition and release
    - Connection health monitoring

    This pool removes the complexity of the previous implementation while
    maintaining the essential functionality for connection reuse.
    """

    def __init__(
        self, host: str = "localhost", port: int = 4002, max_connections: int = 5
    ):
        """
        Initialize connection pool.

        Args:
            host: IB Gateway/TWS host
            port: IB Gateway/TWS port
            max_connections: Maximum number of concurrent connections
        """
        self.host = host
        self.port = port
        self.max_connections = max_connections

        # Connection management
        self.connections: list[IbConnection] = []
        self.lock = asyncio.Lock()

        # Client ID management (simple sequential approach)
        self.next_client_id = 1
        self.max_client_id_attempts = (
            3  # Conservative limit to avoid overwhelming IB Gateway
        )

        # Statistics
        self.connections_created = 0
        self.connections_reused = 0
        self.cleanup_count = 0

        logger.info(
            f"IbConnectionPool initialized for {host}:{port} (max_connections={max_connections})"
        )

    async def acquire_connection(self, timeout: float = 30.0) -> IbConnection:
        """
        Get a healthy connection from the pool or create a new one.

        Args:
            timeout: Maximum time to wait for connection

        Returns:
            Healthy IbConnection instance

        Raises:
            ConnectionError: If unable to acquire connection within timeout
        """
        start_time = time.time()

        async with self.lock:
            # First, try to find an existing healthy connection
            healthy_conn = await self._find_healthy_connection()
            if healthy_conn:
                self.connections_reused += 1
                logger.debug(f"Reusing existing connection {healthy_conn.client_id}")
                return healthy_conn

            # Clean up unhealthy connections
            await self._cleanup_unhealthy_connections()

            # Check if we can create a new connection
            if len(self.connections) >= self.max_connections:
                raise ConnectionError(
                    f"Connection pool exhausted: {len(self.connections)}/{self.max_connections} connections"
                )

            # Create new connection
            elapsed = time.time() - start_time
            remaining_timeout = timeout - elapsed

            if remaining_timeout <= 0:
                raise ConnectionError("Timeout while acquiring connection")

            connection = await self._create_new_connection(remaining_timeout)

            self.connections.append(connection)
            self.connections_created += 1

            logger.info(
                f"Created new connection {connection.client_id} (pool size: {len(self.connections)})"
            )
            return connection

    async def _find_healthy_connection(self) -> Optional[IbConnection]:
        """Find an existing healthy connection in the pool"""
        for conn in self.connections:
            if conn.is_healthy():
                return conn
        return None

    async def _cleanup_unhealthy_connections(self):
        """Remove unhealthy connections from the pool"""
        healthy_connections = []

        for conn in self.connections:
            if conn.is_healthy():
                healthy_connections.append(conn)
            else:
                logger.debug(f"Removing unhealthy connection {conn.client_id}")
                try:
                    conn.stop(timeout=2.0)  # Quick stop for cleanup
                except Exception as e:
                    logger.warning(
                        f"Error stopping unhealthy connection {conn.client_id}: {e}"
                    )
                self.cleanup_count += 1

        self.connections = healthy_connections

    async def _handle_sleep_recovery(self):
        """
        Handle recovery after system sleep/wake by clearing all connections.

        After system sleep, connections may appear healthy but be corrupted.
        This method proactively clears all connections to force fresh ones.
        """
        if not self.connections:
            return

        logger.info(
            "Sleep/wake recovery: Clearing all connections to prevent accumulation"
        )

        # Stop all existing connections
        for conn in self.connections:
            try:
                conn.stop(timeout=1.0)  # Quick stop
            except Exception as e:
                logger.debug(
                    f"Error stopping connection {conn.client_id} during sleep recovery: {e}"
                )

        # Clear the pool
        self.connections.clear()
        self.cleanup_count += len(self.connections)

        logger.info("Sleep/wake recovery complete: All connections cleared")

    async def _create_new_connection(self, timeout: float) -> IbConnection:
        """
        Create a new IB connection with automatic client ID handling.

        Args:
            timeout: Maximum time to wait for connection

        Returns:
            New IbConnection instance

        Raises:
            ConnectionError: If unable to create connection
        """
        start_time = time.time()

        for attempt in range(self.max_client_id_attempts):
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise ConnectionError("Timeout while creating connection")

            client_id = self.next_client_id
            self.next_client_id += 1

            try:
                logger.debug(f"Creating connection with client_id={client_id}")

                # Create and start connection
                connection = IbConnection(client_id, self.host, self.port)

                if not connection.start():
                    logger.warning(
                        f"Failed to start connection thread for client_id={client_id}"
                    )
                    # Wait before trying next client ID to avoid overwhelming IB Gateway
                    await asyncio.sleep(1.0)
                    continue

                # Wait for connection to establish (with timeout)
                remaining_time = timeout - (time.time() - start_time)
                await self._wait_for_connection_ready(
                    connection, min(remaining_time, 20.0)
                )

                if connection.is_healthy():
                    logger.info(f"Successfully created connection {client_id}")
                    return connection
                else:
                    logger.warning(f"Connection {client_id} failed health check")
                    logger.debug(
                        f"DEBUG: Failed connection state - host={self.host}:{self.port}, connected={connection.connected}"
                    )
                    logger.debug(
                        f"DEBUG: Failed connection stats - errors={connection.errors_encountered}, thread_alive={connection.thread.is_alive() if connection.thread else False}"
                    )
                    connection.stop(timeout=2.0)
                    # Wait before trying next client ID to avoid overwhelming IB Gateway
                    await asyncio.sleep(2.0)

            except Exception as e:
                error_type, wait_time = IbErrorClassifier.classify(0, str(e))

                # Check if it's a client ID conflict
                if IbErrorClassifier.is_client_id_conflict(str(e)):
                    logger.debug(f"Client ID {client_id} conflict, trying next ID")
                    continue

                # For other errors, decide whether to retry
                if error_type == IbErrorType.FATAL:
                    logger.error(f"Fatal error creating connection: {e}")
                    raise ConnectionError(f"Fatal error: {e}")

                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")

                # Wait before retry if suggested
                if wait_time > 0 and time.time() - start_time + wait_time < timeout:
                    await asyncio.sleep(min(wait_time, 5.0))

        raise ConnectionError(
            f"Failed to create connection after {self.max_client_id_attempts} attempts"
        )

    async def _wait_for_connection_ready(
        self, connection: IbConnection, timeout: float
    ):
        """
        Wait for connection to become ready.

        Args:
            connection: Connection to wait for
            timeout: Maximum time to wait
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if connection.is_healthy():
                return
            await asyncio.sleep(0.1)

        logger.warning(
            f"Connection {connection.client_id} not ready within {timeout:.1f}s"
        )
        logger.debug(
            f"DEBUG: Connection state - connected={connection.connected}, thread_alive={connection.thread.is_alive() if connection.thread else False}"
        )
        logger.debug(
            f"DEBUG: Connection stats - requests_processed={connection.requests_processed}, errors={connection.errors_encountered}"
        )

    @asynccontextmanager
    async def get_connection(self):
        """
        Context manager for connection acquisition and automatic release.

        Usage:
            async with pool.get_connection() as conn:
                result = await conn.execute_request(some_function, args)
        """
        logger.debug("Acquiring connection from pool")
        connection = await self.acquire_connection()
        logger.debug(f"Connection {connection.client_id} acquired successfully")
        try:
            yield connection
        finally:
            # Note: We don't explicitly release connections since they
            # auto-timeout after 3 minutes. This simplifies the design.
            logger.debug(f"Releasing connection {connection.client_id}")
            pass

    async def execute_with_connection_sync(self, func, *args, **kwargs):
        """
        Execute a synchronous function with an acquired connection.

        For use with synchronous IB API calls to avoid async/await issues.

        Args:
            func: Function to execute (should be synchronous)
            *args: Arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result of function execution
        """
        logger.debug(
            f"Starting execute_with_connection_sync for {func.__name__}"
        )  # Only log first 2 args to avoid clutter

        try:
            logger.debug("Acquiring connection for sync execution")
            async with self.get_connection() as conn:
                logger.debug(
                    f"Got connection {conn.client_id}, calling execute_sync_request"
                )
                result = conn.execute_sync_request(func, *args, **kwargs)
                logger.debug("execute_sync_request completed successfully")
                return result
        except Exception as e:
            logger.error(f"execute_with_connection_sync failed: {e}")
            raise

    async def execute_with_connection(self, func, *args, **kwargs):
        """
        Execute a function with an acquired connection.

        Args:
            func: Function to execute
            *args: Arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result of function execution
        """
        async with self.get_connection() as conn:
            return await conn.execute_request(func, *args, **kwargs)

    def get_pool_stats(self) -> dict:
        """
        Get pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        healthy_count = sum(1 for conn in self.connections if conn.is_healthy())

        return {
            "total_connections": len(self.connections),
            "healthy_connections": healthy_count,
            "unhealthy_connections": len(self.connections) - healthy_count,
            "max_connections": self.max_connections,
            "next_client_id": self.next_client_id,
            "connections_created": self.connections_created,
            "connections_reused": self.connections_reused,
            "cleanup_count": self.cleanup_count,
            "host": self.host,
            "port": self.port,
        }

    def get_connection_stats(self) -> list[dict]:
        """
        Get statistics for all connections in the pool.

        Returns:
            List of connection statistics
        """
        return [conn.get_stats() for conn in self.connections]

    async def cleanup_all(self):
        """
        Clean up all connections in the pool.

        This method stops all connections and clears the pool.
        Useful for shutdown or testing scenarios.
        """
        async with self.lock:
            logger.info(
                f"Cleaning up all connections in pool ({len(self.connections)} connections)"
            )

            for conn in self.connections:
                try:
                    conn.stop(timeout=3.0)
                except Exception as e:
                    logger.warning(f"Error stopping connection {conn.client_id}: {e}")

            self.connections.clear()
            self.cleanup_count += len(self.connections)

            logger.info("All connections cleaned up")

    async def health_check(self) -> dict:
        """
        Perform health check on the pool.

        Returns:
            Health check results
        """
        async with self.lock:
            await self._cleanup_unhealthy_connections()

            stats = self.get_pool_stats()
            healthy_count = stats["healthy_connections"]
            total_count = stats["total_connections"]

            return {
                "healthy": healthy_count > 0,
                "healthy_connections": healthy_count,
                "total_connections": total_count,
                "pool_utilization": (
                    healthy_count / self.max_connections
                    if self.max_connections > 0
                    else 0
                ),
                "can_create_new": total_count < self.max_connections,
                "next_client_id": self.next_client_id,
            }

    def __str__(self) -> str:
        """String representation of pool"""
        return f"IbConnectionPool({len(self.connections)}/{self.max_connections} connections)"

    def __repr__(self) -> str:
        """Detailed string representation"""
        return (
            f"IbConnectionPool(host={self.host}, port={self.port}, "
            f"connections={len(self.connections)}/{self.max_connections})"
        )

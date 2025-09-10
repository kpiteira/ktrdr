"""
KTRDR Unified Cancellation System

Provides a unified cancellation framework that integrates with ServiceOrchestrator
patterns while maintaining compatibility with existing AsyncDataLoader implementations.

Key Components:
- CancellationToken: Protocol for cancellation checking
- AsyncCancellationToken: Thread-safe implementation
- CancellationState: Thread-safe state management
- CancellationCoordinator: Centralized cancellation management
- ServiceOrchestrator integration patterns

This system consolidates cancellation logic from AsyncDataLoader and provides
a foundation for unified cancellation across all KTRDR operations.
"""

import asyncio
import threading
import uuid
from abc import abstractmethod
from collections.abc import Awaitable
from typing import Any, Callable, Optional, Protocol

from ktrdr.logging import get_logger

logger = get_logger(__name__)


class CancellationToken(Protocol):
    """
    Protocol for cancellation tokens used across KTRDR operations.

    This protocol is compatible with both ServiceOrchestrator patterns
    and AsyncDataLoader job cancellation patterns.
    """

    @abstractmethod
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        ...

    @abstractmethod
    def cancel(self, reason: str = "Operation cancelled") -> None:
        """Request cancellation with optional reason."""
        ...

    @abstractmethod
    async def wait_for_cancellation(self) -> None:
        """Async wait for cancellation signal."""
        ...

    @property
    @abstractmethod
    def is_cancelled_requested(self) -> bool:
        """
        Compatibility property for ServiceOrchestrator integration.

        Maps to is_cancelled() for backward compatibility.
        """
        ...


class CancellationError(Exception):
    """Exception raised when an operation is cancelled."""

    def __init__(
        self,
        message: str,
        operation_id: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        super().__init__(message)
        self.operation_id = operation_id
        self.reason = reason


class CancellationState:
    """
    Thread-safe cancellation state management.

    Manages both individual operation cancellation and global cancellation
    using proper synchronization primitives.
    """

    def __init__(self):
        self._cancelled = False
        self._global_cancelled = False
        self._reason: Optional[str] = None
        self._lock = threading.RLock()
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        """Check if operation is cancelled (individual or global)."""
        with self._lock:
            return self._cancelled or self._global_cancelled

    @property
    def is_global_cancelled(self) -> bool:
        """Check if global cancellation is active."""
        with self._lock:
            return self._global_cancelled

    @property
    def reason(self) -> Optional[str]:
        """Get cancellation reason."""
        with self._lock:
            return self._reason

    def cancel(self, reason: str = "Operation cancelled") -> None:
        """Cancel this specific operation."""
        with self._lock:
            if not self._cancelled and not self._global_cancelled:
                self._cancelled = True
                self._reason = reason
                logger.debug(f"Operation cancelled: {reason}")

                # Notify async waiters (thread-safe)
                try:
                    loop = asyncio.get_running_loop()
                    loop.call_soon_threadsafe(self._event.set)
                except RuntimeError:
                    # No running loop, set event directly
                    if hasattr(self._event, "_loop") and self._event._loop:
                        self._event.set()

    def set_global_cancelled(self, reason: str = "Global cancellation") -> None:
        """Set global cancellation state."""
        with self._lock:
            if not self._global_cancelled:
                self._global_cancelled = True
                # Only update reason if not already set
                if not self._reason:
                    self._reason = reason
                logger.debug(f"Global cancellation set: {reason}")

                # Notify async waiters (thread-safe)
                try:
                    loop = asyncio.get_running_loop()
                    loop.call_soon_threadsafe(self._event.set)
                except RuntimeError:
                    # No running loop, set event directly
                    if hasattr(self._event, "_loop") and self._event._loop:
                        self._event.set()

    async def wait(self) -> None:
        """Async wait for cancellation."""
        if self.is_cancelled:
            return
        await self._event.wait()


class AsyncCancellationToken:
    """
    Thread-safe async cancellation token implementation.

    Compatible with both ServiceOrchestrator patterns and AsyncDataLoader
    job cancellation patterns.
    """

    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self._state = CancellationState()

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._state.is_cancelled

    @property
    def is_cancelled_requested(self) -> bool:
        """Compatibility property for ServiceOrchestrator integration."""
        return self.is_cancelled()

    def cancel(self, reason: str = "Operation cancelled") -> None:
        """Request cancellation with reason."""
        self._state.cancel(reason)
        logger.info(
            f"Cancellation requested for operation {self.operation_id}: {reason}"
        )

    async def wait_for_cancellation(self) -> None:
        """Async wait for cancellation signal."""
        await self._state.wait()

    def check_cancellation(self, context: str = "") -> None:
        """
        Check cancellation and raise exception if cancelled.

        Args:
            context: Optional context information for better error messages

        Raises:
            CancellationError: If operation has been cancelled
        """
        if self.is_cancelled():
            message_parts = [f"Operation {self.operation_id} cancelled"]
            if context:
                message_parts.append(f"at {context}")
            if self.reason:
                message_parts.append(f"({self.reason})")

            raise CancellationError(
                ": ".join(message_parts),
                operation_id=self.operation_id,
                reason=self.reason,
            )

    @property
    def reason(self) -> Optional[str]:
        """Get cancellation reason."""
        return self._state.reason

    def set_global_cancelled(self, reason: str = "Global cancellation") -> None:
        """Set global cancellation for this token."""
        self._state.set_global_cancelled(reason)


class CancellationCoordinator:
    """
    Centralized coordination of cancellation across all operations.

    Manages multiple operations, supports global cancellation, and provides
    integration points for CLI interrupt handling and ServiceOrchestrator patterns.
    """

    def __init__(self):
        self._tokens: dict[str, AsyncCancellationToken] = {}
        self._global_state = CancellationState()
        self._lock = threading.RLock()
        logger.debug("CancellationCoordinator initialized")

    def create_token(self, operation_id: str) -> AsyncCancellationToken:
        """
        Create a new cancellation token for an operation.

        Args:
            operation_id: Unique identifier for the operation

        Returns:
            AsyncCancellationToken instance registered with coordinator
        """
        token = AsyncCancellationToken(operation_id)

        with self._lock:
            self._tokens[operation_id] = token

            # Apply global cancellation if active
            if self._global_state.is_cancelled:
                token.set_global_cancelled(
                    self._global_state.reason or "Global cancellation active"
                )

        logger.debug(f"Created cancellation token for operation {operation_id}")
        return token

    def cancel_operation(
        self, operation_id: str, reason: str = "Operation cancelled"
    ) -> bool:
        """
        Cancel a specific operation.

        Args:
            operation_id: Operation to cancel
            reason: Cancellation reason

        Returns:
            True if operation was found and cancelled, False if not found
        """
        with self._lock:
            if operation_id in self._tokens:
                self._tokens[operation_id].cancel(reason)
                logger.info(f"Cancelled operation {operation_id}: {reason}")
                return True
            else:
                logger.debug(f"Operation {operation_id} not found for cancellation")
                return False

    def cancel_all_operations(self, reason: str = "Global cancellation") -> None:
        """
        Cancel all registered operations.

        Args:
            reason: Global cancellation reason
        """
        with self._lock:
            # Set global cancellation state
            self._global_state.set_global_cancelled(reason)

            # Cancel all existing operations
            for operation_id, token in self._tokens.items():
                token.set_global_cancelled(reason)
                logger.debug(f"Globally cancelled operation {operation_id}")

            logger.info(
                f"Global cancellation applied to {len(self._tokens)} operations: {reason}"
            )

    def _cleanup_token(self, operation_id: str) -> None:
        """
        Clean up completed operation token.

        Args:
            operation_id: Operation to clean up
        """
        with self._lock:
            if operation_id in self._tokens:
                del self._tokens[operation_id]
                logger.debug(f"Cleaned up token for operation {operation_id}")

    async def execute_with_cancellation(
        self,
        operation_id: str,
        operation_func: Callable[[CancellationToken], Awaitable[Any]],
        operation_name: str = "operation",
    ) -> Any:
        """
        Execute an operation with unified cancellation support.

        This method integrates with ServiceOrchestrator patterns while providing
        enhanced cancellation capabilities from AsyncDataLoader patterns.

        Args:
            operation_id: Unique identifier for this operation execution
            operation_func: Async function that takes a CancellationToken
            operation_name: Human-readable name for logging

        Returns:
            Result of the operation

        Raises:
            CancellationError: If operation is cancelled
        """
        logger.debug(
            f"Starting {operation_name} (id: {operation_id}) with cancellation support"
        )

        # Create token for this operation
        token = self.create_token(operation_id)

        try:
            # Check if already globally cancelled
            if self._global_state.is_cancelled:
                raise CancellationError(
                    f"Operation {operation_name} cancelled before start: {self._global_state.reason}",
                    operation_id=operation_id,
                    reason=self._global_state.reason,
                )

            # Execute the operation
            result = await operation_func(token)

            logger.debug(f"Completed {operation_name} (id: {operation_id})")
            return result

        except CancellationError:
            logger.info(
                f"Operation {operation_name} (id: {operation_id}) was cancelled"
            )
            raise
        except Exception as e:
            logger.error(f"Operation {operation_name} (id: {operation_id}) failed: {e}")
            raise
        finally:
            # Clean up token
            self._cleanup_token(operation_id)

    def get_status(self) -> dict[str, Any]:
        """
        Get coordinator status for monitoring and debugging.

        Returns:
            Dictionary with coordinator status information
        """
        with self._lock:
            return {
                "active_operations": len(self._tokens),
                "global_cancelled": self._global_state.is_cancelled,
                "global_reason": self._global_state.reason,
                "operations": list(self._tokens.keys()),
            }


# Global coordinator instance for system-wide cancellation management
_global_coordinator: Optional[CancellationCoordinator] = None


def get_global_coordinator() -> CancellationCoordinator:
    """
    Get the global cancellation coordinator instance.

    Returns:
        Global CancellationCoordinator instance (creates if needed)
    """
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = CancellationCoordinator()
    return _global_coordinator


def create_cancellation_token(
    operation_id: Optional[str] = None,
    coordinator: Optional[CancellationCoordinator] = None,
) -> AsyncCancellationToken:
    """
    Factory function for creating cancellation tokens.

    Args:
        operation_id: Optional operation ID (generates UUID if not provided)
        coordinator: Optional coordinator (uses global if not provided)

    Returns:
        AsyncCancellationToken instance
    """
    if operation_id is None:
        operation_id = f"op-{uuid.uuid4().hex[:8]}"

    if coordinator is None:
        coordinator = get_global_coordinator()

    return coordinator.create_token(operation_id)


def cancel_all_operations(reason: str = "System shutdown") -> None:
    """
    Cancel all operations globally.

    This function provides a convenient way to cancel all operations,
    typically used for system shutdown or emergency cancellation.

    Args:
        reason: Cancellation reason
    """
    coordinator = get_global_coordinator()
    coordinator.cancel_all_operations(reason)


def setup_cli_cancellation_handler():
    """
    Set up CLI cancellation handlers for KeyboardInterrupt (Ctrl+C).

    This integrates the cancellation system with CLI interrupt handling,
    ensuring that Ctrl+C properly cancels all running operations.
    """
    import signal

    def handle_interrupt(signum, frame):
        logger.info("KeyboardInterrupt received, cancelling all operations...")
        cancel_all_operations("User requested cancellation (Ctrl+C)")

    signal.signal(signal.SIGINT, handle_interrupt)
    logger.info("CLI cancellation handler registered for KeyboardInterrupt")

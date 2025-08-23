"""
Circuit breaker pattern for IB operations to handle silent connections gracefully.

This prevents cascading failures when IB operations consistently timeout,
providing fast-fail behavior and automatic recovery.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from ktrdr import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3  # Lower threshold for faster detection
    recovery_timeout: float = 30.0  # Shorter recovery time
    success_threshold: int = 2  # Fewer successes needed
    timeout: float = 15.0  # Shorter timeout for faster diagnosis


class CircuitBreaker:
    """Circuit breaker for IB operations."""

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.next_attempt_time = 0

        logger.info(f"Circuit breaker '{name}' initialized: {self.config}")

    async def __call__(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""

        # Check if circuit is open and we haven't waited long enough
        if self.state == CircuitState.OPEN:
            if time.time() < self.next_attempt_time:
                raise CircuitBreakerOpenError(
                    f"🚨 IB Gateway Connection Problem Detected!\n\n"
                    f"The '{self.name}' operation has failed {self.failure_count} times consecutively.\n"
                    f"This indicates an UNRECOVERABLE IB Gateway issue.\n\n"
                    f"REQUIRED ACTION:\n"
                    f"1. Check IB Gateway/TWS is running and logged in\n"
                    f"2. Restart IB Gateway if needed\n"
                    f"3. Check port forwarding (Docker: host.docker.internal:4003)\n"
                    f"4. Verify API settings are enabled in IB Gateway\n\n"
                    f"System will retry automatically in {self.next_attempt_time - time.time():.0f} seconds."
                )
            else:
                # Time to try again
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")

        try:
            # Execute the function with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.config.timeout
            )

            # Success - handle state transitions
            await self._handle_success()
            return result

        except (asyncio.TimeoutError, Exception) as e:
            # Failure - handle state transitions
            await self._handle_failure(e)
            raise

    async def _handle_success(self):
        """Handle successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                # Enough successes - close the circuit
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(
                    f"Circuit breaker '{self.name}' CLOSED - recovery successful"
                )
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    async def _handle_failure(self, error: Exception):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery - go back to open
            self.state = CircuitState.OPEN
            self.next_attempt_time = time.time() + self.config.recovery_timeout
            logger.warning(
                f"Circuit breaker '{self.name}' failed during recovery - back to OPEN. "
                f"Error: {error}"
            )
        elif self.failure_count >= self.config.failure_threshold:
            # Too many failures - open the circuit
            self.state = CircuitState.OPEN
            self.next_attempt_time = time.time() + self.config.recovery_timeout
            logger.error(
                f"Circuit breaker '{self.name}' OPENED after {self.failure_count} failures. "
                f"Last error: {error}"
            )

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "next_attempt_time": (
                self.next_attempt_time if self.state == CircuitState.OPEN else None
            ),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
            },
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


# Global circuit breakers for different IB operations
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str, config: CircuitBreakerConfig = None
) -> CircuitBreaker:
    """Get or create a circuit breaker for an operation."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """Get all active circuit breakers."""
    return _circuit_breakers.copy()


async def with_circuit_breaker(name: str, func: Callable, *args, **kwargs) -> Any:
    """Execute function with circuit breaker protection."""
    breaker = get_circuit_breaker(name)
    return await breaker(func, *args, **kwargs)

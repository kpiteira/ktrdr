"""
IB Pace Manager

Unified pace violation management for Interactive Brokers operations.

This manager provides:
- Centralized pace violation detection and recovery
- Enhanced error 162 classification with head timestamp awareness
- Proactive pace limiting for all IB operations
- Request rate monitoring and throttling
- Intelligent retry strategies with backoff
- Integration with existing error handling

Key Features:
- Integrates existing IbErrorHandler functionality
- Enhanced error classification using head timestamp data
- Centralized pace monitoring across all components
- Configurable pace limits and retry strategies
- Comprehensive metrics and monitoring
- Thread-safe operations for concurrent use
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Optional, Set, Any, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from contextlib import asynccontextmanager

from ktrdr.logging import get_logger
from ktrdr.config.ib_limits import IbLimitsRegistry
from ktrdr.data.ib_error_handler import IbErrorHandler, IbErrorInfo, IbErrorType
from ktrdr.utils.timezone_utils import TimestampManager

logger = get_logger(__name__)


class PaceViolationType(Enum):
    """Types of pace violations."""

    FREQUENCY_LIMIT = "frequency_limit"  # Too many requests in time window
    IDENTICAL_REQUEST = "identical_request"  # Same request too soon
    BURST_LIMIT = "burst_limit"  # Too many requests in short burst
    MINIMUM_DELAY = "minimum_delay"  # Not enough delay between requests
    IB_ERROR_162 = "ib_error_162"  # IB error 162 pace violation
    IB_ERROR_165 = "ib_error_165"  # IB error 165 pace violation


@dataclass
class PaceViolationEvent:
    """Information about a pace violation event."""

    violation_type: PaceViolationType
    timestamp: float
    request_key: str
    wait_time: float
    retry_count: int = 0
    resolved: bool = False
    resolution_time: Optional[float] = None

    def mark_resolved(self):
        """Mark the violation as resolved."""
        self.resolved = True
        self.resolution_time = time.time()

    def get_duration(self) -> float:
        """Get duration of the violation in seconds."""
        end_time = self.resolution_time or time.time()
        return end_time - self.timestamp


@dataclass
class RequestMetrics:
    """Metrics for request tracking."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    pace_violations: int = 0
    total_wait_time: float = 0.0
    avg_request_interval: float = 0.0
    last_request_time: float = 0.0

    def record_request(self, success: bool, wait_time: float = 0.0):
        """Record a request."""
        current_time = time.time()

        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.total_wait_time += wait_time

        # Update average interval
        if self.last_request_time > 0:
            interval = current_time - self.last_request_time
            self.avg_request_interval = (
                self.avg_request_interval * (self.total_requests - 1) + interval
            ) / self.total_requests

        self.last_request_time = current_time

    def record_pace_violation(self):
        """Record a pace violation."""
        self.pace_violations += 1


class IbPaceManager:
    """
    Unified pace violation management for all IB operations.

    This manager integrates and enhances the existing IbErrorHandler with:
    - Proactive pace limiting before requests
    - Enhanced error classification
    - Centralized violation tracking
    - Intelligent retry strategies
    - Comprehensive monitoring
    """

    _instance: Optional["IbPaceManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "IbPaceManager":
        """Singleton pattern for global access."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the pace manager."""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        # Thread safety
        self._pace_lock = threading.RLock()

        # Core error handler integration
        self.error_handler = IbErrorHandler()

        # Request tracking
        self._request_history: List[tuple] = []  # (timestamp, request_key)
        self._identical_request_cache: Dict[str, float] = {}  # request_key -> last_time
        self._last_request_time: float = 0.0

        # Pace violation tracking
        self._active_violations: Dict[str, PaceViolationEvent] = {}
        self._violation_history: List[PaceViolationEvent] = []
        self._max_violation_history = 1000

        # Component-specific metrics
        self._component_metrics: Dict[str, RequestMetrics] = {}

        # Configuration
        self._enable_proactive_limiting = True
        self._enable_enhanced_classification = True
        self._max_history_age = 600  # 10 minutes

        # Async support
        self._async_locks: Dict[str, asyncio.Lock] = {}

        logger.info("IbPaceManager initialized with enhanced error handling")

    async def check_pace_limits_async(
        self,
        symbol: str,
        timeframe: str,
        component: str,
        operation: str = "data_request",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> None:
        """
        Async version of proactive pace checking.

        Args:
            symbol: Symbol being requested
            timeframe: Timeframe being requested
            component: Component making the request
            operation: Type of operation
            start_date: Optional start date for context
            end_date: Optional end date for context
        """
        if not self._enable_proactive_limiting:
            return

        # Set request context for better error classification
        if start_date and end_date:
            self.error_handler.set_request_context(
                symbol, start_date, end_date, timeframe
            )

        # Create request key
        request_key = self._create_request_key(
            symbol, timeframe, operation, start_date, end_date
        )

        # Check pace limits
        wait_time = await self._calculate_required_wait_async(request_key, component)

        if wait_time > 0:
            await self._handle_pace_wait_async(request_key, wait_time, component)

        # Record the request
        self._record_request(request_key, component)

    def check_pace_limits_sync(
        self,
        symbol: str,
        timeframe: str,
        component: str,
        operation: str = "data_request",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> None:
        """
        Synchronous version of proactive pace checking.

        Args:
            symbol: Symbol being requested
            timeframe: Timeframe being requested
            component: Component making the request
            operation: Type of operation
            start_date: Optional start date for context
            end_date: Optional end date for context
        """
        if not self._enable_proactive_limiting:
            return

        # Set request context for better error classification
        if start_date and end_date:
            self.error_handler.set_request_context(
                symbol, start_date, end_date, timeframe
            )

        # Create request key
        request_key = self._create_request_key(
            symbol, timeframe, operation, start_date, end_date
        )

        # Check pace limits
        wait_time = self._calculate_required_wait_sync(request_key, component)

        if wait_time > 0:
            self._handle_pace_wait_sync(request_key, wait_time, component)

        # Record the request
        self._record_request(request_key, component)

    async def handle_ib_error_async(
        self,
        error_code: int,
        error_message: str,
        component: str,
        request_key: Optional[str] = None,
        req_id: Optional[int] = None,
    ) -> tuple[bool, float]:
        """
        Async version of IB error handling with enhanced classification.

        Args:
            error_code: IB error code
            error_message: IB error message
            component: Component that received the error
            request_key: Optional request key for context
            req_id: Optional IB request ID

        Returns:
            Tuple of (should_retry, wait_time_seconds)
        """
        # Use enhanced error classification
        error_info = self.error_handler.classify_error(
            error_code, error_message, use_context=self._enable_enhanced_classification
        )

        # Record metrics
        self._record_error(component, error_info)

        # Handle pace violations specifically
        if error_info.error_type == IbErrorType.PACING_VIOLATION:
            await self._handle_pace_violation_async(
                error_code, error_message, component, request_key
            )

        # Log appropriately
        self._log_error(error_info, component, req_id)

        return error_info.is_retryable, error_info.suggested_wait_time

    def handle_ib_error_sync(
        self,
        error_code: int,
        error_message: str,
        component: str,
        request_key: Optional[str] = None,
        req_id: Optional[int] = None,
    ) -> tuple[bool, float]:
        """
        Synchronous version of IB error handling.

        Args:
            error_code: IB error code
            error_message: IB error message
            component: Component that received the error
            request_key: Optional request key for context
            req_id: Optional IB request ID

        Returns:
            Tuple of (should_retry, wait_time_seconds)
        """
        # Use enhanced error classification
        error_info = self.error_handler.classify_error(
            error_code, error_message, use_context=self._enable_enhanced_classification
        )

        # Record metrics
        self._record_error(component, error_info)

        # Handle pace violations specifically
        if error_info.error_type == IbErrorType.PACING_VIOLATION:
            self._handle_pace_violation_sync(
                error_code, error_message, component, request_key
            )

        # Log appropriately
        self._log_error(error_info, component, req_id)

        return error_info.is_retryable, error_info.suggested_wait_time

    @asynccontextmanager
    async def pace_controlled_request(
        self,
        symbol: str,
        timeframe: str,
        component: str,
        operation: str = "data_request",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """
        Async context manager for pace-controlled requests.

        Usage:
            async with pace_manager.pace_controlled_request("AAPL", "1h", "data_fetcher") as request_key:
                # Make IB request here
                pass
        """
        request_key = self._create_request_key(
            symbol, timeframe, operation, start_date, end_date
        )

        try:
            # Check pace before request
            await self.check_pace_limits_async(
                symbol, timeframe, component, operation, start_date, end_date
            )

            yield request_key

            # Record successful request
            self._get_component_metrics(component).record_request(success=True)

        except Exception as e:
            # Record failed request
            self._get_component_metrics(component).record_request(success=False)
            raise

    def _create_request_key(
        self,
        symbol: str,
        timeframe: str,
        operation: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        """Create a unique request key for tracking."""
        if start_date and end_date:
            return f"{symbol}:{timeframe}:{operation}:{start_date.isoformat()}:{end_date.isoformat()}"
        else:
            return f"{symbol}:{timeframe}:{operation}"

    async def _calculate_required_wait_async(
        self, request_key: str, component: str
    ) -> float:
        """Calculate required wait time for async operations."""
        return self._calculate_required_wait_sync(request_key, component)

    def _calculate_required_wait_sync(self, request_key: str, component: str) -> float:
        """Calculate required wait time based on pace limits."""
        with self._pace_lock:
            current_time = time.time()

            # Clean old request history
            self._clean_request_history(current_time)

            # Check different pace limits
            waits = []

            # 1. Overall frequency limit
            freq_wait = self._check_frequency_limit(current_time)
            if freq_wait > 0:
                waits.append(("frequency", freq_wait))

            # 2. Identical request cooldown
            identical_wait = self._check_identical_request_limit(
                request_key, current_time
            )
            if identical_wait > 0:
                waits.append(("identical", identical_wait))

            # 3. Burst limit
            burst_wait = self._check_burst_limit(current_time)
            if burst_wait > 0:
                waits.append(("burst", burst_wait))

            # 4. Minimum delay
            min_wait = self._check_minimum_delay(current_time)
            if min_wait > 0:
                waits.append(("minimum", min_wait))

            # Return maximum wait time and reason
            if waits:
                max_wait = max(waits, key=lambda x: x[1])
                logger.debug(
                    f"🚦 Pace limit triggered: {max_wait[0]} requires {max_wait[1]:.1f}s wait"
                )
                return max_wait[1]

            return 0.0

    async def _handle_pace_wait_async(
        self, request_key: str, wait_time: float, component: str
    ):
        """Handle pace wait asynchronously."""
        violation = PaceViolationEvent(
            violation_type=PaceViolationType.FREQUENCY_LIMIT,  # Generic for proactive
            timestamp=time.time(),
            request_key=request_key,
            wait_time=wait_time,
        )

        self._active_violations[request_key] = violation
        self._get_component_metrics(component).record_pace_violation()

        logger.warning(
            f"🚦 PROACTIVE PACE LIMIT: Waiting {wait_time:.1f}s for {request_key}"
        )

        try:
            await asyncio.sleep(wait_time)
            violation.mark_resolved()
            logger.info(f"✅ Pace wait completed for {request_key}")

        except asyncio.CancelledError:
            logger.info(f"🛑 Pace wait cancelled for {request_key}")
            raise
        finally:
            self._active_violations.pop(request_key, None)
            self._violation_history.append(violation)
            self._trim_violation_history()

    def _handle_pace_wait_sync(
        self, request_key: str, wait_time: float, component: str
    ):
        """Handle pace wait synchronously."""
        violation = PaceViolationEvent(
            violation_type=PaceViolationType.FREQUENCY_LIMIT,  # Generic for proactive
            timestamp=time.time(),
            request_key=request_key,
            wait_time=wait_time,
        )

        self._active_violations[request_key] = violation
        self._get_component_metrics(component).record_pace_violation()

        logger.warning(
            f"🚦 PROACTIVE PACE LIMIT: Waiting {wait_time:.1f}s for {request_key}"
        )

        try:
            time.sleep(wait_time)
            violation.mark_resolved()
            logger.info(f"✅ Pace wait completed for {request_key}")

        finally:
            self._active_violations.pop(request_key, None)
            self._violation_history.append(violation)
            self._trim_violation_history()

    async def _handle_pace_violation_async(
        self,
        error_code: int,
        error_message: str,
        component: str,
        request_key: Optional[str],
    ):
        """Handle actual IB pace violations asynchronously."""
        violation_type = (
            PaceViolationType.IB_ERROR_162
            if error_code == 162
            else (
                PaceViolationType.IB_ERROR_165
                if error_code == 165
                else PaceViolationType.FREQUENCY_LIMIT
            )
        )

        violation = PaceViolationEvent(
            violation_type=violation_type,
            timestamp=time.time(),
            request_key=request_key or "unknown",
            wait_time=60.0,  # Default IB violation wait
        )

        if request_key:
            self._active_violations[request_key] = violation

        self._get_component_metrics(component).record_pace_violation()

        logger.error(f"🚦 IB PACE VIOLATION: Error {error_code} - {error_message}")

        # Use error handler's wait mechanism
        try:
            await asyncio.sleep(violation.wait_time)
            violation.mark_resolved()

        finally:
            if request_key:
                self._active_violations.pop(request_key, None)
            self._violation_history.append(violation)
            self._trim_violation_history()

    def _handle_pace_violation_sync(
        self,
        error_code: int,
        error_message: str,
        component: str,
        request_key: Optional[str],
    ):
        """Handle actual IB pace violations synchronously."""
        violation_type = (
            PaceViolationType.IB_ERROR_162
            if error_code == 162
            else (
                PaceViolationType.IB_ERROR_165
                if error_code == 165
                else PaceViolationType.FREQUENCY_LIMIT
            )
        )

        violation = PaceViolationEvent(
            violation_type=violation_type,
            timestamp=time.time(),
            request_key=request_key or "unknown",
            wait_time=60.0,  # Default IB violation wait
        )

        if request_key:
            self._active_violations[request_key] = violation

        self._get_component_metrics(component).record_pace_violation()

        logger.error(f"🚦 IB PACE VIOLATION: Error {error_code} - {error_message}")

        # Use error handler's wait mechanism
        try:
            time.sleep(violation.wait_time)
            violation.mark_resolved()

        finally:
            if request_key:
                self._active_violations.pop(request_key, None)
            self._violation_history.append(violation)
            self._trim_violation_history()

    def _record_request(self, request_key: str, component: str):
        """Record a request in history."""
        current_time = time.time()

        with self._pace_lock:
            self._request_history.append((current_time, request_key))
            self._identical_request_cache[request_key] = current_time
            self._last_request_time = current_time

    def _record_error(self, component: str, error_info: IbErrorInfo):
        """Record error metrics."""
        metrics = self._get_component_metrics(component)

        if error_info.error_type == IbErrorType.PACING_VIOLATION:
            metrics.record_pace_violation()

    def _get_component_metrics(self, component: str) -> RequestMetrics:
        """Get or create metrics for a component."""
        if component not in self._component_metrics:
            self._component_metrics[component] = RequestMetrics()
        return self._component_metrics[component]

    def _clean_request_history(self, current_time: float):
        """Clean old requests from history."""
        cutoff_time = current_time - self._max_history_age
        self._request_history = [
            req for req in self._request_history if req[0] > cutoff_time
        ]

    def _check_frequency_limit(self, current_time: float) -> float:
        """Check overall frequency limit."""
        max_requests = IbLimitsRegistry.PACING_LIMITS["max_requests_per_10min"]
        window_seconds = IbLimitsRegistry.PACING_LIMITS["rate_window_seconds"]

        window_start = current_time - window_seconds
        requests_in_window = len(
            [req for req in self._request_history if req[0] > window_start]
        )

        safety_threshold = int(max_requests * 0.8)  # 80% safety margin

        if requests_in_window >= safety_threshold:
            if self._request_history:
                oldest_in_window = min(
                    req[0] for req in self._request_history if req[0] > window_start
                )
                wait_time = (oldest_in_window + window_seconds) - current_time
                return max(0, wait_time)

        return 0.0

    def _check_identical_request_limit(
        self, request_key: str, current_time: float
    ) -> float:
        """Check cooldown for identical requests."""
        if request_key in self._identical_request_cache:
            last_time = self._identical_request_cache[request_key]
            cooldown = IbLimitsRegistry.SAFE_DELAYS["identical_requests"]
            time_since_last = current_time - last_time

            if time_since_last < cooldown:
                return cooldown - time_since_last

        return 0.0

    def _check_burst_limit(self, current_time: float) -> float:
        """Check burst limit."""
        burst_window = IbLimitsRegistry.PACING_LIMITS["burst_window_seconds"]
        max_burst = IbLimitsRegistry.PACING_LIMITS["burst_limit"]

        burst_start = current_time - burst_window
        requests_in_burst = len(
            [req for req in self._request_history if req[0] > burst_start]
        )

        if requests_in_burst >= max_burst:
            if self._request_history:
                oldest_in_burst = min(
                    req[0] for req in self._request_history if req[0] > burst_start
                )
                wait_time = (oldest_in_burst + burst_window) - current_time
                return max(0, wait_time)

        return 0.0

    def _check_minimum_delay(self, current_time: float) -> float:
        """Check minimum delay between requests."""
        min_delay = IbLimitsRegistry.SAFE_DELAYS["between_requests"]
        time_since_last = current_time - self._last_request_time

        if time_since_last < min_delay:
            return min_delay - time_since_last

        return 0.0

    def _log_error(
        self, error_info: IbErrorInfo, component: str, req_id: Optional[int]
    ):
        """Log error appropriately based on type."""
        prefix = f"[{component}]" + (f" (req:{req_id})" if req_id else "")

        if error_info.error_type == IbErrorType.INFORMATIONAL:
            logger.debug(
                f"{prefix} IB Info {error_info.error_code}: {error_info.error_message}"
            )
        elif error_info.error_type == IbErrorType.PACING_VIOLATION:
            logger.error(
                f"{prefix} 🚦 PACE VIOLATION {error_info.error_code}: {error_info.error_message}"
            )
        elif error_info.error_type == IbErrorType.FUTURE_DATE_REQUEST:
            logger.error(f"{prefix} 🔮 FUTURE DATE ERROR: {error_info.error_message}")
        elif error_info.error_type == IbErrorType.HISTORICAL_DATA_LIMIT:
            logger.warning(f"{prefix} 📅 HISTORICAL LIMIT: {error_info.error_message}")
        elif error_info.error_type == IbErrorType.NO_DATA_AVAILABLE:
            logger.info(f"{prefix} 📭 NO DATA: {error_info.error_message}")
        else:
            level = logging.ERROR if not error_info.is_retryable else logging.WARNING
            logger.log(
                level,
                f"{prefix} IB {'ERROR' if not error_info.is_retryable else 'WARNING'} {error_info.error_code}: {error_info.error_message}",
            )

    def _trim_violation_history(self):
        """Trim violation history to max size."""
        if len(self._violation_history) > self._max_violation_history:
            self._violation_history = self._violation_history[
                -self._max_violation_history :
            ]

    def get_pace_statistics(self) -> Dict[str, Any]:
        """Get comprehensive pace statistics."""
        current_time = time.time()

        with self._pace_lock:
            self._clean_request_history(current_time)

            # Calculate request rates
            window_10min = current_time - 600
            window_2sec = current_time - 2

            requests_10min = len(
                [req for req in self._request_history if req[0] > window_10min]
            )
            requests_2sec = len(
                [req for req in self._request_history if req[0] > window_2sec]
            )

            # Component statistics
            component_stats = {}
            for component, metrics in self._component_metrics.items():
                component_stats[component] = {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "pace_violations": metrics.pace_violations,
                    "total_wait_time": metrics.total_wait_time,
                    "avg_request_interval": metrics.avg_request_interval,
                    "success_rate": (
                        metrics.successful_requests / metrics.total_requests
                        if metrics.total_requests > 0
                        else 0.0
                    ),
                }

            # Violation statistics
            violation_stats = {}
            for violation_type in PaceViolationType:
                violations = [
                    v
                    for v in self._violation_history
                    if v.violation_type == violation_type
                ]
                violation_stats[violation_type.value] = {
                    "count": len(violations),
                    "total_wait_time": sum(v.wait_time for v in violations),
                    "avg_wait_time": (
                        sum(v.wait_time for v in violations) / len(violations)
                        if violations
                        else 0.0
                    ),
                }

            return {
                "current_state": {
                    "requests_in_10min": requests_10min,
                    "requests_in_2sec": requests_2sec,
                    "time_since_last_request": (
                        current_time - self._last_request_time
                        if self._last_request_time > 0
                        else 0
                    ),
                    "active_violations": len(self._active_violations),
                    "is_frequency_safe": requests_10min < 48,  # 80% of 60
                    "is_burst_safe": requests_2sec < 6,
                },
                "component_statistics": component_stats,
                "violation_statistics": violation_stats,
                "configuration": {
                    "proactive_limiting_enabled": self._enable_proactive_limiting,
                    "enhanced_classification_enabled": self._enable_enhanced_classification,
                    "max_requests_per_10min": IbLimitsRegistry.PACING_LIMITS[
                        "max_requests_per_10min"
                    ],
                    "burst_limit": IbLimitsRegistry.PACING_LIMITS["burst_limit"],
                    "minimum_delay": IbLimitsRegistry.SAFE_DELAYS["between_requests"],
                },
                "history_stats": {
                    "total_request_history": len(self._request_history),
                    "total_violation_history": len(self._violation_history),
                    "oldest_request": (
                        min(req[0] for req in self._request_history)
                        if self._request_history
                        else 0
                    ),
                },
            }

    def reset_statistics(self):
        """Reset all statistics and history."""
        with self._pace_lock:
            self._request_history.clear()
            self._identical_request_cache.clear()
            self._component_metrics.clear()
            self._violation_history.clear()
            self._active_violations.clear()
            self._last_request_time = 0.0

            logger.info("🔄 Pace manager statistics reset")


# Global pace manager instance
_pace_manager: Optional[IbPaceManager] = None


def get_pace_manager() -> IbPaceManager:
    """Get the global pace manager instance."""
    global _pace_manager
    if _pace_manager is None:
        _pace_manager = IbPaceManager()
    return _pace_manager


# Convenience functions for common operations
async def check_pace_async(
    symbol: str,
    timeframe: str,
    component: str,
    operation: str = "data_request",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> None:
    """Convenience function for async pace checking."""
    pace_manager = get_pace_manager()
    await pace_manager.check_pace_limits_async(
        symbol, timeframe, component, operation, start_date, end_date
    )


def check_pace_sync(
    symbol: str,
    timeframe: str,
    component: str,
    operation: str = "data_request",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> None:
    """Convenience function for sync pace checking."""
    pace_manager = get_pace_manager()
    pace_manager.check_pace_limits_sync(
        symbol, timeframe, component, operation, start_date, end_date
    )


async def handle_ib_error_async(
    error_code: int,
    error_message: str,
    component: str,
    request_key: Optional[str] = None,
    req_id: Optional[int] = None,
) -> tuple[bool, float]:
    """Convenience function for async IB error handling."""
    pace_manager = get_pace_manager()
    return await pace_manager.handle_ib_error_async(
        error_code, error_message, component, request_key, req_id
    )


def handle_ib_error_sync(
    error_code: int,
    error_message: str,
    component: str,
    request_key: Optional[str] = None,
    req_id: Optional[int] = None,
) -> tuple[bool, float]:
    """Convenience function for sync IB error handling."""
    pace_manager = get_pace_manager()
    return pace_manager.handle_ib_error_sync(
        error_code, error_message, component, request_key, req_id
    )

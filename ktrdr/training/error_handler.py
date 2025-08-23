"""Robust error handling and recovery system for KTRDR training."""

import signal
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from ktrdr import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"  # Minor issues, can continue
    MEDIUM = "medium"  # Concerning but recoverable
    HIGH = "high"  # Major issues, may need intervention
    CRITICAL = "critical"  # System-threatening, immediate action required


class RecoveryAction(Enum):
    """Recovery action types."""

    CONTINUE = "continue"  # Continue with current operation
    RETRY = "retry"  # Retry the failed operation
    SKIP = "skip"  # Skip the current operation
    FALLBACK = "fallback"  # Use fallback method
    RESTART = "restart"  # Restart the component
    ABORT = "abort"  # Abort the operation
    GRACEFUL_SHUTDOWN = "shutdown"  # Graceful system shutdown


@dataclass
class ErrorContext:
    """Context information for error handling."""

    timestamp: float
    error_type: str
    error_message: str
    traceback_str: str
    severity: ErrorSeverity
    component: str
    operation: str
    retry_count: int = 0
    max_retries: int = 3
    recovery_actions: list[RecoveryAction] = field(default_factory=list)
    additional_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "traceback": self.traceback_str,
            "severity": self.severity.value,
            "component": self.component,
            "operation": self.operation,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "recovery_actions": [action.value for action in self.recovery_actions],
            "additional_data": self.additional_data,
        }


@dataclass
class RecoveryStrategy:
    """Recovery strategy configuration."""

    error_types: list[type[Exception]]
    severity: ErrorSeverity
    max_retries: int
    retry_delay: float  # seconds
    recovery_actions: list[RecoveryAction]
    fallback_function: Optional[Callable] = None
    cleanup_function: Optional[Callable] = None

    def matches_error(self, error: Exception) -> bool:
        """Check if this strategy applies to the given error."""
        return any(isinstance(error, error_type) for error_type in self.error_types)


class ErrorHandler:
    """Comprehensive error handling and recovery system."""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize error handler.

        Args:
            output_dir: Directory to save error logs and recovery data
        """
        self.output_dir = Path(output_dir) if output_dir else Path("error_logs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Error tracking
        self.error_history: list[ErrorContext] = []
        self.recovery_strategies: list[RecoveryStrategy] = []
        self.component_health: dict[str, dict[str, Any]] = {}

        # Recovery state
        self.recovery_in_progress = False
        self.recovery_lock = threading.Lock()

        # Signal handling for graceful shutdown
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

        # Setup default recovery strategies
        self._setup_default_strategies()

        logger.info(f"ErrorHandler initialized, logs dir: {self.output_dir}")

    def _setup_default_strategies(self):
        """Setup default recovery strategies for common errors."""

        # Out of memory errors
        self.add_recovery_strategy(
            RecoveryStrategy(
                error_types=[RuntimeError],  # Includes CUDA OOM
                severity=ErrorSeverity.HIGH,
                max_retries=2,
                retry_delay=1.0,
                recovery_actions=[RecoveryAction.RETRY, RecoveryAction.FALLBACK],
                cleanup_function=self._cleanup_memory,
            )
        )

        # Network/connection errors
        self.add_recovery_strategy(
            RecoveryStrategy(
                error_types=[ConnectionError, TimeoutError, OSError],
                severity=ErrorSeverity.MEDIUM,
                max_retries=5,
                retry_delay=2.0,
                recovery_actions=[RecoveryAction.RETRY, RecoveryAction.SKIP],
            )
        )

        # File I/O errors
        self.add_recovery_strategy(
            RecoveryStrategy(
                error_types=[FileNotFoundError, PermissionError, IOError],
                severity=ErrorSeverity.MEDIUM,
                max_retries=3,
                retry_delay=0.5,
                recovery_actions=[RecoveryAction.RETRY, RecoveryAction.FALLBACK],
            )
        )

        # Value errors (data issues)
        self.add_recovery_strategy(
            RecoveryStrategy(
                error_types=[ValueError, TypeError],
                severity=ErrorSeverity.LOW,
                max_retries=1,
                retry_delay=0.1,
                recovery_actions=[RecoveryAction.SKIP, RecoveryAction.FALLBACK],
            )
        )

        # Critical system errors
        self.add_recovery_strategy(
            RecoveryStrategy(
                error_types=[SystemError, MemoryError],
                severity=ErrorSeverity.CRITICAL,
                max_retries=0,
                retry_delay=0.0,
                recovery_actions=[RecoveryAction.GRACEFUL_SHUTDOWN],
            )
        )

    def add_recovery_strategy(self, strategy: RecoveryStrategy):
        """Add a custom recovery strategy."""
        self.recovery_strategies.append(strategy)
        logger.debug(
            f"Added recovery strategy for {[e.__name__ for e in strategy.error_types]}"
        )

    def handle_error(
        self,
        error: Exception,
        component: str,
        operation: str,
        additional_data: Optional[dict[str, Any]] = None,
    ) -> RecoveryAction:
        """Handle an error and determine recovery action.

        Args:
            error: The exception that occurred
            component: Component where error occurred
            operation: Operation that failed
            additional_data: Additional context data

        Returns:
            Recommended recovery action
        """
        # Create error context
        error_context = ErrorContext(
            timestamp=time.time(),
            error_type=type(error).__name__,
            error_message=str(error),
            traceback_str=traceback.format_exc(),
            severity=self._determine_severity(error),
            component=component,
            operation=operation,
            additional_data=additional_data or {},
        )

        # Find matching recovery strategy
        strategy = self._find_recovery_strategy(error)
        if strategy:
            error_context.max_retries = strategy.max_retries
            error_context.recovery_actions = strategy.recovery_actions.copy()

        # Log the error
        self._log_error(error_context)

        # Add to history
        self.error_history.append(error_context)

        # Update component health
        self._update_component_health(component, error_context)

        # Determine recovery action
        recovery_action = self._determine_recovery_action(error_context, strategy)

        # Execute recovery if needed
        if strategy and recovery_action in [
            RecoveryAction.RETRY,
            RecoveryAction.FALLBACK,
        ]:
            self._execute_recovery(error_context, strategy, recovery_action)

        return recovery_action

    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """Determine error severity based on error type."""
        critical_errors = (SystemError, MemoryError, KeyboardInterrupt)
        high_errors = (RuntimeError, ImportError, ModuleNotFoundError)
        medium_errors = (ConnectionError, TimeoutError, IOError, OSError)

        if isinstance(error, critical_errors):
            return ErrorSeverity.CRITICAL
        elif isinstance(error, high_errors):
            return ErrorSeverity.HIGH
        elif isinstance(error, medium_errors):
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW

    def _find_recovery_strategy(self, error: Exception) -> Optional[RecoveryStrategy]:
        """Find the best recovery strategy for an error."""
        for strategy in self.recovery_strategies:
            if strategy.matches_error(error):
                return strategy
        return None

    def _determine_recovery_action(
        self, error_context: ErrorContext, strategy: Optional[RecoveryStrategy]
    ) -> RecoveryAction:
        """Determine the best recovery action."""

        # Check for shutdown request
        if self.shutdown_requested:
            return RecoveryAction.GRACEFUL_SHUTDOWN

        # Critical errors
        if error_context.severity == ErrorSeverity.CRITICAL:
            return RecoveryAction.GRACEFUL_SHUTDOWN

        # No strategy available
        if not strategy:
            return RecoveryAction.CONTINUE

        # Check retry limit
        if error_context.retry_count >= strategy.max_retries:
            if RecoveryAction.FALLBACK in strategy.recovery_actions:
                return RecoveryAction.FALLBACK
            elif RecoveryAction.SKIP in strategy.recovery_actions:
                return RecoveryAction.SKIP
            else:
                return RecoveryAction.ABORT

        # Use first available action from strategy
        return (
            strategy.recovery_actions[0]
            if strategy.recovery_actions
            else RecoveryAction.CONTINUE
        )

    def _execute_recovery(
        self,
        error_context: ErrorContext,
        strategy: RecoveryStrategy,
        action: RecoveryAction,
    ):
        """Execute recovery actions."""
        with self.recovery_lock:
            if self.recovery_in_progress:
                return

            self.recovery_in_progress = True

            try:
                if action == RecoveryAction.RETRY:
                    logger.info(
                        f"Retrying {error_context.operation} (attempt {error_context.retry_count + 1})"
                    )
                    if strategy.retry_delay > 0:
                        time.sleep(strategy.retry_delay)

                elif action == RecoveryAction.FALLBACK:
                    logger.info(f"Using fallback for {error_context.operation}")
                    if strategy.fallback_function:
                        strategy.fallback_function()

                # Run cleanup if available
                if strategy.cleanup_function:
                    strategy.cleanup_function()

            except Exception as recovery_error:
                logger.error(f"Recovery action failed: {recovery_error}")
            finally:
                self.recovery_in_progress = False

    def _cleanup_memory(self):
        """Memory cleanup recovery function."""
        import gc

        import torch

        # Python garbage collection
        collected = gc.collect()
        logger.debug(f"Garbage collection freed {collected} objects")

        # GPU memory cleanup if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("GPU cache cleared")

    def _log_error(self, error_context: ErrorContext):
        """Log error with appropriate level."""
        message = f"{error_context.component}.{error_context.operation}: {error_context.error_message}"

        if error_context.severity == ErrorSeverity.CRITICAL:
            logger.critical(message)
        elif error_context.severity == ErrorSeverity.HIGH:
            logger.error(message)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            logger.warning(message)
        else:
            logger.info(message)

    def _update_component_health(self, component: str, error_context: ErrorContext):
        """Update component health tracking."""
        if component not in self.component_health:
            self.component_health[component] = {
                "total_errors": 0,
                "error_types": {},
                "last_error": None,
                "health_score": 1.0,
            }

        health = self.component_health[component]
        health["total_errors"] += 1
        health["last_error"] = error_context.timestamp

        # Track error types
        error_type = error_context.error_type
        if error_type not in health["error_types"]:
            health["error_types"][error_type] = 0
        health["error_types"][error_type] += 1

        # Update health score (0.0 = unhealthy, 1.0 = healthy)
        severity_weights = {
            ErrorSeverity.LOW: 0.05,
            ErrorSeverity.MEDIUM: 0.15,
            ErrorSeverity.HIGH: 0.30,
            ErrorSeverity.CRITICAL: 0.50,
        }

        weight = severity_weights.get(error_context.severity, 0.10)
        health["health_score"] = max(0.0, health["health_score"] - weight)

    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.warning(f"Received shutdown signal {signum}")
        self.shutdown_requested = True

    def retry_with_recovery(
        self,
        func: Callable,
        component: str,
        operation: str,
        *args,
        max_retries: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """Execute function with automatic retry and recovery.

        Args:
            func: Function to execute
            component: Component name
            operation: Operation name
            max_retries: Override default max retries
            *args, **kwargs: Arguments for the function

        Returns:
            Function result

        Raises:
            Exception: If all recovery attempts fail
        """
        retry_count = 0
        last_error = None

        while retry_count <= (max_retries or 3):
            try:
                return func(*args, **kwargs)

            except Exception as error:
                last_error = error
                recovery_action = self.handle_error(
                    error,
                    component,
                    operation,
                    {"retry_count": retry_count, "args": str(args)[:100]},
                )

                if recovery_action == RecoveryAction.RETRY:
                    retry_count += 1
                    continue
                elif recovery_action == RecoveryAction.SKIP:
                    logger.warning(f"Skipping {operation} due to error")
                    return None
                elif recovery_action == RecoveryAction.GRACEFUL_SHUTDOWN:
                    logger.critical("Initiating graceful shutdown")
                    self.graceful_shutdown()
                    raise error
                else:
                    # ABORT or other - re-raise the error
                    raise error

        # All retries exhausted
        raise last_error

    def graceful_shutdown(self):
        """Perform graceful shutdown."""
        logger.info("Starting graceful shutdown...")

        # Save error logs
        try:
            self.export_error_logs()
        except Exception as e:
            logger.error(f"Failed to save error logs during shutdown: {e}")

        # Set shutdown flag
        self.shutdown_requested = True

        logger.info("Graceful shutdown completed")

    def get_error_summary(self) -> dict[str, Any]:
        """Get comprehensive error summary."""
        if not self.error_history:
            return {"total_errors": 0, "components": {}, "error_types": {}}

        # Overall statistics
        total_errors = len(self.error_history)
        severity_counts = {}
        error_type_counts = {}

        for error in self.error_history:
            # Severity distribution
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # Error type distribution
            error_type = error.error_type
            error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1

        # Component health summary
        component_summary = {}
        for component, health in self.component_health.items():
            component_summary[component] = {
                "total_errors": health["total_errors"],
                "health_score": health["health_score"],
                "most_common_error": (
                    max(health["error_types"].items(), key=lambda x: x[1])[0]
                    if health["error_types"]
                    else None
                ),
            }

        return {
            "total_errors": total_errors,
            "severity_distribution": severity_counts,
            "error_type_distribution": error_type_counts,
            "component_health": component_summary,
            "most_recent_errors": [
                error.to_dict() for error in self.error_history[-5:]
            ],
        }

    def export_error_logs(self, filename: Optional[str] = None) -> Path:
        """Export error logs to file.

        Args:
            filename: Custom filename (optional)

        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"error_log_{timestamp}.json"

        export_path = self.output_dir / filename

        export_data = {
            "metadata": {
                "export_timestamp": time.time(),
                "total_errors": len(self.error_history),
                "export_version": "1.0",
            },
            "error_summary": self.get_error_summary(),
            "error_history": [error.to_dict() for error in self.error_history],
            "component_health": self.component_health,
            "recovery_strategies": [
                {
                    "error_types": [e.__name__ for e in strategy.error_types],
                    "severity": strategy.severity.value,
                    "max_retries": strategy.max_retries,
                    "retry_delay": strategy.retry_delay,
                    "recovery_actions": [
                        action.value for action in strategy.recovery_actions
                    ],
                }
                for strategy in self.recovery_strategies
            ],
        }

        # Save to JSON
        import json

        with open(export_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Error logs exported to: {export_path}")
        return export_path

    def get_health_report(self) -> dict[str, Any]:
        """Get system health report."""
        recent_errors = [
            e for e in self.error_history if time.time() - e.timestamp < 3600
        ]  # Last hour

        # Overall system health score
        if not self.component_health:
            overall_health = 1.0
        else:
            health_scores = [
                health["health_score"] for health in self.component_health.values()
            ]
            overall_health = sum(health_scores) / len(health_scores)

        # Health status
        if overall_health >= 0.8:
            health_status = "healthy"
        elif overall_health >= 0.6:
            health_status = "warning"
        elif overall_health >= 0.4:
            health_status = "degraded"
        else:
            health_status = "critical"

        return {
            "overall_health_score": overall_health,
            "health_status": health_status,
            "recent_errors_count": len(recent_errors),
            "component_count": len(self.component_health),
            "unhealthy_components": [
                comp
                for comp, health in self.component_health.items()
                if health["health_score"] < 0.5
            ],
            "shutdown_requested": self.shutdown_requested,
            "recovery_in_progress": self.recovery_in_progress,
        }

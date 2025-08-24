"""
ProgressManager component for thread-safe progress tracking.

This component extracts progress logic from DataManager's 2600+ line god class
into a focused component that enables async architecture and future WebSocket streaming.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProgressState:
    """Progress state information for operations."""

    operation_id: str
    current_step: int
    total_steps: int
    message: str
    percentage: float
    estimated_remaining: Optional[timedelta] = None
    start_time: datetime = field(default_factory=datetime.now)

    # Additional state for compatibility
    steps_completed: int = 0
    steps_total: int = 0

    # Segment tracking for hierarchical progress
    current_step_name: Optional[str] = None
    step_current: int = 0
    step_total: int = 0
    step_detail: str = ""


class ProgressManager:
    """
    Thread-safe progress manager for data loading and processing operations.

    This component provides:
    - Thread-safe progress tracking across async/sync boundaries
    - Hierarchical progress reporting (Operation -> Steps -> Sub-steps)
    - Backward compatibility with existing DataManager callback patterns
    - Cancellation token integration
    - Time estimation for long operations

    Architecture compliance:
    - Thread-safe (Progress component type from spec)
    - Hierarchical progress tracking
    - Cancellation token integration
    - Works across sync/async boundaries
    - Provides consistent interface
    - Includes comprehensive logging
    """

    def __init__(self, callback_func: Optional[Callable[[str, float], None]] = None):
        """
        Initialize ProgressManager with optional callback.

        Args:
            callback_func: Optional callback function with signature (message: str, percentage: float)
                          Matches existing DataManager callback behavior for backward compatibility
        """
        self.callback = callback_func
        self._current_state: Optional[ProgressState] = None
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._cancellation_token: Optional[Any] = None
        self._operation_start_time: Optional[datetime] = None

        logger.debug(
            "ProgressManager initialized with callback: %s", callback_func is not None
        )

    def start_operation(self, total_steps: int, operation_name: str) -> None:
        """
        Begin tracking new operation.

        Args:
            total_steps: Total number of steps in the operation
            operation_name: Human-readable name for the operation
        """
        with self._lock:
            self._operation_start_time = datetime.now()

            self._current_state = ProgressState(
                operation_id=operation_name,
                current_step=0,
                total_steps=total_steps,
                message=f"Starting {operation_name}",
                percentage=0.0,
                start_time=self._operation_start_time,
                steps_completed=0,
                steps_total=total_steps,
            )

            logger.debug(
                "Started operation '%s' with %d steps", operation_name, total_steps
            )

            # Trigger initial callback
            self._trigger_callback()

    def start_step(self, step_name: str, step_number: int) -> None:
        """
        Start a new step within the current operation.

        Args:
            step_name: Name of the step being started
            step_number: Step number (1-based)
        """
        with self._lock:
            if self._current_state is None:
                logger.warning("start_step called without active operation")
                return

            self._current_state.current_step = step_number
            self._current_state.current_step_name = step_name
            self._current_state.message = f"Starting {step_name}"
            self._current_state.step_current = 0
            self._current_state.step_total = 0
            self._current_state.step_detail = ""

            # Update percentage based on step progress
            if self._current_state.total_steps > 0:
                self._current_state.percentage = (
                    (step_number - 1) / self._current_state.total_steps * 100.0
                )

            logger.debug("Started step %d: %s", step_number, step_name)
            self._trigger_callback()

    def update_step_progress(self, current: int, total: int, detail: str = "") -> None:
        """
        Update progress within the current step.

        Args:
            current: Current progress within the step
            total: Total items in the step
            detail: Additional detail message
        """
        with self._lock:
            if self._current_state is None:
                logger.warning("update_step_progress called without active operation")
                return

            self._current_state.step_current = current
            self._current_state.step_total = total
            self._current_state.step_detail = detail

            # Calculate percentage including sub-step progress
            if self._current_state.total_steps > 0:
                step_base_percentage = (
                    (self._current_state.current_step - 1)
                    / self._current_state.total_steps
                    * 100.0
                )
                step_increment = 100.0 / self._current_state.total_steps

                if total > 0:
                    sub_step_progress = (current / total) * step_increment
                    self._current_state.percentage = (
                        step_base_percentage + sub_step_progress
                    )
                else:
                    self._current_state.percentage = step_base_percentage

            # Update message with detail
            if detail:
                step_name = (
                    self._current_state.current_step_name
                    or f"Step {self._current_state.current_step}"
                )
                if total > 0:
                    self._current_state.message = (
                        f"{step_name}: {detail} ({current}/{total})"
                    )
                else:
                    self._current_state.message = f"{step_name}: {detail}"

            # Calculate time estimate
            self._update_time_estimate()

            self._trigger_callback()

    def update_progress(self, step: int, message: str) -> None:
        """
        Update overall operation progress.

        Args:
            step: Current step number (0-based for backward compatibility)
            message: Progress message
        """
        with self._lock:
            if self._current_state is None:
                return  # Skip warning for performance

            self._current_state.current_step = step
            self._current_state.message = message
            self._current_state.steps_completed = step

            # Calculate percentage (handle zero total steps)
            if self._current_state.total_steps > 0:
                self._current_state.percentage = min(
                    100.0, (step / self._current_state.total_steps) * 100.0
                )
            else:
                self._current_state.percentage = 100.0  # Treat 0/0 as complete

            # Ensure percentage doesn't go negative
            self._current_state.percentage = max(0.0, self._current_state.percentage)

            # Calculate time estimate (only occasionally for performance)
            if step % 10 == 0:  # Only every 10th update
                self._update_time_estimate()

            # Skip debug logging for performance in tight loops

            self._trigger_callback()

    def complete_step(self) -> None:
        """Mark the current step as complete."""
        with self._lock:
            if self._current_state is None:
                logger.warning("complete_step called without active operation")
                return

            self._current_state.steps_completed = self._current_state.current_step

            # Update message
            step_name = (
                self._current_state.current_step_name
                or f"Step {self._current_state.current_step}"
            )
            self._current_state.message = f"Completed {step_name}"

            logger.debug(
                "Completed step %d: %s", self._current_state.current_step, step_name
            )
            self._trigger_callback()

    def complete_operation(self) -> None:
        """Mark operation complete and cleanup."""
        with self._lock:
            if self._current_state is None:
                logger.warning("complete_operation called without active operation")
                return

            self._current_state.current_step = self._current_state.total_steps
            self._current_state.steps_completed = self._current_state.total_steps
            self._current_state.percentage = 100.0
            self._current_state.message = (
                f"Operation '{self._current_state.operation_id}' completed successfully"
            )
            self._current_state.estimated_remaining = timedelta(0)

            logger.info(
                "Operation '%s' completed successfully",
                self._current_state.operation_id,
            )
            self._trigger_callback()

    def check_cancelled(self) -> bool:
        """
        Check if the operation has been cancelled.

        Returns:
            True if cancelled, False otherwise
        """
        with self._lock:
            if self._cancellation_token is None:
                return False

            # Support both attribute and callable patterns
            if hasattr(self._cancellation_token, "is_cancelled"):
                return bool(self._cancellation_token.is_cancelled)
            elif callable(self._cancellation_token):
                return bool(self._cancellation_token())

            return False

    def get_progress_state(self) -> ProgressState:
        """
        Get current progress state.

        Returns:
            Current progress state (thread-safe copy)
        """
        with self._lock:
            if self._current_state is None:
                # Return empty state if no operation is active
                return ProgressState(
                    operation_id="",
                    current_step=0,
                    total_steps=0,
                    message="No active operation",
                    percentage=0.0,
                )

            # Return a copy to avoid external mutation
            return ProgressState(
                operation_id=self._current_state.operation_id,
                current_step=self._current_state.current_step,
                total_steps=self._current_state.total_steps,
                message=self._current_state.message,
                percentage=self._current_state.percentage,
                estimated_remaining=self._current_state.estimated_remaining,
                start_time=self._current_state.start_time,
                steps_completed=self._current_state.steps_completed,
                steps_total=self._current_state.steps_total,
                current_step_name=self._current_state.current_step_name,
                step_current=self._current_state.step_current,
                step_total=self._current_state.step_total,
                step_detail=self._current_state.step_detail,
            )

    def set_cancellation_token(self, token: Any) -> None:
        """
        Set cancellation token for operation cancellation.

        Args:
            token: Cancellation token with is_cancelled attribute or callable
        """
        with self._lock:
            self._cancellation_token = token
            logger.debug("Cancellation token set: %s", type(token).__name__)

    def _trigger_callback(self) -> None:
        """
        Trigger the progress callback if one is set.

        This method maintains backward compatibility with existing DataManager
        callback signature: callback(message: str, percentage: float)
        """
        if self.callback is None or self._current_state is None:
            return

        try:
            # Use existing callback signature for backward compatibility
            self.callback(self._current_state.message, self._current_state.percentage)
        except Exception as e:
            logger.warning("Progress callback failed: %s", e)

    def _update_time_estimate(self) -> None:
        """Update estimated remaining time based on current progress."""
        if (
            self._current_state is None
            or self._operation_start_time is None
            or self._current_state.percentage <= 0
        ):
            return

        try:
            elapsed = datetime.now() - self._operation_start_time
            if (
                elapsed.total_seconds() < 1.0
            ):  # Need at least 1 second for meaningful estimate
                return

            progress_fraction = self._current_state.percentage / 100.0
            if progress_fraction >= 1.0:
                self._current_state.estimated_remaining = timedelta(0)
                return

            # Estimate based on current rate
            estimated_total_time = elapsed / progress_fraction
            remaining_time = estimated_total_time - elapsed

            # Cap estimates at reasonable values
            if remaining_time.total_seconds() > 3600:  # More than 1 hour
                remaining_time = timedelta(hours=1)
            elif remaining_time.total_seconds() < 0:
                remaining_time = timedelta(0)

            self._current_state.estimated_remaining = remaining_time

        except (ZeroDivisionError, OverflowError) as e:
            logger.debug("Time estimation failed: %s", e)
            self._current_state.estimated_remaining = None

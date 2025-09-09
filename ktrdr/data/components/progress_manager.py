"""
ProgressManager component for thread-safe progress tracking.

This component extracts progress logic from DataManager's 2600+ line god class
into a focused component that enables async architecture and future WebSocket streaming.
"""

import logging
import pickle
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
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

    # Step percentage range (for custom step allocation)
    step_start_percentage: float = 0.0
    step_end_percentage: float = 0.0

    # Item tracking for generic progress (bars, data points, etc.)
    expected_items: Optional[int] = None
    items_processed: int = 0
    step_items_processed: int = 0  # Items processed in current step

    # Context information for enhanced progress descriptions
    operation_context: Optional[dict[str, Any]] = None
    current_item_detail: Optional[str] = None

    # Enhanced time estimation
    estimated_completion: Optional[datetime] = None
    overall_percentage: float = 0.0


class TimeEstimationEngine:
    """
    Learning-based time estimation engine for progress operations.

    Records completion times for different operation types and contexts,
    then uses this historical data to provide increasingly accurate estimates.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize time estimation engine with optional persistent cache."""
        self.cache_file = cache_file
        self.operation_history: dict[str, list[dict]] = {}
        self._load_cache()

    def _create_operation_key(
        self, operation_type: str, context: dict[str, Any]
    ) -> str:
        """Create a unique key for operation type and context."""
        # Create key based on operation type and relevant context
        key_parts = [operation_type]

        # Add generic context parts for better estimation
        # Domain-specific logic moved to domain renderers (e.g., DataProgressRenderer)
        if "data_points" in context:
            # Group by data size ranges for better estimation
            size = int(context["data_points"])
            if size < 1000:
                key_parts.append("size:small")
            elif size < 10000:
                key_parts.append("size:medium")
            else:
                key_parts.append("size:large")

        return "|".join(key_parts)

    def record_operation_completion(
        self, operation_type: str, context: dict[str, Any], duration_seconds: float
    ) -> None:
        """Record completed operation for future estimation."""
        if duration_seconds <= 0:
            return  # Invalid duration

        key = self._create_operation_key(operation_type, context)

        if key not in self.operation_history:
            self.operation_history[key] = []

        self.operation_history[key].append(
            {
                "duration": duration_seconds,
                "timestamp": datetime.now(),
                "context": context.copy(),
            }
        )

        # Keep only recent history (last 10 operations)
        self.operation_history[key] = self.operation_history[key][-10:]

        # Save to cache periodically
        self._save_cache()

        logger.debug(f"Recorded operation completion: {key} - {duration_seconds:.2f}s")

    def estimate_duration(
        self, operation_type: str, context: dict[str, Any]
    ) -> Optional[float]:
        """Estimate operation duration based on historical data."""
        key = self._create_operation_key(operation_type, context)

        if key not in self.operation_history or len(self.operation_history[key]) < 2:
            return None  # Not enough data for estimation

        # Use weighted average with more weight on recent operations
        history = self.operation_history[key]
        total_weight = 0.0
        weighted_sum = 0.0

        for i, record in enumerate(history):
            # More recent = higher weight, also consider recency by timestamp
            age_weight = i + 1
            time_weight = 1.0

            # Reduce weight for very old records (older than 30 days)
            age_days = (datetime.now() - record["timestamp"]).days
            if age_days > 30:
                time_weight = 0.5
            elif age_days > 7:
                time_weight = 0.8

            combined_weight = age_weight * time_weight
            weighted_sum += record["duration"] * combined_weight
            total_weight += combined_weight

        estimated = weighted_sum / total_weight if total_weight > 0 else None

        if estimated:
            logger.debug(
                f"Estimated duration for {key}: {estimated:.2f}s (based on {len(history)} records)"
            )

        return estimated

    def _load_cache(self) -> None:
        """Load operation history from cache file."""
        if not self.cache_file or not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, "rb") as f:
                self.operation_history = pickle.load(f)
            logger.debug(
                f"Loaded time estimation cache with {len(self.operation_history)} operation types"
            )
        except Exception as e:
            logger.warning(f"Failed to load time estimation cache: {e}")
            self.operation_history = {}

    def _save_cache(self) -> None:
        """Save operation history to cache file."""
        if not self.cache_file:
            return

        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "wb") as f:
                pickle.dump(self.operation_history, f)
        except Exception as e:
            logger.warning(f"Failed to save time estimation cache: {e}")


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

    def __init__(
        self,
        callback_func: Optional[Callable[[Any], None]] = None,
        enable_time_estimation: bool = True,
        time_estimation_cache_file: Optional[Path] = None,
    ):
        """
        Initialize ProgressManager with enhanced capabilities.

        Args:
            callback_func: Optional callback function with signature (progress_state: ProgressState)
                          Receives complete progress information including steps, items, and timing
            enable_time_estimation: Enable learning-based time estimation
            time_estimation_cache_file: Optional file path for persisting time estimation data
        """
        self.callback = callback_func
        self._current_state: Optional[ProgressState] = None
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._cancellation_token: Optional[Any] = None
        self._operation_start_time: Optional[datetime] = None

        # Enhanced capabilities
        self.enable_time_estimation = enable_time_estimation
        self._time_estimator: Optional[TimeEstimationEngine] = None
        self._current_operation_type: Optional[str] = None
        self._current_context: dict[str, Any] = {}

        if enable_time_estimation:
            # Create time estimation cache in data directory if not specified
            if time_estimation_cache_file is None:
                cache_dir = Path.home() / ".ktrdr" / "cache"
                time_estimation_cache_file = cache_dir / "progress_time_estimation.pkl"

            self._time_estimator = TimeEstimationEngine(time_estimation_cache_file)

        logger.debug(
            "ProgressManager initialized with callback: %s, time_estimation: %s",
            callback_func is not None,
            enable_time_estimation,
        )

    def start_operation(
        self,
        total_steps: int,
        operation_name: str,
        expected_items: Optional[int] = None,
        operation_context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Begin tracking new operation with enhanced contextual information.

        Args:
            total_steps: Total number of steps in the operation
            operation_name: Human-readable name for the operation
            expected_items: Expected total number of items to process (bars, data points, etc.)
            operation_context: Context information for enhanced progress descriptions and time estimation
                             (e.g., {'symbol': 'AAPL', 'timeframe': '1d', 'mode': 'backfill'})
        """
        with self._lock:
            self._operation_start_time = datetime.now()
            self._current_operation_type = operation_name
            self._current_context = operation_context or {}

            # Estimate completion time if time estimation is enabled
            estimated_completion = None
            if self.enable_time_estimation and self._time_estimator:
                estimated_duration = self._time_estimator.estimate_duration(
                    operation_name, self._current_context
                )
                if estimated_duration:
                    estimated_completion = self._operation_start_time + timedelta(
                        seconds=estimated_duration
                    )

            # Create simple start message (domain-specific enhancement moved to renderers)
            start_message = f"Starting {operation_name}"

            self._current_state = ProgressState(
                operation_id=operation_name,
                current_step=0,
                total_steps=total_steps,
                message=start_message,
                percentage=0.0,
                start_time=self._operation_start_time,
                steps_completed=0,
                steps_total=total_steps,
                expected_items=expected_items,
                items_processed=0,
                step_items_processed=0,
                operation_context=self._current_context,
                estimated_completion=estimated_completion,
                overall_percentage=0.0,
            )

            logger.debug(
                "Started operation '%s' with %d steps and context: %s",
                operation_name,
                total_steps,
                self._current_context,
            )

            # Trigger initial callback
            self._trigger_callback()

    def start_step(
        self,
        step_name: str,
        step_number: int,
        expected_items: Optional[int] = None,
        step_percentage: Optional[float] = None,
        step_end_percentage: Optional[float] = None,
    ) -> None:
        """
        Start a new step within the current operation.

        Args:
            step_name: Name of the step being started
            step_number: Step number (1-based)
            expected_items: Expected number of items to process in this step
            step_percentage: Optional custom percentage for this step start (overrides default calculation)
            step_end_percentage: Optional custom percentage for this step end (for custom step ranges)
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
            self._current_state.step_items_processed = 0

            # Update expected items for this step if provided
            if expected_items is not None:
                self._current_state.expected_items = expected_items

            # Update percentage based on step progress
            if step_percentage is not None:
                # Use custom percentage if provided
                self._current_state.percentage = step_percentage
                self._current_state.step_start_percentage = step_percentage

                # Set step end percentage
                if step_end_percentage is not None:
                    self._current_state.step_end_percentage = step_end_percentage
                else:
                    # Default: assume equal step increments
                    default_increment = (
                        100.0 / self._current_state.total_steps
                        if self._current_state.total_steps > 0
                        else 10.0
                    )
                    self._current_state.step_end_percentage = (
                        step_percentage + default_increment
                    )

            elif self._current_state.total_steps > 0:
                # Use default equal increment calculation
                start_pct = (step_number - 1) / self._current_state.total_steps * 100.0
                end_pct = step_number / self._current_state.total_steps * 100.0

                self._current_state.percentage = start_pct
                self._current_state.step_start_percentage = start_pct
                self._current_state.step_end_percentage = end_pct

            logger.debug("Started step %d: %s", step_number, step_name)
            self._trigger_callback()

    def update_step_progress(
        self, current: int, total: int, items_processed: int = 0, detail: str = ""
    ) -> None:
        """
        Update progress within the current step.

        Args:
            current: Current progress within the step
            total: Total items in the step
            items_processed: Number of items processed (bars, data points, etc.)
            detail: Additional detail message
        """
        with self._lock:
            if self._current_state is None:
                logger.warning("update_step_progress called without active operation")
                return

            self._current_state.step_current = current
            self._current_state.step_total = total
            self._current_state.step_detail = detail

            # Update item tracking
            if items_processed > 0:
                self._current_state.items_processed = items_processed
                self._current_state.step_items_processed = items_processed

            # Calculate percentage including sub-step progress using step range
            step_start = self._current_state.step_start_percentage
            step_end = self._current_state.step_end_percentage
            step_range = step_end - step_start

            if total > 0:
                # Calculate progress within the step's percentage range
                sub_progress_ratio = current / total
                sub_progress_percentage = sub_progress_ratio * step_range
                self._current_state.percentage = step_start + sub_progress_percentage
            else:
                # No sub-progress, stay at step start
                self._current_state.percentage = step_start

            # Update message with detail and item information
            if detail:
                step_name = (
                    self._current_state.current_step_name
                    or f"Step {self._current_state.current_step}"
                )

                # Build rich message with item information
                message_parts = [f"{step_name}: {detail}"]

                if total > 0:
                    message_parts.append(f"({current}/{total})")

                # Add item count if available
                if self._current_state.items_processed > 0:
                    if self._current_state.expected_items:
                        message_parts.append(
                            f"({self._current_state.items_processed}/{self._current_state.expected_items} items)"
                        )
                    else:
                        message_parts.append(
                            f"({self._current_state.items_processed} items)"
                        )

                self._current_state.message = " ".join(message_parts)

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
        """Mark operation complete and cleanup with time estimation recording."""
        with self._lock:
            if self._current_state is None:
                logger.warning("complete_operation called without active operation")
                return

            # Record operation completion for time estimation
            if (
                self.enable_time_estimation
                and self._time_estimator
                and self._operation_start_time
                and self._current_operation_type
            ):

                duration = (datetime.now() - self._operation_start_time).total_seconds()
                self._time_estimator.record_operation_completion(
                    self._current_operation_type, self._current_context, duration
                )

            self._current_state.current_step = self._current_state.total_steps
            self._current_state.steps_completed = self._current_state.total_steps
            self._current_state.percentage = 100.0
            self._current_state.overall_percentage = 100.0

            # Create simple completion message (domain-specific enhancement moved to renderers)
            self._current_state.message = (
                f"Operation '{self._current_state.operation_id}' completed successfully"
            )
            self._current_state.estimated_remaining = timedelta(0)

            logger.info(
                "Operation '%s' completed successfully in %.2fs",
                self._current_state.operation_id,
                (
                    (datetime.now() - self._operation_start_time).total_seconds()
                    if self._operation_start_time
                    else 0
                ),
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
            elif hasattr(self._cancellation_token, "is_set"):
                # Handle asyncio.Event pattern
                return bool(self._cancellation_token.is_set())
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
                step_start_percentage=self._current_state.step_start_percentage,
                step_end_percentage=self._current_state.step_end_percentage,
                expected_items=self._current_state.expected_items,
                items_processed=self._current_state.items_processed,
                step_items_processed=self._current_state.step_items_processed,
                operation_context=self._current_state.operation_context,
                current_item_detail=self._current_state.current_item_detail,
                estimated_completion=self._current_state.estimated_completion,
                overall_percentage=self._current_state.overall_percentage,
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

        Passes the complete ProgressState to the callback for rich progress information.
        """
        if self.callback is None or self._current_state is None:
            return

        try:
            # Pass the complete ProgressState object to the callback
            self.callback(self.get_progress_state())
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

    # Domain-specific message enhancement logic REMOVED
    # This functionality has been moved to domain-specific progress renderers
    # (e.g., DataProgressRenderer for data operations)
    # Legacy ProgressManager now provides basic functionality only

    def _format_time_remaining(self, remaining: timedelta) -> str:
        """Format remaining time in user-friendly format."""
        total_seconds = int(remaining.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s remaining"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            if seconds > 0:
                return f"{minutes}m {seconds}s remaining"
            else:
                return f"{minutes}m remaining"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m remaining"
            else:
                return f"{hours}h remaining"

    def update_progress_with_context(
        self,
        step: int,
        base_message: str,
        context: Optional[dict[str, Any]] = None,
        current_item_detail: Optional[str] = None,
    ) -> None:
        """
        Enhanced progress update with contextual information.

        Args:
            step: Current step number
            base_message: Base progress message
            context: Optional additional context for this update
            current_item_detail: Optional detail about current item being processed
        """
        with self._lock:
            if self._current_state is None:
                return  # Skip if no operation active

            # Update current item detail in state
            if current_item_detail:
                self._current_state.current_item_detail = current_item_detail

            # Use simple message (domain-specific enhancement moved to renderers)
            self.update_progress(step, base_message)

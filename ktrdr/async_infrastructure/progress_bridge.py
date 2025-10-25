"""
ProgressBridge: Pull-based progress state container for worker threads.

This module implements the concrete ProgressBridge base class that provides
thread-safe, pull-based progress tracking for long-running operations.

Key characteristics:
- Pure synchronous: No async/await, safe for worker threads
- Pull-based: Consumers read on-demand, workers never block
- Thread-safe: RLock protects all state access
- Generic: Works with any operation type (training, data loading, etc.)
- Concrete: Fully implemented, can be used directly or subclassed

Architecture:
- Workers call protected helpers (_update_state, _append_metric)
- Consumers call public interface (get_status, get_metrics)
- State lives in memory with the worker (locality of reference)
- No I/O, no callbacks, just fast memory operations (<1μs)
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any


class ProgressBridge:
    """
    Concrete pull-based progress bridge - scenario-independent.

    This is a fully implemented base class that provides generic progress
    tracking for any type of long-running operation. Workers write progress
    via protected helper methods, consumers read via public interface.

    Thread Safety:
        Uses RLock for all state access. Safe for single-writer, multiple-reader
        pattern. All operations are atomic and non-blocking.

    Performance:
        Designed for <1μs worker overhead. All operations are memory-only,
        no I/O or external calls.

    Usage:
        Can be used directly for simple progress tracking, or subclassed for
        domain-specific behavior (training, data loading, etc.).

    Example:
        >>> bridge = ProgressBridge()
        >>> bridge._update_state(percentage=50.0, message="Halfway")
        >>> bridge._append_metric({"epoch": 5, "loss": 1.5})
        >>> status = bridge.get_status()
        >>> metrics, cursor = bridge.get_metrics(0)
    """

    def __init__(self) -> None:
        """
        Initialize progress bridge with empty state.

        Creates thread-safe storage for state and metrics history.
        No configuration needed - bridge is ready to use immediately.
        """
        self._lock = threading.RLock()
        self._current_state: dict[str, Any] = {}
        self._metrics_history: list[dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Public Pull Interface (called by OperationsService/consumers)
    # -------------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """
        Get current progress state snapshot (pull interface).

        Returns a copy of the current state, not a reference to internal state.
        Safe to call from any thread. Never blocks worker writes.

        Returns:
            dict: Current progress state with all fields set by _update_state().
                 Empty dict if no state has been set yet.

        Thread Safety:
            Acquires lock briefly to copy state. Multiple readers can query
            concurrently without blocking each other significantly.

        Performance:
            <1μs typical, just dict copy under lock.
        """
        with self._lock:
            return self._current_state.copy()

    def get_metrics(self, cursor: int = 0) -> tuple[list[dict[str, Any]], int]:
        """
        Get metrics since cursor (pull interface, incremental).

        Returns only metrics added since the given cursor position,
        enabling efficient incremental reads. Cursor is simply an index
        into the metrics history list.

        Args:
            cursor: Position in metrics history (0 = from beginning).
                   Typically the new_cursor returned from previous call.

        Returns:
            tuple: (new_metrics, new_cursor)
                - new_metrics: List of metric dicts since cursor
                - new_cursor: New cursor position for next incremental read

        Thread Safety:
            Acquires lock to slice metrics list. Safe for concurrent access.

        Performance:
            <1μs for typical cursor increments (returns slice of list).

        Example:
            >>> metrics, cursor = bridge.get_metrics(0)  # Get all
            >>> len(metrics)
            100
            >>> cursor
            100
            >>> # Later, get only new metrics
            >>> new_metrics, cursor = bridge.get_metrics(cursor)
            >>> len(new_metrics)
            10
            >>> cursor
            110
        """
        with self._lock:
            new_metrics = self._metrics_history[cursor:]
            new_cursor = len(self._metrics_history)
            return new_metrics, new_cursor

    # -------------------------------------------------------------------------
    # Protected Helpers (called by subclass on_* methods)
    # -------------------------------------------------------------------------

    def _update_state(self, percentage: float, message: str, **kwargs: Any) -> None:
        """
        Update current state (called by subclass on_* methods).

        Replaces entire state dict with new values. Always includes timestamp.
        This is the primary way workers report progress.

        Args:
            percentage: Progress percentage (0.0 - 100.0)
            message: Human-readable progress message
            **kwargs: Domain-specific fields (epoch, batch, symbol, etc.)

        Thread Safety:
            Acquires lock briefly to update state dict. Non-blocking for caller.

        Performance:
            <1μs typical - just dict assignment + timestamp.

        Example:
            >>> self._update_state(
            ...     percentage=55.0,
            ...     message="Epoch 55/100",
            ...     epoch=55,
            ...     total_epochs=100,
            ...     phase="training"
            ... )
        """
        with self._lock:
            self._current_state = {
                "percentage": percentage,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                **kwargs,  # Domain-specific fields
            }

    def _append_metric(self, metric: dict[str, Any]) -> None:
        """
        Append metric to history (called by subclass).

        Adds a metric record to the append-only history. Metric dict format
        is domain-specific (training: epoch metrics, data: symbol metrics, etc.).

        Args:
            metric: Metric dict to append. Should include timestamp if tracking
                   time-series metrics. Format is domain-specific.

        Thread Safety:
            Acquires lock briefly to append to list. Non-blocking for caller.

        Performance:
            <1μs typical - just list append.

        Example:
            >>> self._append_metric({
            ...     "epoch": 5,
            ...     "train_loss": 1.5,
            ...     "val_loss": 1.7,
            ...     "timestamp": datetime.now().isoformat()
            ... })
        """
        with self._lock:
            self._metrics_history.append(metric)

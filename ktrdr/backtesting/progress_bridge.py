"""BacktestProgressBridge: Progress tracking for backtesting operations.

This module provides a ProgressBridge subclass specifically designed for
backtesting operations, following the same pattern as TrainingProgressBridge.
"""

from typing import Any

from ktrdr.async_infrastructure.progress_bridge import ProgressBridge


class BacktestProgressBridge(ProgressBridge):
    """
    Backtesting-specific progress bridge.

    Provides thread-safe progress tracking for backtesting operations,
    following the same pull-based pattern as TrainingProgressBridge.

    Architecture:
    - Inherits thread-safe state management from ProgressBridge
    - Implements domain-specific update_progress() method
    - BacktestingEngine calls update_progress(), OperationsService pulls via get_status()

    Usage:
        >>> bridge = BacktestProgressBridge(
        ...     operation_id="op-123",
        ...     symbol="AAPL",
        ...     timeframe="1h",
        ...     total_bars=1000
        ... )
        >>> bridge.update_progress(
        ...     current_bar=500,
        ...     total_bars=1000,
        ...     current_date="2024-01-15",
        ...     current_pnl=1234.56,
        ...     total_trades=5,
        ...     win_rate=0.60
        ... )
        >>> status = bridge.get_status()
        >>> status["percentage"]
        50.0
    """

    def __init__(
        self,
        operation_id: str,
        symbol: str,
        timeframe: str,
        total_bars: int,
    ) -> None:
        """
        Initialize backtesting progress bridge.

        Args:
            operation_id: Unique operation identifier
            symbol: Trading symbol being backtested (e.g., "AAPL", "EURUSD")
            timeframe: Timeframe being tested (e.g., "1h", "1d")
            total_bars: Total number of bars to process

        Example:
            >>> bridge = BacktestProgressBridge(
            ...     operation_id="backtest-123",
            ...     symbol="AAPL",
            ...     timeframe="1h",
            ...     total_bars=1000
            ... )
        """
        # Initialize base class (sets up thread-safe storage)
        super().__init__()

        # Store backtesting metadata
        self.operation_id = operation_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.total_bars = total_bars

        # Task 3.7: Checkpoint state caching for cancellation checkpoints
        self._latest_checkpoint_data: dict[str, Any] = {}
        self.started_at: Any = None  # Set externally if needed

    def update_progress(
        self,
        current_bar: int,
        total_bars: int,
        current_date: str,
        current_pnl: float,
        total_trades: int,
        win_rate: float,
    ) -> None:
        """
        Update backtest progress (called by BacktestingEngine).

        This is a SYNC method - fast (<1μs), no I/O, thread-safe.
        Called by BacktestingEngine every N bars to report progress.

        Args:
            current_bar: Current bar being processed (0-indexed)
            total_bars: Total bars in backtest
            current_date: Current date being processed (ISO format)
            current_pnl: Current profit/loss (can be negative)
            total_trades: Total trades executed so far
            win_rate: Win rate (0.0 to 1.0)

        Example:
            >>> bridge.update_progress(
            ...     current_bar=500,
            ...     total_bars=1000,
            ...     current_date="2024-01-15 10:30:00",
            ...     current_pnl=1234.56,
            ...     total_trades=5,
            ...     win_rate=0.60
            ... )
        """
        # Calculate progress percentage (avoid division by zero)
        percentage = (current_bar / max(1, total_bars)) * 100.0

        # Format message with symbol, timeframe, and date
        message = f"Backtesting {self.symbol} {self.timeframe} [{current_date}]"

        # Update base class state (thread-safe via _update_state)
        self._update_state(
            percentage=percentage,
            message=message,
            current_bar=current_bar,
            total_bars=total_bars,
            current_date=current_date,
            current_pnl=current_pnl,
            total_trades=total_trades,
            win_rate=win_rate,
        )

    # ------------------------------------------------------------------
    # Task 3.7: Checkpoint State Caching (for cancellation checkpoints)
    # ------------------------------------------------------------------
    def set_latest_checkpoint_state(self, checkpoint_data: dict[str, Any]) -> None:
        """
        Cache latest checkpoint state for cancellation checkpoints.

        Called by BacktestingEngine periodically (e.g., every 100 bars) to cache
        domain-specific state (bar_index, portfolio, positions, trades) so it can
        be included in cancellation checkpoints.

        Args:
            checkpoint_data: Checkpoint state (bar_index, portfolio, trades, etc.)

        Example:
            >>> # Called by BacktestingEngine every 100 bars
            >>> bridge.set_latest_checkpoint_state({
            ...     "current_bar_index": 5000,
            ...     "current_timestamp": "2024-06-15T14:30:00",
            ...     "portfolio_state": {
            ...         "cash": 52000.0,
            ...         "positions": [{"symbol": "AAPL", "shares": 100}],
            ...     },
            ...     "trade_history": [...],
            ... })
        """
        with self._lock:
            self._latest_checkpoint_data = checkpoint_data.copy()

    async def get_state(self) -> dict[str, Any]:
        """
        Get complete operation state for checkpoint creation (async, called by OperationsService).

        Returns current progress state combined with cached checkpoint data.
        This method is called by OperationsService._get_operation_state() when creating
        cancellation checkpoints.

        Returns:
            dict: Complete state including:
                - operation_id: Operation identifier
                - operation_type: "backtesting"
                - status: "running" or "completed"
                - progress: Current progress state (percentage, message, etc.)
                - started_at: Operation start timestamp (ISO format)
                - checkpoint_data: Cached checkpoint state (if available)

        Example:
            >>> state = await bridge.get_state()
            >>> state["checkpoint_data"]["current_bar_index"]  # 5000
            >>> state["checkpoint_data"]["portfolio_state"]["cash"]  # 52000.0
        """
        with self._lock:
            # Get current progress state from base class
            current_progress = self._current_state.copy()

            # Build complete state
            state: dict[str, Any] = {
                "operation_id": self.operation_id,
                "operation_type": "backtesting",
                "status": "running",  # Assume running if bridge is alive
                "progress": current_progress,
            }

            # Add started_at if available
            if self.started_at is not None:
                state["started_at"] = (
                    self.started_at.isoformat()
                    if hasattr(self.started_at, "isoformat")
                    else str(self.started_at)
                )

            # Add cached checkpoint data (if available)
            if self._latest_checkpoint_data:
                state["checkpoint_data"] = self._latest_checkpoint_data.copy()

            return state

"""Backtesting checkpoint builder.

Builds checkpoint state from a BacktestingEngine for save/resume functionality.
"""

from typing import TYPE_CHECKING, Any, Optional

import pandas as pd

from ktrdr.checkpoint.schemas import BacktestCheckpointState

if TYPE_CHECKING:
    from ktrdr.backtesting.engine import BacktestingEngine

# Default equity sampling interval (every N bars)
DEFAULT_EQUITY_SAMPLE_INTERVAL = 100


def build_backtest_checkpoint_state(
    engine: "BacktestingEngine",
    bar_index: int,
    current_timestamp: pd.Timestamp,
    original_request: Optional[dict[str, Any]] = None,
    equity_sample_interval: int = DEFAULT_EQUITY_SAMPLE_INTERVAL,
) -> BacktestCheckpointState:
    """Extract checkpoint state from a BacktestingEngine.

    Args:
        engine: The BacktestingEngine instance with current state.
        bar_index: Current bar index in the simulation.
        current_timestamp: Timestamp of the current bar.
        original_request: Original backtest request for resume context.
            If not provided, extracted from engine.config.
        equity_sample_interval: Interval for sampling equity curve (default 100 bars).

    Returns:
        BacktestCheckpointState populated from the engine's state.
    """
    # Extract cash from position manager
    cash = engine.position_manager.current_capital

    # Extract current position (if any)
    positions = _extract_positions(engine)

    # Extract trade history
    trades = _extract_trades(engine)

    # Sample equity curve
    equity_samples = _sample_equity_curve(
        engine.performance_tracker.equity_curve,
        sample_interval=equity_sample_interval,
    )

    # Build original request from config if not provided
    if original_request is None:
        original_request = _build_original_request(engine)

    return BacktestCheckpointState(
        bar_index=bar_index,
        current_date=current_timestamp.isoformat(),
        cash=cash,
        positions=positions,
        trades=trades,
        equity_samples=equity_samples,
        original_request=original_request,
    )


def _extract_positions(engine: "BacktestingEngine") -> list[dict[str, Any]]:
    """Extract current open position from engine.

    Args:
        engine: The BacktestingEngine instance.

    Returns:
        List of position dictionaries (0 or 1 elements).
    """
    position = engine.position_manager.current_position
    if position is None:
        return []

    return [
        {
            "symbol": engine.config.symbol,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "entry_date": position.entry_time.isoformat(),
            "status": position.status.value,
            "current_price": position.current_price,
        }
    ]


def _extract_trades(engine: "BacktestingEngine") -> list[dict[str, Any]]:
    """Extract completed trade history from engine.

    Args:
        engine: The BacktestingEngine instance.

    Returns:
        List of trade dictionaries.
    """
    trades = []
    for trade in engine.position_manager.trade_history:
        trades.append(
            {
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "side": trade.side,
                "entry_price": trade.entry_price,
                "entry_time": trade.entry_time.isoformat(),
                "exit_price": trade.exit_price,
                "exit_time": trade.exit_time.isoformat(),
                "quantity": trade.quantity,
                "gross_pnl": trade.gross_pnl,
                "commission": trade.commission,
                "slippage": trade.slippage,
                "net_pnl": trade.net_pnl,
                "holding_period_hours": trade.holding_period_hours,
                "max_favorable_excursion": trade.max_favorable_excursion,
                "max_adverse_excursion": trade.max_adverse_excursion,
            }
        )
    return trades


def _sample_equity_curve(
    equity_curve: list[dict[str, Any]],
    sample_interval: int = DEFAULT_EQUITY_SAMPLE_INTERVAL,
) -> list[dict[str, Any]]:
    """Sample equity curve at regular intervals.

    Args:
        equity_curve: List of dicts with portfolio_value key.
        sample_interval: Sample every N bars.

    Returns:
        List of {bar_index, equity} dictionaries.
    """
    if not equity_curve:
        return []

    samples = []
    for i in range(0, len(equity_curve), sample_interval):
        row = equity_curve[i]
        samples.append(
            {
                "bar_index": i,
                "equity": float(row["portfolio_value"]),
            }
        )

    # Always include the last point if not already included
    last_index = len(equity_curve) - 1
    if last_index % sample_interval != 0:
        row = equity_curve[last_index]
        samples.append(
            {
                "bar_index": last_index,
                "equity": float(row["portfolio_value"]),
            }
        )

    return samples


def _build_original_request(engine: "BacktestingEngine") -> dict[str, Any]:
    """Build original request from engine config.

    Args:
        engine: The BacktestingEngine instance.

    Returns:
        Dictionary with original backtest request parameters.
    """
    config = engine.config
    return {
        "symbol": config.symbol,
        "timeframe": config.timeframe,
        "start_date": config.start_date,
        "end_date": config.end_date,
        "initial_capital": config.initial_capital,
        "commission": config.commission,
        "slippage": config.slippage,
    }

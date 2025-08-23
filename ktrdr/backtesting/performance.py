"""Performance analytics for backtesting system."""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .. import get_logger
from .position_manager import PositionStatus, Trade

logger = get_logger(__name__)


def sanitize_float_for_json(value: float) -> float:
    """Sanitize float values for JSON serialization.

    Args:
        value: Float value to sanitize

    Returns:
        JSON-safe float value (replaces inf/nan with safe values)
    """
    if math.isnan(value):
        return 0.0
    elif math.isinf(value):
        if value > 0:
            return 999999.0  # Large positive number instead of infinity
        else:
            return -999999.0  # Large negative number instead of -infinity
    else:
        return value


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""

    # Return metrics
    total_return: float
    total_return_pct: float
    annualized_return: float

    # Risk metrics
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float

    # Trade metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float

    # Timing metrics
    avg_holding_period: float
    avg_win_holding_period: float
    avg_loss_holding_period: float

    # P&L metrics
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float

    # Additional metrics
    calmar_ratio: float
    sortino_ratio: float
    recovery_factor: float

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary with JSON-safe float values."""
        return {
            "total_return": sanitize_float_for_json(self.total_return),
            "total_return_pct": sanitize_float_for_json(self.total_return_pct),
            "annualized_return": sanitize_float_for_json(self.annualized_return),
            "volatility": sanitize_float_for_json(self.volatility),
            "sharpe_ratio": sanitize_float_for_json(self.sharpe_ratio),
            "max_drawdown": sanitize_float_for_json(self.max_drawdown),
            "max_drawdown_pct": sanitize_float_for_json(self.max_drawdown_pct),
            "total_trades": self.total_trades,  # Integer, no sanitization needed
            "winning_trades": self.winning_trades,  # Integer, no sanitization needed
            "losing_trades": self.losing_trades,  # Integer, no sanitization needed
            "win_rate": sanitize_float_for_json(self.win_rate),
            "profit_factor": sanitize_float_for_json(self.profit_factor),
            "avg_holding_period": sanitize_float_for_json(self.avg_holding_period),
            "avg_win_holding_period": sanitize_float_for_json(
                self.avg_win_holding_period
            ),
            "avg_loss_holding_period": sanitize_float_for_json(
                self.avg_loss_holding_period
            ),
            "avg_win": sanitize_float_for_json(self.avg_win),
            "avg_loss": sanitize_float_for_json(self.avg_loss),
            "largest_win": sanitize_float_for_json(self.largest_win),
            "largest_loss": sanitize_float_for_json(self.largest_loss),
            "calmar_ratio": sanitize_float_for_json(self.calmar_ratio),
            "sortino_ratio": sanitize_float_for_json(self.sortino_ratio),
            "recovery_factor": sanitize_float_for_json(self.recovery_factor),
        }


class PerformanceTracker:
    """Track and calculate performance metrics during backtesting."""

    def __init__(self):
        """Initialize performance tracker."""
        self.equity_curve: list[dict[str, Any]] = []
        self.daily_returns: list[float] = []
        self.peak_equity = 0.0
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        self.last_equity = 0.0

    def update(
        self,
        timestamp: pd.Timestamp,
        price: float,
        portfolio_value: float,
        position: PositionStatus,
    ):
        """Update performance tracking with current state.

        Args:
            timestamp: Current timestamp
            price: Current market price
            portfolio_value: Current total portfolio value
            position: Current position status
        """
        # Record equity curve point
        equity_point = {
            "timestamp": timestamp,
            "price": price,
            "portfolio_value": portfolio_value,
            "position": position.value if hasattr(position, "value") else str(position),
        }
        self.equity_curve.append(equity_point)

        # Calculate daily return
        if self.last_equity > 0:
            daily_return = (portfolio_value - self.last_equity) / self.last_equity
            self.daily_returns.append(daily_return)

        # Update drawdown tracking
        if portfolio_value > self.peak_equity:
            self.peak_equity = portfolio_value
            self.current_drawdown = 0.0
        else:
            self.current_drawdown = (
                self.peak_equity - portfolio_value
            ) / self.peak_equity

            # CRITICAL DEBUG: Check for impossible drawdown values
            if self.current_drawdown > 1.0:
                logger.error(
                    f"🚨 IMPOSSIBLE DRAWDOWN: {self.current_drawdown:.4f} ({self.current_drawdown*100:.1f}%)"
                )
                logger.error(f"   Peak equity: ${self.peak_equity:,.2f}")
                logger.error(f"   Current portfolio: ${portfolio_value:,.2f}")
                logger.error(
                    f"   Difference: ${self.peak_equity - portfolio_value:,.2f}"
                )

            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)

            # CRITICAL DEBUG: Log when max drawdown updates
            if (
                self.current_drawdown == self.max_drawdown
                and self.current_drawdown > 0.1
            ):
                logger.warning(
                    f"📉 New max drawdown: {self.max_drawdown:.4f} ({self.max_drawdown*100:.1f}%) at portfolio ${portfolio_value:,.2f}"
                )

        self.last_equity = portfolio_value

    def calculate_metrics(
        self,
        trades: list[Trade],
        initial_capital: float,
        start_date: pd.Timestamp = None,
        end_date: pd.Timestamp = None,
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics.

        Args:
            trades: List of completed trades
            initial_capital: Initial capital amount
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            PerformanceMetrics object
        """
        if not self.equity_curve:
            # Return zero metrics if no data
            return self._zero_metrics()

        # Basic return metrics
        final_equity = self.equity_curve[-1]["portfolio_value"]
        total_return = final_equity - initial_capital
        total_return_pct = total_return / initial_capital  # Return as decimal 0-1

        # Calculate time period for annualization
        if start_date and end_date:
            days = (end_date - start_date).days
            years = days / 365.25
        else:
            years = len(self.equity_curve) / (252 * 6.5)  # Assume 6.5 hour trading day

        annualized_return = (
            ((final_equity / initial_capital) ** (1 / max(years, 0.001)) - 1)
            if years > 0
            else 0
        )  # Return as decimal 0-1

        # Volatility and Sharpe ratio with safe calculation
        if len(self.daily_returns) > 1:
            volatility = np.std(self.daily_returns) * np.sqrt(252)  # Annualized
            avg_return = np.mean(self.daily_returns)
            returns_std = np.std(self.daily_returns)

            if returns_std > 1e-10:  # Avoid division by near-zero values
                sharpe_ratio = (avg_return / returns_std) * np.sqrt(252)
                # Cap extreme values to prevent JSON serialization issues
                sharpe_ratio = max(-999999.0, min(999999.0, sharpe_ratio))
            else:
                sharpe_ratio = 0.0
        else:
            volatility = 0.0
            sharpe_ratio = 0.0

        # Trade analysis
        if trades:
            winning_trades = [t for t in trades if t.net_pnl > 0]
            losing_trades = [t for t in trades if t.net_pnl < 0]

            total_trades = len(trades)
            win_count = len(winning_trades)
            loss_count = len(losing_trades)
            win_rate = (
                (win_count / total_trades) if total_trades > 0 else 0
            )  # Return as decimal 0-1

            # P&L metrics
            total_wins = sum(t.net_pnl for t in winning_trades)
            total_losses = abs(sum(t.net_pnl for t in losing_trades))
            # Calculate profit factor with safe maximum value instead of infinity
            if total_losses > 0:
                profit_factor = total_wins / total_losses
            elif total_wins > 0:
                profit_factor = (
                    999999.0  # Very high but finite value instead of infinity
                )
            else:
                profit_factor = 0.0

            avg_win = (
                np.mean([t.net_pnl for t in winning_trades]) if winning_trades else 0
            )
            avg_loss = (
                np.mean([t.net_pnl for t in losing_trades]) if losing_trades else 0
            )
            largest_win = (
                max([t.net_pnl for t in winning_trades]) if winning_trades else 0
            )
            largest_loss = (
                min([t.net_pnl for t in losing_trades]) if losing_trades else 0
            )

            # Holding period analysis
            avg_holding_period = np.mean([t.holding_period_hours for t in trades])
            avg_win_holding_period = (
                np.mean([t.holding_period_hours for t in winning_trades])
                if winning_trades
                else 0
            )
            avg_loss_holding_period = (
                np.mean([t.holding_period_hours for t in losing_trades])
                if losing_trades
                else 0
            )
        else:
            total_trades = win_count = loss_count = 0
            win_rate = profit_factor = avg_win = avg_loss = 0
            largest_win = largest_loss = 0
            avg_holding_period = avg_win_holding_period = avg_loss_holding_period = 0

        # Max drawdown in absolute terms
        max_drawdown_abs = self.max_drawdown * self.peak_equity
        max_drawdown_pct = self.max_drawdown  # Already as decimal 0-1

        # CRITICAL DEBUG: Check for corrupted values
        logger.info("📊 Final metrics calculation:")
        logger.info(f"   self.max_drawdown: {self.max_drawdown:.6f}")
        logger.info(f"   self.peak_equity: ${self.peak_equity:,.2f}")
        logger.info(f"   max_drawdown_abs: ${max_drawdown_abs:,.2f}")
        logger.info(
            f"   max_drawdown_pct: {max_drawdown_pct:.6f} ({max_drawdown_pct*100:.2f}%)"
        )

        if max_drawdown_pct > 1.0:
            logger.error(
                f"🚨 IMPOSSIBLE: max_drawdown_pct {max_drawdown_pct:.6f} > 1.0!"
            )
        if self.peak_equity <= 0:
            logger.error(f"🚨 IMPOSSIBLE: peak_equity ${self.peak_equity:,.2f} <= 0!")
        if max_drawdown_abs < 0:
            logger.error(
                f"🚨 IMPOSSIBLE: max_drawdown_abs ${max_drawdown_abs:,.2f} < 0!"
            )

        # Additional risk metrics - Calmar ratio with safe division
        if max_drawdown_pct > 0:
            calmar_ratio = annualized_return / max_drawdown_pct
            # Cap extreme values to prevent JSON serialization issues
            calmar_ratio = max(-999999.0, min(999999.0, calmar_ratio))
        else:
            calmar_ratio = 0.0

        # Sortino ratio (downside deviation) with safe calculation
        negative_returns = [r for r in self.daily_returns if r < 0]
        downside_std = np.std(negative_returns) if negative_returns else 0
        if downside_std > 1e-10:  # Avoid division by near-zero values
            sortino_ratio = (np.mean(self.daily_returns) / downside_std) * np.sqrt(252)
            # Cap extreme values to prevent JSON serialization issues
            sortino_ratio = max(-999999.0, min(999999.0, sortino_ratio))
        else:
            sortino_ratio = 0.0

        # Recovery factor with safe calculation
        if max_drawdown_abs > 0:
            recovery_factor = total_return / max_drawdown_abs
            # Cap extreme values to prevent JSON serialization issues
            recovery_factor = max(-999999.0, min(999999.0, recovery_factor))
        else:
            recovery_factor = 0.0

        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown_abs,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            winning_trades=win_count,
            losing_trades=loss_count,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_holding_period=avg_holding_period,
            avg_win_holding_period=avg_win_holding_period,
            avg_loss_holding_period=avg_loss_holding_period,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            calmar_ratio=calmar_ratio,
            sortino_ratio=sortino_ratio,
            recovery_factor=recovery_factor,
        )

    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve as DataFrame.

        Returns:
            DataFrame with timestamp, price, portfolio_value, position columns
        """
        if not self.equity_curve:
            return pd.DataFrame()

        df = pd.DataFrame(self.equity_curve)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.set_index("timestamp")

    def get_drawdown_series(self) -> pd.Series:
        """Get drawdown series.

        Returns:
            Series with drawdown percentages over time
        """
        if not self.equity_curve:
            return pd.Series()

        equity_df = self.get_equity_curve()
        peak = equity_df["portfolio_value"].expanding().max()
        drawdown = (equity_df["portfolio_value"] - peak) / peak
        return drawdown

    def get_rolling_returns(self, window: int = 30) -> pd.Series:
        """Get rolling returns over specified window.

        Args:
            window: Number of periods for rolling calculation

        Returns:
            Series with rolling returns
        """
        if not self.equity_curve:
            return pd.Series()

        equity_df = self.get_equity_curve()
        returns = equity_df["portfolio_value"].pct_change()
        rolling_returns = returns.rolling(window).mean()
        return rolling_returns

    def _zero_metrics(self) -> PerformanceMetrics:
        """Return zero/empty metrics."""
        return PerformanceMetrics(
            total_return=0.0,
            total_return_pct=0.0,
            annualized_return=0.0,
            volatility=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_holding_period=0.0,
            avg_win_holding_period=0.0,
            avg_loss_holding_period=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            calmar_ratio=0.0,
            sortino_ratio=0.0,
            recovery_factor=0.0,
        )

    def reset(self):
        """Reset performance tracker."""
        self.equity_curve.clear()
        self.daily_returns.clear()
        self.peak_equity = 0.0
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        self.last_equity = 0.0

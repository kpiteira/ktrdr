"""Performance analytics for backtesting system."""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime

from .position_manager import Trade, PositionStatus


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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "annualized_return": self.annualized_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_holding_period": self.avg_holding_period,
            "avg_win_holding_period": self.avg_win_holding_period,
            "avg_loss_holding_period": self.avg_loss_holding_period,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "calmar_ratio": self.calmar_ratio,
            "sortino_ratio": self.sortino_ratio,
            "recovery_factor": self.recovery_factor
        }


class PerformanceTracker:
    """Track and calculate performance metrics during backtesting."""
    
    def __init__(self):
        """Initialize performance tracker."""
        self.equity_curve: List[Dict[str, Any]] = []
        self.daily_returns: List[float] = []
        self.peak_equity = 0.0
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        self.last_equity = 0.0
        
    def update(self, 
               timestamp: pd.Timestamp, 
               price: float,
               portfolio_value: float, 
               position: PositionStatus):
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
            "position": position.value if hasattr(position, 'value') else str(position)
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
            self.current_drawdown = (self.peak_equity - portfolio_value) / self.peak_equity
            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
        
        self.last_equity = portfolio_value
    
    def calculate_metrics(self, 
                         trades: List[Trade], 
                         initial_capital: float,
                         start_date: pd.Timestamp = None,
                         end_date: pd.Timestamp = None) -> PerformanceMetrics:
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
        total_return_pct = (total_return / initial_capital) * 100
        
        # Calculate time period for annualization
        if start_date and end_date:
            days = (end_date - start_date).days
            years = days / 365.25
        else:
            years = len(self.equity_curve) / (252 * 6.5)  # Assume 6.5 hour trading day
        
        annualized_return = ((final_equity / initial_capital) ** (1 / max(years, 0.001)) - 1) * 100 if years > 0 else 0
        
        # Volatility and Sharpe ratio
        if len(self.daily_returns) > 1:
            volatility = np.std(self.daily_returns) * np.sqrt(252) * 100  # Annualized
            avg_return = np.mean(self.daily_returns)
            sharpe_ratio = (avg_return / (np.std(self.daily_returns) + 1e-10)) * np.sqrt(252) if np.std(self.daily_returns) > 0 else 0
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
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            
            # P&L metrics
            total_wins = sum(t.net_pnl for t in winning_trades)
            total_losses = abs(sum(t.net_pnl for t in losing_trades))
            profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf') if total_wins > 0 else 0
            
            avg_win = np.mean([t.net_pnl for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t.net_pnl for t in losing_trades]) if losing_trades else 0
            largest_win = max([t.net_pnl for t in winning_trades]) if winning_trades else 0
            largest_loss = min([t.net_pnl for t in losing_trades]) if losing_trades else 0
            
            # Holding period analysis
            avg_holding_period = np.mean([t.holding_period_hours for t in trades])
            avg_win_holding_period = np.mean([t.holding_period_hours for t in winning_trades]) if winning_trades else 0
            avg_loss_holding_period = np.mean([t.holding_period_hours for t in losing_trades]) if losing_trades else 0
        else:
            total_trades = win_count = loss_count = 0
            win_rate = profit_factor = avg_win = avg_loss = 0
            largest_win = largest_loss = 0
            avg_holding_period = avg_win_holding_period = avg_loss_holding_period = 0
        
        # Max drawdown in absolute terms
        max_drawdown_abs = self.max_drawdown * self.peak_equity
        max_drawdown_pct = self.max_drawdown * 100
        
        # Additional risk metrics
        calmar_ratio = (annualized_return / max_drawdown_pct) if max_drawdown_pct > 0 else 0
        
        # Sortino ratio (downside deviation)
        negative_returns = [r for r in self.daily_returns if r < 0]
        downside_std = np.std(negative_returns) if negative_returns else 0
        sortino_ratio = (np.mean(self.daily_returns) / (downside_std + 1e-10)) * np.sqrt(252) if downside_std > 0 else 0
        
        # Recovery factor
        recovery_factor = (total_return / max_drawdown_abs) if max_drawdown_abs > 0 else 0
        
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
            recovery_factor=recovery_factor
        )
    
    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve as DataFrame.
        
        Returns:
            DataFrame with timestamp, price, portfolio_value, position columns
        """
        if not self.equity_curve:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.equity_curve)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df.set_index('timestamp')
    
    def get_drawdown_series(self) -> pd.Series:
        """Get drawdown series.
        
        Returns:
            Series with drawdown percentages over time
        """
        if not self.equity_curve:
            return pd.Series()
        
        equity_df = self.get_equity_curve()
        peak = equity_df['portfolio_value'].expanding().max()
        drawdown = (equity_df['portfolio_value'] - peak) / peak
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
        returns = equity_df['portfolio_value'].pct_change()
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
            recovery_factor=0.0
        )
    
    def reset(self):
        """Reset performance tracker."""
        self.equity_curve.clear()
        self.daily_returns.clear()
        self.peak_equity = 0.0
        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        self.last_equity = 0.0
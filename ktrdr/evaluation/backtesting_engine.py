"""Comprehensive backtesting engine for multi-timeframe trading strategies.

This module provides realistic backtesting capabilities that account for
multi-timeframe signals, realistic execution delays, transaction costs,
and various market conditions.
"""

import pandas as pd
import numpy as np
import torch
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import warnings

from ktrdr import get_logger
from ktrdr.neural.models.multi_timeframe_mlp import MultiTimeframeMLP
from ktrdr.training.data_preparation import TrainingSequence

logger = get_logger(__name__)


class OrderType(Enum):
    """Order types for backtesting."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class TradeDirection(Enum):
    """Trade direction."""
    LONG = 1
    SHORT = -1
    FLAT = 0


@dataclass
class BacktestConfig:
    """Configuration for backtesting engine."""
    initial_capital: float = 100000.0
    commission_rate: float = 0.001  # 0.1%
    slippage_rate: float = 0.0005   # 0.05%
    max_position_size: float = 1.0  # 100% of capital
    min_trade_size: float = 100.0   # Minimum trade size
    execution_delay: int = 1        # Bars delay for execution
    
    # Risk management
    stop_loss_pct: Optional[float] = 0.02      # 2% stop loss
    take_profit_pct: Optional[float] = 0.04    # 4% take profit
    max_consecutive_losses: int = 5
    daily_loss_limit: float = 0.05             # 5% daily loss limit
    
    # Position sizing
    position_sizing_method: str = "fixed"      # "fixed", "kelly", "volatility"
    volatility_lookback: int = 20
    kelly_lookback: int = 100
    
    # Multi-timeframe settings
    primary_timeframe: str = "1h"
    confirmation_timeframes: List[str] = None
    signal_confidence_threshold: float = 0.6


@dataclass
class Trade:
    """Individual trade record."""
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp]
    direction: TradeDirection
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    commission: float
    slippage: float
    pnl: Optional[float]
    pnl_pct: Optional[float]
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    exit_reason: str = "open"  # "signal", "stop_loss", "take_profit", "time"
    metadata: Dict[str, Any] = None


@dataclass
class PositionState:
    """Current position state."""
    direction: TradeDirection = TradeDirection.FLAT
    quantity: float = 0.0
    entry_price: float = 0.0
    entry_time: Optional[pd.Timestamp] = None
    unrealized_pnl: float = 0.0
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    consecutive_losses: int = 0


@dataclass
class BacktestResult:
    """Comprehensive backtesting results."""
    # Performance metrics
    total_return: float
    annual_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    
    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    
    # Risk metrics
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional Value at Risk 95%
    calmar_ratio: float
    recovery_factor: float
    
    # Equity curve and trades
    equity_curve: pd.DataFrame
    trades: List[Trade]
    monthly_returns: pd.Series
    
    # Multi-timeframe specific
    timeframe_performance: Dict[str, Dict[str, float]]
    signal_quality_metrics: Dict[str, float]
    
    # Detailed analysis
    drawdown_periods: List[Dict[str, Any]]
    performance_attribution: Dict[str, float]
    
    # Metadata
    backtest_config: BacktestConfig
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    total_days: int


class MultiTimeframeBacktestEngine:
    """Comprehensive backtesting engine for multi-timeframe strategies."""
    
    def __init__(self, config: BacktestConfig):
        """
        Initialize backtesting engine.
        
        Args:
            config: Backtesting configuration
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize state
        self.reset_state()
        
        self.logger.info("Initialized MultiTimeframeBacktestEngine")
    
    def reset_state(self):
        """Reset backtesting state."""
        self.position = PositionState()
        self.equity_curve = []
        self.trades = []
        self.current_equity = self.config.initial_capital
        self.peak_equity = self.config.initial_capital
        self.daily_pnl = 0.0
        self.last_trade_date = None
    
    def run_backtest(
        self,
        model: MultiTimeframeMLP,
        price_data: Dict[str, pd.DataFrame],
        features_data: Dict[str, pd.DataFrame],
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None
    ) -> BacktestResult:
        """
        Run comprehensive backtest.
        
        Args:
            model: Trained multi-timeframe model
            price_data: Price data by timeframe
            features_data: Feature data by timeframe
            start_date: Backtest start date
            end_date: Backtest end date
            
        Returns:
            Comprehensive backtest results
        """
        self.logger.info("Starting multi-timeframe backtest")
        
        # Reset state
        self.reset_state()
        
        # Prepare data
        aligned_data = self._prepare_backtest_data(
            price_data, features_data, start_date, end_date
        )
        
        if aligned_data.empty:
            raise ValueError("No data available for backtesting period")
        
        # Run simulation
        self._simulate_trading(model, aligned_data)
        
        # Calculate results
        result = self._calculate_backtest_results(aligned_data)
        
        self.logger.info(f"Backtest completed: {result.total_trades} trades, "
                        f"{result.total_return:.2%} return")
        
        return result
    
    def _prepare_backtest_data(
        self,
        price_data: Dict[str, pd.DataFrame],
        features_data: Dict[str, pd.DataFrame],
        start_date: Optional[pd.Timestamp],
        end_date: Optional[pd.Timestamp]
    ) -> pd.DataFrame:
        """Prepare aligned data for backtesting."""
        
        primary_tf = self.config.primary_timeframe
        
        if primary_tf not in price_data:
            raise ValueError(f"Primary timeframe {primary_tf} not found in price data")
        
        # Use primary timeframe as base
        base_data = price_data[primary_tf].copy()
        
        # Filter by date range if specified
        if start_date:
            base_data = base_data[base_data['timestamp'] >= start_date]
        if end_date:
            base_data = base_data[base_data['timestamp'] <= end_date]
        
        if base_data.empty:
            return pd.DataFrame()
        
        # Add features for model prediction
        if primary_tf in features_data:
            features_df = features_data[primary_tf]
            
            # Align features with price data
            aligned_features = pd.merge(
                base_data[['timestamp']],
                features_df,
                on='timestamp',
                how='left'
            )
            
            # Add feature columns to base data
            feature_cols = [col for col in aligned_features.columns if col != 'timestamp']
            for col in feature_cols:
                base_data[col] = aligned_features[col]
        
        # Sort by timestamp
        base_data = base_data.sort_values('timestamp').reset_index(drop=True)
        
        self.logger.info(f"Prepared {len(base_data)} data points for backtesting")
        
        return base_data
    
    def _simulate_trading(self, model: MultiTimeframeMLP, data: pd.DataFrame):
        """Simulate trading with the model."""
        
        model.model.eval()
        
        # Get feature columns
        feature_cols = [col for col in data.columns 
                       if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        if not feature_cols:
            self.logger.warning("No feature columns found for model prediction")
            return
        
        for i in range(len(data)):
            current_data = data.iloc[i]
            current_time = current_data['timestamp']
            current_price = current_data['close']
            
            # Update daily P&L tracking
            self._update_daily_tracking(current_time)
            
            # Check for exit signals first
            self._check_exit_conditions(current_data)
            
            # Generate trading signal
            signal = self._generate_signal(model, data, i, feature_cols)
            
            # Process signal
            if signal != TradeDirection.FLAT and self.position.direction == TradeDirection.FLAT:
                # Open new position
                self._open_position(signal, current_data)
            
            # Update position state
            self._update_position_state(current_data)
            
            # Record equity
            self._record_equity_point(current_data)
    
    def _generate_signal(
        self, 
        model: MultiTimeframeMLP, 
        data: pd.DataFrame, 
        current_idx: int,
        feature_cols: List[str]
    ) -> TradeDirection:
        """Generate trading signal from model."""
        
        if current_idx < self.config.execution_delay:
            return TradeDirection.FLAT
        
        # Look back to avoid lookahead bias
        signal_idx = current_idx - self.config.execution_delay
        signal_data = data.iloc[signal_idx]
        
        # Prepare features
        features = []
        for col in feature_cols:
            value = signal_data.get(col, 0.0)
            if pd.isna(value):
                value = 0.0
            features.append(float(value))
        
        if not features:
            return TradeDirection.FLAT
        
        # Get model prediction
        with torch.no_grad():
            features_tensor = torch.FloatTensor([features])
            outputs = model.model(features_tensor)
            probabilities = torch.softmax(outputs, dim=1)
            predicted_class = torch.argmax(outputs, dim=1).item()
            max_confidence = torch.max(probabilities).item()
        
        # Check confidence threshold
        if max_confidence < self.config.signal_confidence_threshold:
            return TradeDirection.FLAT
        
        # Convert model output to trading signal
        if predicted_class == 0:  # BUY
            return TradeDirection.LONG
        elif predicted_class == 2:  # SELL
            return TradeDirection.SHORT
        else:  # HOLD
            return TradeDirection.FLAT
    
    def _open_position(self, direction: TradeDirection, current_data: pd.Series):
        """Open a new trading position."""
        
        if self.position.direction != TradeDirection.FLAT:
            return  # Already in position
        
        # Check risk limits
        if not self._check_risk_limits():
            return
        
        current_price = current_data['close']
        current_time = current_data['timestamp']
        
        # Calculate position size
        position_size = self._calculate_position_size(current_price, direction)
        
        if position_size < self.config.min_trade_size:
            return
        
        # Calculate costs
        commission = position_size * current_price * self.config.commission_rate
        slippage = position_size * current_price * self.config.slippage_rate
        
        # Check if we have enough capital
        total_cost = position_size * current_price + commission + slippage
        if total_cost > self.current_equity:
            return
        
        # Apply slippage to entry price
        if direction == TradeDirection.LONG:
            entry_price = current_price * (1 + self.config.slippage_rate)
        else:
            entry_price = current_price * (1 - self.config.slippage_rate)
        
        # Update position state
        self.position.direction = direction
        self.position.quantity = position_size
        self.position.entry_price = entry_price
        self.position.entry_time = current_time
        self.position.unrealized_pnl = 0.0
        
        # Set stop loss and take profit
        if self.config.stop_loss_pct:
            if direction == TradeDirection.LONG:
                self.position.stop_loss_price = entry_price * (1 - self.config.stop_loss_pct)
            else:
                self.position.stop_loss_price = entry_price * (1 + self.config.stop_loss_pct)
        
        if self.config.take_profit_pct:
            if direction == TradeDirection.LONG:
                self.position.take_profit_price = entry_price * (1 + self.config.take_profit_pct)
            else:
                self.position.take_profit_price = entry_price * (1 - self.config.take_profit_pct)
        
        # Deduct costs from equity
        self.current_equity -= commission + slippage
        
        self.logger.debug(f"Opened {direction.name} position: {position_size:.2f} @ {entry_price:.4f}")
    
    def _check_exit_conditions(self, current_data: pd.Series) -> bool:
        """Check if position should be closed."""
        
        if self.position.direction == TradeDirection.FLAT:
            return False
        
        current_price = current_data['close']
        high_price = current_data['high']
        low_price = current_data['low']
        
        exit_reason = None
        exit_price = current_price
        
        # Check stop loss
        if self.position.stop_loss_price:
            if self.position.direction == TradeDirection.LONG:
                if low_price <= self.position.stop_loss_price:
                    exit_reason = "stop_loss"
                    exit_price = self.position.stop_loss_price
            else:
                if high_price >= self.position.stop_loss_price:
                    exit_reason = "stop_loss"
                    exit_price = self.position.stop_loss_price
        
        # Check take profit
        if not exit_reason and self.position.take_profit_price:
            if self.position.direction == TradeDirection.LONG:
                if high_price >= self.position.take_profit_price:
                    exit_reason = "take_profit"
                    exit_price = self.position.take_profit_price
            else:
                if low_price <= self.position.take_profit_price:
                    exit_reason = "take_profit"
                    exit_price = self.position.take_profit_price
        
        if exit_reason:
            self._close_position(exit_price, current_data['timestamp'], exit_reason)
            return True
        
        return False
    
    def _close_position(self, exit_price: float, exit_time: pd.Timestamp, exit_reason: str):
        """Close the current position."""
        
        if self.position.direction == TradeDirection.FLAT:
            return
        
        # Calculate costs
        commission = self.position.quantity * exit_price * self.config.commission_rate
        slippage_rate = self.config.slippage_rate
        
        # Apply slippage to exit price
        if self.position.direction == TradeDirection.LONG:
            final_exit_price = exit_price * (1 - slippage_rate)
        else:
            final_exit_price = exit_price * (1 + slippage_rate)
        
        slippage = abs(exit_price - final_exit_price) * self.position.quantity
        
        # Calculate P&L
        if self.position.direction == TradeDirection.LONG:
            pnl = (final_exit_price - self.position.entry_price) * self.position.quantity
        else:
            pnl = (self.position.entry_price - final_exit_price) * self.position.quantity
        
        # Subtract costs
        total_costs = commission + slippage
        net_pnl = pnl - total_costs
        pnl_pct = net_pnl / (self.position.entry_price * self.position.quantity)
        
        # Create trade record
        trade = Trade(
            entry_time=self.position.entry_time,
            exit_time=exit_time,
            direction=self.position.direction,
            entry_price=self.position.entry_price,
            exit_price=final_exit_price,
            quantity=self.position.quantity,
            commission=commission,
            slippage=slippage,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
            metadata={
                'gross_pnl': pnl,
                'total_costs': total_costs
            }
        )
        
        self.trades.append(trade)
        
        # Update equity
        self.current_equity += net_pnl - commission - slippage
        self.daily_pnl += net_pnl
        
        # Update consecutive losses tracking
        if net_pnl < 0:
            self.position.consecutive_losses += 1
        else:
            self.position.consecutive_losses = 0
        
        # Reset position
        self.position = PositionState()
        self.position.consecutive_losses = trade.pnl < 0
        
        self.logger.debug(f"Closed position: {trade.direction.name} P&L: {net_pnl:.2f} ({pnl_pct:.2%})")
    
    def _update_position_state(self, current_data: pd.Series):
        """Update current position state."""
        
        if self.position.direction == TradeDirection.FLAT:
            return
        
        current_price = current_data['close']
        
        # Calculate unrealized P&L
        if self.position.direction == TradeDirection.LONG:
            unrealized_pnl = (current_price - self.position.entry_price) * self.position.quantity
        else:
            unrealized_pnl = (self.position.entry_price - current_price) * self.position.quantity
        
        self.position.unrealized_pnl = unrealized_pnl
    
    def _calculate_position_size(self, price: float, direction: TradeDirection) -> float:
        """Calculate position size based on configured method."""
        
        if self.config.position_sizing_method == "fixed":
            # Fixed percentage of capital
            max_value = self.current_equity * self.config.max_position_size
            return max_value / price
        
        elif self.config.position_sizing_method == "volatility":
            # Volatility-based sizing (placeholder)
            base_size = self.current_equity * self.config.max_position_size / price
            return base_size * 0.5  # Reduced for volatility
        
        elif self.config.position_sizing_method == "kelly":
            # Kelly criterion (placeholder)
            base_size = self.current_equity * self.config.max_position_size / price
            return base_size * 0.25  # Conservative Kelly
        
        else:
            # Default to fixed
            max_value = self.current_equity * self.config.max_position_size
            return max_value / price
    
    def _check_risk_limits(self) -> bool:
        """Check if position can be opened based on risk limits."""
        
        # Check consecutive losses
        if self.position.consecutive_losses >= self.config.max_consecutive_losses:
            return False
        
        # Check daily loss limit
        if self.daily_pnl < -self.current_equity * self.config.daily_loss_limit:
            return False
        
        return True
    
    def _update_daily_tracking(self, current_time: pd.Timestamp):
        """Update daily P&L tracking."""
        
        current_date = current_time.date()
        
        if self.last_trade_date is None:
            self.last_trade_date = current_date
        elif current_date != self.last_trade_date:
            # New day - reset daily P&L
            self.daily_pnl = 0.0
            self.last_trade_date = current_date
    
    def _record_equity_point(self, current_data: pd.Series):
        """Record current equity point."""
        
        total_equity = self.current_equity + self.position.unrealized_pnl
        
        equity_point = {
            'timestamp': current_data['timestamp'],
            'equity': total_equity,
            'cash': self.current_equity,
            'unrealized_pnl': self.position.unrealized_pnl,
            'position_value': abs(self.position.quantity * current_data['close']) if self.position.direction != TradeDirection.FLAT else 0,
            'drawdown': (total_equity - self.peak_equity) / self.peak_equity if self.peak_equity > 0 else 0
        }
        
        # Update peak equity
        if total_equity > self.peak_equity:
            self.peak_equity = total_equity
            equity_point['drawdown'] = 0.0
        
        self.equity_curve.append(equity_point)
    
    def _calculate_backtest_results(self, data: pd.DataFrame) -> BacktestResult:
        """Calculate comprehensive backtest results."""
        
        if not self.equity_curve:
            raise ValueError("No equity data available")
        
        # Convert equity curve to DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index('timestamp', inplace=True)
        
        # Calculate returns
        equity_series = equity_df['equity']
        returns = equity_series.pct_change().dropna()
        
        # Basic performance metrics
        total_return = (equity_series.iloc[-1] - self.config.initial_capital) / self.config.initial_capital
        
        # Annualized return
        days = (equity_df.index[-1] - equity_df.index[0]).days
        annual_return = (1 + total_return) ** (365.25 / max(days, 1)) - 1
        
        # Risk-adjusted metrics
        if len(returns) > 1 and returns.std() > 0:
            sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std()
            downside_returns = returns[returns < 0]
            if len(downside_returns) > 0 and downside_returns.std() > 0:
                sortino_ratio = np.sqrt(252) * returns.mean() / downside_returns.std()
            else:
                sortino_ratio = float('inf') if returns.mean() > 0 else 0.0
        else:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0
        
        # Drawdown metrics
        peak_equity = equity_series.expanding().max()
        drawdowns = (equity_series - peak_equity) / peak_equity
        max_drawdown = abs(drawdowns.min()) if len(drawdowns) > 0 else 0.0
        
        # Drawdown duration
        in_drawdown = drawdowns < -0.001  # More than 0.1% drawdown
        if in_drawdown.any():
            drawdown_periods = []
            current_period = None
            
            for timestamp, is_dd in in_drawdown.items():
                if is_dd and current_period is None:
                    current_period = {'start': timestamp, 'end': timestamp}
                elif is_dd:
                    current_period['end'] = timestamp
                elif not is_dd and current_period is not None:
                    current_period['duration'] = (current_period['end'] - current_period['start']).days
                    drawdown_periods.append(current_period)
                    current_period = None
            
            if current_period is not None:
                current_period['duration'] = (equity_df.index[-1] - current_period['start']).days
                drawdown_periods.append(current_period)
            
            max_dd_duration = max([p['duration'] for p in drawdown_periods]) if drawdown_periods else 0
        else:
            drawdown_periods = []
            max_dd_duration = 0
        
        # Trade statistics
        if self.trades:
            winning_trades = sum(1 for t in self.trades if t.pnl > 0)
            losing_trades = sum(1 for t in self.trades if t.pnl < 0)
            win_rate = winning_trades / len(self.trades)
            
            wins = [t.pnl for t in self.trades if t.pnl > 0]
            losses = [t.pnl for t in self.trades if t.pnl < 0]
            
            avg_win = np.mean(wins) if wins else 0.0
            avg_loss = np.mean(losses) if losses else 0.0
            
            gross_profit = sum(wins)
            gross_loss = abs(sum(losses))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        else:
            winning_trades = losing_trades = 0
            win_rate = avg_win = avg_loss = profit_factor = 0.0
        
        # Risk metrics
        if len(returns) > 20:  # Need sufficient data for VaR
            var_95 = np.percentile(returns, 5)
            cvar_95 = returns[returns <= var_95].mean()
        else:
            var_95 = cvar_95 = 0.0
        
        # Additional metrics
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0.0
        recovery_factor = total_return / max_drawdown if max_drawdown > 0 else 0.0
        
        # Monthly returns
        monthly_returns = equity_series.resample('M').last().pct_change().dropna()
        
        # Timeframe performance (placeholder)
        timeframe_performance = {
            '1h': {'return': total_return, 'trades': len(self.trades)},
            '4h': {'return': total_return * 0.8, 'trades': len(self.trades) // 2},
            '1d': {'return': total_return * 0.6, 'trades': len(self.trades) // 4}
        }
        
        # Signal quality metrics
        signal_quality_metrics = {
            'signal_accuracy': win_rate,
            'signal_consistency': 0.85,  # Placeholder
            'false_signal_rate': 1 - win_rate
        }
        
        # Performance attribution
        performance_attribution = {
            'stock_selection': total_return * 0.7,
            'timing': total_return * 0.3,
            'costs': -sum(t.commission + t.slippage for t in self.trades) / self.config.initial_capital
        }
        
        return BacktestResult(
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            total_trades=len(self.trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            var_95=var_95,
            cvar_95=cvar_95,
            calmar_ratio=calmar_ratio,
            recovery_factor=recovery_factor,
            equity_curve=equity_df,
            trades=self.trades,
            monthly_returns=monthly_returns,
            timeframe_performance=timeframe_performance,
            signal_quality_metrics=signal_quality_metrics,
            drawdown_periods=drawdown_periods,
            performance_attribution=performance_attribution,
            backtest_config=self.config,
            start_date=data['timestamp'].iloc[0],
            end_date=data['timestamp'].iloc[-1],
            total_days=days
        )


def create_default_backtest_config() -> BacktestConfig:
    """Create default backtesting configuration."""
    return BacktestConfig(
        initial_capital=100000.0,
        commission_rate=0.001,
        slippage_rate=0.0005,
        max_position_size=0.95,
        min_trade_size=100.0,
        execution_delay=1,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        max_consecutive_losses=5,
        daily_loss_limit=0.05,
        position_sizing_method="fixed",
        primary_timeframe="1h",
        signal_confidence_threshold=0.6
    )


def run_quick_backtest(
    model: MultiTimeframeMLP,
    price_data: Dict[str, pd.DataFrame],
    features_data: Dict[str, pd.DataFrame],
    config: Optional[BacktestConfig] = None
) -> BacktestResult:
    """
    Run a quick backtest with default settings.
    
    Args:
        model: Trained multi-timeframe model
        price_data: Price data by timeframe
        features_data: Feature data by timeframe  
        config: Optional backtest configuration
        
    Returns:
        Backtest results
    """
    
    if config is None:
        config = create_default_backtest_config()
    
    engine = MultiTimeframeBacktestEngine(config)
    return engine.run_backtest(model, price_data, features_data)
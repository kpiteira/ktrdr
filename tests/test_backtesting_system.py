"""Tests for Phase 4: Backtesting System."""

import pytest
import pandas as pd
import numpy as np
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from ktrdr.backtesting import (
    PositionManager,
    PositionStatus,
    Trade,
    PerformanceTracker,
    PerformanceMetrics,
    BacktestingEngine,
    BacktestConfig,
)
from ktrdr.decision.base import Signal
from ktrdr.training import ModelStorage
import torch


class TestPositionManager:
    """Test position management functionality."""

    def test_position_manager_initialization(self):
        """Test position manager initialization."""
        pm = PositionManager(initial_capital=100000, commission=0.001, slippage=0.0005)

        assert pm.initial_capital == 100000
        assert pm.current_capital == 100000
        assert pm.commission == 0.001
        assert pm.slippage == 0.0005
        assert pm.current_position is None
        assert pm.current_position_status == PositionStatus.FLAT
        assert pm.available_capital == 100000

    def test_buy_execution(self):
        """Test buy order execution."""
        pm = PositionManager(initial_capital=100000, commission=0.001, slippage=0.0005)

        # Execute buy
        can_buy = pm.can_execute_trade(Signal.BUY, 100.0)
        assert can_buy

        trade = pm.execute_trade(
            signal=Signal.BUY,
            price=100.0,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            symbol="AAPL",
        )

        # Buy creates a partial trade record (improved tracking)
        assert trade is not None
        assert trade.side == "BUY_ENTRY"
        assert trade.symbol == "AAPL"
        assert pm.current_position is not None
        assert pm.current_position_status == PositionStatus.LONG
        assert pm.current_position.entry_price == 100.05  # Price + slippage
        assert pm.current_capital < 100000  # Capital reduced by purchase

    def test_sell_execution(self):
        """Test sell order execution and trade completion."""
        pm = PositionManager(initial_capital=100000, commission=0.001, slippage=0.0005)

        # First buy
        pm.execute_trade(
            signal=Signal.BUY,
            price=100.0,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            symbol="AAPL",
        )

        initial_position = pm.current_position
        assert initial_position is not None

        # Update position with new price
        pm.update_position(105.0, pd.Timestamp("2024-01-01 11:00:00"))

        # Then sell
        trade = pm.execute_trade(
            signal=Signal.SELL,
            price=105.0,
            timestamp=pd.Timestamp("2024-01-01 11:00:00"),
            symbol="AAPL",
        )

        # Should create a completed trade
        assert trade is not None
        assert isinstance(trade, Trade)
        assert trade.side == "LONG"
        assert trade.entry_price == 100.05  # Buy price with slippage
        assert trade.exit_price == 104.9475  # Sell price with slippage
        assert trade.net_pnl > 0  # Should be profitable
        assert pm.current_position is None  # Position closed
        assert pm.current_position_status == PositionStatus.FLAT

    def test_position_update(self):
        """Test position value updates."""
        pm = PositionManager(initial_capital=100000)

        # Create position
        pm.execute_trade(
            signal=Signal.BUY,
            price=100.0,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            symbol="AAPL",
        )

        # Update with profitable price
        pm.update_position(110.0, pd.Timestamp("2024-01-01 11:00:00"))

        assert pm.current_position.current_price == 110.0
        assert pm.current_position.unrealized_pnl > 0
        assert pm.current_position.max_favorable_excursion > 0

        # Update with loss
        pm.update_position(95.0, pd.Timestamp("2024-01-01 12:00:00"))

        assert pm.current_position.unrealized_pnl < 0
        assert pm.current_position.max_adverse_excursion < 0

    def test_portfolio_value_calculation(self):
        """Test portfolio value calculation."""
        pm = PositionManager(initial_capital=100000)

        # Initial value
        assert pm.get_portfolio_value(100.0) == 100000

        # After buy
        pm.execute_trade(
            signal=Signal.BUY,
            price=100.0,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            symbol="AAPL",
        )

        # Portfolio value at same price (should be slightly less due to transaction costs)
        portfolio_value_same = pm.get_portfolio_value(100.0)
        assert portfolio_value_same < 100000  # Less due to commission and slippage

        # Portfolio value at higher price (should show unrealized gains)
        portfolio_value_higher = pm.get_portfolio_value(105.0)
        assert portfolio_value_higher > portfolio_value_same  # Should be higher
        assert portfolio_value_higher > pm.current_capital  # More than just cash

        # Check that portfolio value increases with higher prices (directional test)
        if pm.current_position:
            # Portfolio should be profitable at higher price than entry
            assert (
                portfolio_value_higher > 100000
            )  # Should show gains above initial capital


class TestPerformanceTracker:
    """Test performance tracking functionality."""

    def test_performance_tracker_initialization(self):
        """Test performance tracker initialization."""
        tracker = PerformanceTracker()

        assert len(tracker.equity_curve) == 0
        assert len(tracker.daily_returns) == 0
        assert tracker.peak_equity == 0.0
        assert tracker.max_drawdown == 0.0

    def test_equity_curve_tracking(self):
        """Test equity curve tracking."""
        tracker = PerformanceTracker()

        # Add some equity points
        timestamps = pd.date_range("2024-01-01", periods=5, freq="1h")
        portfolio_values = [100000, 101000, 99000, 102000, 98000]

        for i, (ts, value) in enumerate(zip(timestamps, portfolio_values)):
            tracker.update(
                timestamp=ts,
                price=100 + i,
                portfolio_value=value,
                position=PositionStatus.FLAT,
            )

        assert len(tracker.equity_curve) == 5

        # Get equity curve as DataFrame
        equity_df = tracker.get_equity_curve()
        assert len(equity_df) == 5
        assert "portfolio_value" in equity_df.columns
        assert "price" in equity_df.columns

    def test_drawdown_calculation(self):
        """Test drawdown calculation."""
        tracker = PerformanceTracker()

        # Simulate equity curve with drawdown
        portfolio_values = [100000, 110000, 105000, 95000, 115000]
        timestamps = pd.date_range("2024-01-01", periods=5, freq="1h")

        for ts, value in zip(timestamps, portfolio_values):
            tracker.update(
                timestamp=ts,
                price=100.0,
                portfolio_value=value,
                position=PositionStatus.FLAT,
            )

        # Max drawdown should be calculated
        assert tracker.max_drawdown > 0
        assert tracker.peak_equity == 115000  # Final peak

    def test_metrics_calculation(self):
        """Test performance metrics calculation."""
        tracker = PerformanceTracker()

        # Create sample equity curve
        portfolio_values = [100000, 105000, 102000, 108000, 106000]
        timestamps = pd.date_range("2024-01-01", periods=5, freq="1D")

        for ts, value in zip(timestamps, portfolio_values):
            tracker.update(
                timestamp=ts,
                price=100.0,
                portfolio_value=value,
                position=PositionStatus.FLAT,
            )

        # Create sample trades
        trades = [
            create_sample_trade(1, 2000, 24),
            create_sample_trade(2, -500, 12),
            create_sample_trade(3, 1500, 36),
        ]

        metrics = tracker.calculate_metrics(
            trades=trades,
            initial_capital=100000,
            start_date=timestamps[0],
            end_date=timestamps[-1],
        )

        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.win_rate == pytest.approx(
            0.6667, rel=1e-2
        )  # Decimal ratio, not percentage
        assert metrics.total_return == 6000  # Final - initial


class TestBacktestingEngine:
    """Test backtesting engine functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.models_dir = Path(self.temp_dir) / "models"
        self.strategies_dir = Path(self.temp_dir) / "strategies"
        self.strategies_dir.mkdir(parents=True)

        # Create test strategy config
        self.strategy_config = {
            "name": "test_backtest_strategy",
            "indicators": [
                {"name": "rsi", "period": 14, "source": "close"},
                {"name": "sma", "period": 20, "source": "close"},
            ],
            "fuzzy_sets": {
                "rsi": {
                    "oversold": {"type": "triangular", "parameters": [0, 10, 30]},
                    "neutral": {"type": "triangular", "parameters": [25, 50, 75]},
                    "overbought": {"type": "triangular", "parameters": [70, 90, 100]},
                }
            },
            "model": {
                "type": "mlp",
                "architecture": {
                    "hidden_layers": [10, 5],
                    "activation": "relu",
                    "dropout": 0.2,
                },
                "features": {"include_price_context": True, "lookback_periods": 2},
            },
            "decisions": {"confidence_threshold": 0.6, "position_awareness": True},
        }

        self.strategy_path = self.strategies_dir / "test_backtest_strategy.yaml"
        import yaml

        with open(self.strategy_path, "w") as f:
            yaml.dump(self.strategy_config, f)

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_backtest_config_creation(self):
        """Test backtest configuration creation."""
        config = BacktestConfig(
            strategy_config_path=str(self.strategy_path),
            model_path=None,
            symbol="AAPL",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=50000,
            commission=0.002,
            slippage=0.001,
        )

        assert config.symbol == "AAPL"
        assert config.timeframe == "1h"
        assert config.initial_capital == 50000
        assert config.commission == 0.002
        assert config.slippage == 0.001

    def test_backtesting_engine_initialization(self):
        """Test backtesting engine initialization."""
        config = BacktestConfig(
            strategy_config_path=str(self.strategy_path),
            model_path=None,
            symbol="AAPL",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-31",
        )

        engine = BacktestingEngine(config)

        assert engine.config == config
        assert engine.strategy_name == "test_backtest_strategy"
        assert engine.position_manager is not None
        assert engine.performance_tracker is not None
        assert engine.orchestrator is not None


def create_sample_trade(trade_id: int, net_pnl: float, holding_hours: float) -> Trade:
    """Create a sample trade for testing.

    Args:
        trade_id: Trade ID
        net_pnl: Net P&L
        holding_hours: Holding period in hours

    Returns:
        Sample Trade object
    """
    entry_time = pd.Timestamp("2024-01-01 10:00:00")
    exit_time = entry_time + pd.Timedelta(hours=holding_hours)

    return Trade(
        trade_id=trade_id,
        symbol="AAPL",
        side="LONG",
        entry_price=100.0,
        entry_time=entry_time,
        exit_price=100.0 + (net_pnl / 100),  # Simplified calculation
        exit_time=exit_time,
        quantity=100,
        gross_pnl=net_pnl + 10,  # Add some commission
        commission=10.0,
        slippage=5.0,
        net_pnl=net_pnl,
        holding_period_hours=holding_hours,
        max_favorable_excursion=max(net_pnl, 0),
        max_adverse_excursion=min(net_pnl, 0),
    )


def create_sample_price_data(
    n_periods: int = 100, start_price: float = 100.0
) -> pd.DataFrame:
    """Create sample price data for testing.

    Args:
        n_periods: Number of periods
        start_price: Starting price

    Returns:
        DataFrame with OHLCV data
    """
    dates = pd.date_range("2024-01-01", periods=n_periods, freq="1h")

    # Generate random walk prices
    returns = np.random.normal(0, 0.01, n_periods)
    prices = start_price * np.exp(np.cumsum(returns))

    # Generate OHLCV data
    data = pd.DataFrame(
        {
            "open": prices * np.random.uniform(0.995, 1.005, n_periods),
            "high": prices * np.random.uniform(1.001, 1.015, n_periods),
            "low": prices * np.random.uniform(0.985, 0.999, n_periods),
            "close": prices,
            "volume": np.random.uniform(800, 1200, n_periods),
        },
        index=dates,
    )

    return data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

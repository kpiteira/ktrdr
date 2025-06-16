"""Tests for multi-timeframe backtesting engine."""

import pytest
import pandas as pd
import numpy as np
import torch
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from ktrdr.evaluation.backtesting_engine import (
    MultiTimeframeBacktestEngine,
    BacktestConfig,
    BacktestResult,
    Trade,
    PositionState,
    TradeDirection,
    OrderType,
    create_default_backtest_config,
    run_quick_backtest
)
from ktrdr.neural.models.multi_timeframe_mlp import MultiTimeframeMLP


class TestBacktestConfig:
    """Test backtest configuration."""
    
    def test_default_config_creation(self):
        """Test default configuration creation."""
        config = create_default_backtest_config()
        
        assert isinstance(config, BacktestConfig)
        assert config.initial_capital > 0
        assert 0.0 <= config.commission_rate <= 0.1
        assert 0.0 <= config.slippage_rate <= 0.1
        assert 0.0 < config.max_position_size <= 1.0
        assert config.min_trade_size > 0
        assert config.execution_delay >= 0
    
    def test_custom_config_creation(self):
        """Test custom configuration creation."""
        config = BacktestConfig(
            initial_capital=50000.0,
            commission_rate=0.002,
            slippage_rate=0.001,
            max_position_size=0.8,
            stop_loss_pct=0.03,
            take_profit_pct=0.06,
            primary_timeframe="4h",
            signal_confidence_threshold=0.7
        )
        
        assert config.initial_capital == 50000.0
        assert config.commission_rate == 0.002
        assert config.slippage_rate == 0.001
        assert config.max_position_size == 0.8
        assert config.stop_loss_pct == 0.03
        assert config.take_profit_pct == 0.06
        assert config.primary_timeframe == "4h"
        assert config.signal_confidence_threshold == 0.7


class TestTradeDirection:
    """Test trade direction enum."""
    
    def test_trade_direction_values(self):
        """Test trade direction enum values."""
        assert TradeDirection.LONG.value == 1
        assert TradeDirection.SHORT.value == -1
        assert TradeDirection.FLAT.value == 0


class TestTrade:
    """Test trade data structure."""
    
    def test_trade_creation(self):
        """Test trade object creation."""
        entry_time = pd.Timestamp('2024-01-01 10:00:00')
        exit_time = pd.Timestamp('2024-01-01 12:00:00')
        
        trade = Trade(
            entry_time=entry_time,
            exit_time=exit_time,
            direction=TradeDirection.LONG,
            entry_price=100.0,
            exit_price=105.0,
            quantity=100.0,
            commission=10.0,
            slippage=5.0,
            pnl=485.0,  # (105-100)*100 - 10 - 5 = 485
            pnl_pct=0.0485,
            exit_reason="take_profit"
        )
        
        assert trade.entry_time == entry_time
        assert trade.exit_time == exit_time
        assert trade.direction == TradeDirection.LONG
        assert trade.entry_price == 100.0
        assert trade.exit_price == 105.0
        assert trade.quantity == 100.0
        assert trade.commission == 10.0
        assert trade.slippage == 5.0
        assert trade.pnl == 485.0
        assert trade.pnl_pct == 0.0485
        assert trade.exit_reason == "take_profit"


class TestPositionState:
    """Test position state management."""
    
    def test_position_state_creation(self):
        """Test position state creation."""
        position = PositionState()
        
        assert position.direction == TradeDirection.FLAT
        assert position.quantity == 0.0
        assert position.entry_price == 0.0
        assert position.entry_time is None
        assert position.unrealized_pnl == 0.0
        assert position.stop_loss_price is None
        assert position.take_profit_price is None
    
    def test_position_state_update(self):
        """Test position state updates."""
        position = PositionState()
        
        # Update position
        position.direction = TradeDirection.LONG
        position.quantity = 100.0
        position.entry_price = 50.0
        position.entry_time = pd.Timestamp('2024-01-01')
        position.unrealized_pnl = 250.0
        
        assert position.direction == TradeDirection.LONG
        assert position.quantity == 100.0
        assert position.entry_price == 50.0
        assert position.unrealized_pnl == 250.0


class TestMultiTimeframeBacktestEngine:
    """Test multi-timeframe backtesting engine."""
    
    @pytest.fixture
    def sample_config(self):
        """Create sample backtest configuration."""
        return BacktestConfig(
            initial_capital=100000.0,
            commission_rate=0.001,
            slippage_rate=0.0005,
            max_position_size=0.95,
            stop_loss_pct=0.02,
            take_profit_pct=0.04,
            primary_timeframe="1h",
            signal_confidence_threshold=0.6
        )
    
    @pytest.fixture
    def backtest_engine(self, sample_config):
        """Create backtest engine instance."""
        return MultiTimeframeBacktestEngine(sample_config)
    
    @pytest.fixture
    def mock_model(self):
        """Create mock multi-timeframe model."""
        model = Mock(spec=MultiTimeframeMLP)
        model.model = Mock()
        model.model.eval.return_value = None
        return model
    
    @pytest.fixture
    def sample_price_data(self):
        """Create sample price data."""
        np.random.seed(42)
        
        dates = pd.date_range('2024-01-01', periods=1000, freq='1h')
        prices = 100 + np.cumsum(np.random.normal(0, 0.5, 1000))
        
        # Ensure OHLC relationships
        opens = prices + np.random.normal(0, 0.1, 1000)
        highs = np.maximum(prices, opens) + np.random.uniform(0, 0.5, 1000)
        lows = np.minimum(prices, opens) - np.random.uniform(0, 0.5, 1000)
        
        return {
            '1h': pd.DataFrame({
                'timestamp': dates,
                'open': opens,
                'high': highs,
                'low': lows,
                'close': prices,
                'volume': np.random.randint(1000, 10000, 1000)
            })
        }
    
    @pytest.fixture
    def sample_features_data(self, sample_price_data):
        """Create sample features data."""
        price_df = sample_price_data['1h']
        
        return {
            '1h': pd.DataFrame({
                'timestamp': price_df['timestamp'],
                'rsi_14': np.random.uniform(20, 80, len(price_df)),
                'sma_20': price_df['close'] + np.random.normal(0, 1, len(price_df)),
                'trend_strength': np.random.uniform(0, 1, len(price_df)),
                'momentum': np.random.uniform(-1, 1, len(price_df))
            })
        }
    
    def test_engine_initialization(self, backtest_engine, sample_config):
        """Test backtest engine initialization."""
        assert backtest_engine.config == sample_config
        assert backtest_engine.position.direction == TradeDirection.FLAT
        assert backtest_engine.current_equity == sample_config.initial_capital
        assert backtest_engine.peak_equity == sample_config.initial_capital
        assert len(backtest_engine.trades) == 0
        assert len(backtest_engine.equity_curve) == 0
    
    def test_reset_state(self, backtest_engine):
        """Test state reset."""
        # Modify state
        backtest_engine.current_equity = 50000.0
        backtest_engine.trades.append(Mock())
        backtest_engine.equity_curve.append({'equity': 50000.0})
        
        # Reset
        backtest_engine.reset_state()
        
        assert backtest_engine.current_equity == backtest_engine.config.initial_capital
        assert len(backtest_engine.trades) == 0
        assert len(backtest_engine.equity_curve) == 0
        assert backtest_engine.position.direction == TradeDirection.FLAT
    
    def test_prepare_backtest_data(self, backtest_engine, sample_price_data, sample_features_data):
        """Test backtest data preparation."""
        aligned_data = backtest_engine._prepare_backtest_data(
            sample_price_data, sample_features_data, None, None
        )
        
        # Verify data structure
        assert isinstance(aligned_data, pd.DataFrame)
        assert not aligned_data.empty
        assert 'timestamp' in aligned_data.columns
        assert 'close' in aligned_data.columns
        assert 'rsi_14' in aligned_data.columns
        assert 'sma_20' in aligned_data.columns
        
        # Verify data alignment
        assert len(aligned_data) <= len(sample_price_data['1h'])
    
    def test_prepare_backtest_data_with_date_filter(self, backtest_engine, sample_price_data, sample_features_data):
        """Test data preparation with date filtering."""
        start_date = pd.Timestamp('2024-01-15')
        end_date = pd.Timestamp('2024-01-20')
        
        aligned_data = backtest_engine._prepare_backtest_data(
            sample_price_data, sample_features_data, start_date, end_date
        )
        
        # Verify date filtering
        assert aligned_data['timestamp'].min() >= start_date
        assert aligned_data['timestamp'].max() <= end_date
        assert len(aligned_data) < len(sample_price_data['1h'])
    
    def test_generate_signal(self, backtest_engine, mock_model, sample_price_data, sample_features_data):
        """Test trading signal generation."""
        # Prepare data
        data = backtest_engine._prepare_backtest_data(
            sample_price_data, sample_features_data, None, None
        )
        
        feature_cols = ['rsi_14', 'sma_20', 'trend_strength', 'momentum']
        
        # Mock model prediction
        with patch.object(mock_model.model, '__call__') as mock_call:
            with patch('torch.no_grad'):
                # Mock high confidence BUY signal
                mock_outputs = torch.tensor([[2.0, 0.5, 0.3]])  # Strong BUY
                mock_probabilities = torch.tensor([[0.8, 0.15, 0.05]])
                mock_call.return_value = mock_outputs
                
                with patch('torch.softmax', return_value=mock_probabilities):
                    with patch('torch.argmax', return_value=torch.tensor([0])):
                        with patch('torch.max', return_value=torch.tensor(0.8)):
                            
                            signal = backtest_engine._generate_signal(
                                mock_model, data, 10, feature_cols
                            )
        
        assert signal == TradeDirection.LONG
    
    def test_generate_signal_low_confidence(self, backtest_engine, mock_model, sample_price_data, sample_features_data):
        """Test signal generation with low confidence."""
        data = backtest_engine._prepare_backtest_data(
            sample_price_data, sample_features_data, None, None
        )
        
        feature_cols = ['rsi_14', 'sma_20', 'trend_strength', 'momentum']
        
        # Mock low confidence prediction
        with patch.object(mock_model.model, '__call__') as mock_call:
            with patch('torch.no_grad'):
                mock_outputs = torch.tensor([[0.6, 0.55, 0.5]])  # Low confidence
                mock_probabilities = torch.tensor([[0.4, 0.35, 0.25]])  # Below threshold
                mock_call.return_value = mock_outputs
                
                with patch('torch.softmax', return_value=mock_probabilities):
                    with patch('torch.argmax', return_value=torch.tensor([0])):
                        with patch('torch.max', return_value=torch.tensor(0.4)):  # Below 0.6 threshold
                            
                            signal = backtest_engine._generate_signal(
                                mock_model, data, 10, feature_cols
                            )
        
        assert signal == TradeDirection.FLAT  # Should reject low confidence
    
    def test_open_position(self, backtest_engine, sample_price_data):
        """Test opening a trading position."""
        data = sample_price_data['1h'].iloc[0]
        
        # Test opening long position
        backtest_engine._open_position(TradeDirection.LONG, data)
        
        # Verify position state
        assert backtest_engine.position.direction == TradeDirection.LONG
        assert backtest_engine.position.quantity > 0
        assert backtest_engine.position.entry_price > 0
        assert backtest_engine.position.entry_time is not None
        
        # Verify stop loss and take profit are set
        if backtest_engine.config.stop_loss_pct:
            assert backtest_engine.position.stop_loss_price is not None
            assert backtest_engine.position.stop_loss_price < backtest_engine.position.entry_price
        
        if backtest_engine.config.take_profit_pct:
            assert backtest_engine.position.take_profit_price is not None
            assert backtest_engine.position.take_profit_price > backtest_engine.position.entry_price
        
        # Verify costs deducted from equity
        assert backtest_engine.current_equity < backtest_engine.config.initial_capital
    
    def test_open_position_insufficient_capital(self, backtest_engine, sample_price_data):
        """Test position opening with insufficient capital."""
        # Reduce available capital
        backtest_engine.current_equity = 100.0  # Very low
        
        data = sample_price_data['1h'].iloc[0]
        
        # Try to open position
        backtest_engine._open_position(TradeDirection.LONG, data)
        
        # Should remain flat due to insufficient capital
        assert backtest_engine.position.direction == TradeDirection.FLAT
    
    def test_close_position_profit(self, backtest_engine, sample_price_data):
        """Test closing position with profit."""
        # Open position first
        entry_data = sample_price_data['1h'].iloc[0]
        backtest_engine._open_position(TradeDirection.LONG, entry_data)
        
        initial_equity = backtest_engine.current_equity
        entry_price = backtest_engine.position.entry_price
        quantity = backtest_engine.position.quantity
        
        # Close position at higher price
        exit_price = entry_price * 1.05  # 5% profit
        exit_time = pd.Timestamp('2024-01-01 11:00:00')
        
        backtest_engine._close_position(exit_price, exit_time, "take_profit")
        
        # Verify position closed
        assert backtest_engine.position.direction == TradeDirection.FLAT
        assert backtest_engine.position.quantity == 0.0
        
        # Verify trade recorded
        assert len(backtest_engine.trades) == 1
        trade = backtest_engine.trades[0]
        assert trade.direction == TradeDirection.LONG
        assert trade.exit_reason == "take_profit"
        assert trade.pnl > 0  # Should be profitable
        
        # Verify equity increased
        assert backtest_engine.current_equity > initial_equity
    
    def test_close_position_loss(self, backtest_engine, sample_price_data):
        """Test closing position with loss."""
        # Open position
        entry_data = sample_price_data['1h'].iloc[0]
        backtest_engine._open_position(TradeDirection.LONG, entry_data)
        
        initial_equity = backtest_engine.current_equity
        entry_price = backtest_engine.position.entry_price
        
        # Close at lower price
        exit_price = entry_price * 0.95  # 5% loss
        exit_time = pd.Timestamp('2024-01-01 11:00:00')
        
        backtest_engine._close_position(exit_price, exit_time, "stop_loss")
        
        # Verify loss recorded
        trade = backtest_engine.trades[0]
        assert trade.pnl < 0  # Should be a loss
        assert trade.exit_reason == "stop_loss"
        
        # Verify equity decreased
        assert backtest_engine.current_equity < initial_equity
    
    def test_check_exit_conditions_stop_loss(self, backtest_engine, sample_price_data):
        """Test stop loss exit condition."""
        # Open long position
        entry_data = sample_price_data['1h'].iloc[0]
        backtest_engine._open_position(TradeDirection.LONG, entry_data)
        
        # Create data with low price to trigger stop loss
        current_data = entry_data.copy()
        stop_loss_price = backtest_engine.position.stop_loss_price
        current_data['low'] = stop_loss_price - 0.01  # Below stop loss
        current_data['high'] = entry_data['close']
        current_data['close'] = stop_loss_price - 0.005
        
        # Check exit conditions
        should_exit = backtest_engine._check_exit_conditions(current_data)
        
        assert should_exit
        assert backtest_engine.position.direction == TradeDirection.FLAT
        assert len(backtest_engine.trades) == 1
        assert backtest_engine.trades[0].exit_reason == "stop_loss"
    
    def test_check_exit_conditions_take_profit(self, backtest_engine, sample_price_data):
        """Test take profit exit condition."""
        # Open long position
        entry_data = sample_price_data['1h'].iloc[0]
        backtest_engine._open_position(TradeDirection.LONG, entry_data)
        
        # Create data with high price to trigger take profit
        current_data = entry_data.copy()
        take_profit_price = backtest_engine.position.take_profit_price
        current_data['high'] = take_profit_price + 0.01  # Above take profit
        current_data['low'] = entry_data['close']
        current_data['close'] = take_profit_price + 0.005
        
        # Check exit conditions
        should_exit = backtest_engine._check_exit_conditions(current_data)
        
        assert should_exit
        assert backtest_engine.position.direction == TradeDirection.FLAT
        assert len(backtest_engine.trades) == 1
        assert backtest_engine.trades[0].exit_reason == "take_profit"
    
    def test_position_sizing_fixed(self, backtest_engine):
        """Test fixed position sizing."""
        price = 100.0
        direction = TradeDirection.LONG
        
        position_size = backtest_engine._calculate_position_size(price, direction)
        
        expected_size = (backtest_engine.config.initial_capital * 
                        backtest_engine.config.max_position_size) / price
        
        assert abs(position_size - expected_size) < 0.01
    
    def test_position_sizing_volatility(self, backtest_engine):
        """Test volatility-based position sizing."""
        backtest_engine.config.position_sizing_method = "volatility"
        
        price = 100.0
        direction = TradeDirection.LONG
        
        position_size = backtest_engine._calculate_position_size(price, direction)
        
        # Should be smaller than fixed due to volatility adjustment
        fixed_size = (backtest_engine.config.initial_capital * 
                     backtest_engine.config.max_position_size) / price
        
        assert position_size < fixed_size
        assert position_size > 0
    
    def test_risk_limits_consecutive_losses(self, backtest_engine):
        """Test consecutive losses risk limit."""
        backtest_engine.position.consecutive_losses = backtest_engine.config.max_consecutive_losses
        
        can_trade = backtest_engine._check_risk_limits()
        assert not can_trade
        
        # Reset consecutive losses
        backtest_engine.position.consecutive_losses = 0
        can_trade = backtest_engine._check_risk_limits()
        assert can_trade
    
    def test_risk_limits_daily_loss(self, backtest_engine):
        """Test daily loss limit."""
        # Set high daily loss
        backtest_engine.daily_pnl = -backtest_engine.current_equity * 0.1  # 10% loss
        
        can_trade = backtest_engine._check_risk_limits()
        assert not can_trade
        
        # Reset daily P&L
        backtest_engine.daily_pnl = 0.0
        can_trade = backtest_engine._check_risk_limits()
        assert can_trade
    
    def test_update_position_state(self, backtest_engine, sample_price_data):
        """Test position state updates."""
        # Open position
        entry_data = sample_price_data['1h'].iloc[0]
        backtest_engine._open_position(TradeDirection.LONG, entry_data)
        
        # Update with new price
        current_data = entry_data.copy()
        current_data['close'] = backtest_engine.position.entry_price * 1.03  # 3% gain
        
        backtest_engine._update_position_state(current_data)
        
        # Verify unrealized P&L updated
        assert backtest_engine.position.unrealized_pnl > 0
        
        expected_pnl = (current_data['close'] - backtest_engine.position.entry_price) * backtest_engine.position.quantity
        assert abs(backtest_engine.position.unrealized_pnl - expected_pnl) < 0.01
    
    def test_record_equity_point(self, backtest_engine, sample_price_data):
        """Test equity point recording."""
        data = sample_price_data['1h'].iloc[0]
        
        backtest_engine._record_equity_point(data)
        
        # Verify equity point recorded
        assert len(backtest_engine.equity_curve) == 1
        
        equity_point = backtest_engine.equity_curve[0]
        assert 'timestamp' in equity_point
        assert 'equity' in equity_point
        assert 'cash' in equity_point
        assert 'unrealized_pnl' in equity_point
        assert 'position_value' in equity_point
        assert 'drawdown' in equity_point
        
        # Verify values
        assert equity_point['equity'] == backtest_engine.config.initial_capital
        assert equity_point['cash'] == backtest_engine.current_equity
        assert equity_point['unrealized_pnl'] == 0.0
        assert equity_point['drawdown'] == 0.0
    
    @patch('torch.no_grad')
    def test_simulate_trading_complete(self, mock_no_grad, backtest_engine, mock_model, sample_price_data, sample_features_data):
        """Test complete trading simulation."""
        # Prepare data
        data = backtest_engine._prepare_backtest_data(
            sample_price_data, sample_features_data, None, None
        )
        
        # Mock model to generate some trading signals
        signal_sequence = [TradeDirection.FLAT] * 10 + [TradeDirection.LONG] + [TradeDirection.FLAT] * 10
        
        with patch.object(backtest_engine, '_generate_signal', side_effect=signal_sequence):
            backtest_engine._simulate_trading(mock_model, data.head(21))  # Use first 21 rows
        
        # Verify simulation ran
        assert len(backtest_engine.equity_curve) > 0
        
        # Should have at least attempted to open position
        # (may or may not have completed trade depending on exit conditions)
    
    def test_calculate_backtest_results_basic(self, backtest_engine, sample_price_data):
        """Test basic backtest results calculation."""
        # Simulate some equity curve data
        dates = pd.date_range('2024-01-01', periods=100, freq='1h')
        equity_values = np.linspace(100000, 110000, 100)  # 10% gain
        
        for i, (date, equity) in enumerate(zip(dates, equity_values)):
            backtest_engine.equity_curve.append({
                'timestamp': date,
                'equity': equity,
                'cash': equity,
                'unrealized_pnl': 0.0,
                'position_value': 0.0,
                'drawdown': 0.0
            })
        
        # Add some sample trades
        backtest_engine.trades = [
            Trade(
                entry_time=dates[10],
                exit_time=dates[20],
                direction=TradeDirection.LONG,
                entry_price=100.0,
                exit_price=105.0,
                quantity=100.0,
                commission=10.0,
                slippage=5.0,
                pnl=485.0,
                pnl_pct=0.0485,
                exit_reason="take_profit"
            ),
            Trade(
                entry_time=dates[30],
                exit_time=dates[40],
                direction=TradeDirection.LONG,
                entry_price=105.0,
                exit_price=103.0,
                quantity=100.0,
                commission=10.0,
                slippage=5.0,
                pnl=-215.0,
                pnl_pct=-0.0215,
                exit_reason="stop_loss"
            )
        ]
        
        # Calculate results
        data = pd.DataFrame({
            'timestamp': dates,
            'close': np.random.randn(100) + 100
        })
        
        result = backtest_engine._calculate_backtest_results(data)
        
        # Verify result structure
        assert isinstance(result, BacktestResult)
        assert result.total_return > 0  # Should show profit
        assert result.total_trades == 2
        assert result.winning_trades == 1
        assert result.losing_trades == 1
        assert result.win_rate == 0.5
        assert result.avg_win > 0
        assert result.avg_loss < 0
        assert result.profit_factor > 0
    
    def test_calculate_backtest_results_with_drawdown(self, backtest_engine):
        """Test backtest results with drawdown."""
        # Create equity curve with drawdown
        dates = pd.date_range('2024-01-01', periods=100, freq='1h')
        equity_values = [100000] * 20 + list(np.linspace(100000, 90000, 30)) + list(np.linspace(90000, 105000, 50))
        
        for date, equity in zip(dates, equity_values):
            backtest_engine.equity_curve.append({
                'timestamp': date,
                'equity': equity,
                'cash': equity,
                'unrealized_pnl': 0.0,
                'position_value': 0.0,
                'drawdown': 0.0
            })
        
        data = pd.DataFrame({
            'timestamp': dates,
            'close': np.random.randn(100) + 100
        })
        
        result = backtest_engine._calculate_backtest_results(data)
        
        # Verify drawdown metrics
        assert result.max_drawdown > 0  # Should detect drawdown
        assert result.max_drawdown_duration > 0
        assert len(result.drawdown_periods) > 0
    
    @patch('torch.no_grad')
    def test_run_backtest_complete(self, mock_no_grad, backtest_engine, mock_model, sample_price_data, sample_features_data):
        """Test complete backtest run."""
        # Mock model predictions to generate some trades
        mock_outputs = torch.tensor([[2.0, 0.5, 0.3]])
        mock_probabilities = torch.tensor([[0.7, 0.2, 0.1]])
        
        with patch.object(mock_model.model, '__call__', return_value=mock_outputs):
            with patch('torch.softmax', return_value=mock_probabilities):
                with patch('torch.argmax', return_value=torch.tensor([0])):
                    with patch('torch.max', return_value=torch.tensor(0.7)):
                        
                        result = backtest_engine.run_backtest(
                            mock_model,
                            sample_price_data,
                            sample_features_data,
                            start_date=pd.Timestamp('2024-01-01'),
                            end_date=pd.Timestamp('2024-01-10')
                        )
        
        # Verify result
        assert isinstance(result, BacktestResult)
        assert result.start_date <= result.end_date
        assert result.total_days > 0
        assert isinstance(result.equity_curve, pd.DataFrame)
        assert not result.equity_curve.empty
        
        # Verify metrics are calculated
        assert isinstance(result.total_return, float)
        assert isinstance(result.annual_return, float)
        assert isinstance(result.sharpe_ratio, float)
        assert isinstance(result.max_drawdown, float)
        assert isinstance(result.total_trades, int)


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_run_quick_backtest(self):
        """Test quick backtest utility function."""
        # Create mock components
        mock_model = Mock(spec=MultiTimeframeMLP)
        mock_model.model = Mock()
        mock_model.model.eval.return_value = None
        
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=100, freq='1h')
        prices = 100 + np.cumsum(np.random.normal(0, 0.5, 100))
        
        price_data = {
            '1h': pd.DataFrame({
                'timestamp': dates,
                'open': prices,
                'high': prices + 0.5,
                'low': prices - 0.5,
                'close': prices,
                'volume': np.random.randint(1000, 10000, 100)
            })
        }
        
        features_data = {
            '1h': pd.DataFrame({
                'timestamp': dates,
                'rsi_14': np.random.uniform(20, 80, 100),
                'trend': np.random.uniform(0, 1, 100)
            })
        }
        
        # Mock the backtest execution
        with patch('ktrdr.evaluation.backtesting_engine.MultiTimeframeBacktestEngine.run_backtest') as mock_backtest:
            mock_result = Mock(spec=BacktestResult)
            mock_backtest.return_value = mock_result
            
            result = run_quick_backtest(mock_model, price_data, features_data)
            
            assert mock_backtest.called
            assert result == mock_result
    
    def test_run_quick_backtest_with_custom_config(self):
        """Test quick backtest with custom configuration."""
        mock_model = Mock()
        price_data = {'1h': pd.DataFrame()}
        features_data = {'1h': pd.DataFrame()}
        
        custom_config = BacktestConfig(
            initial_capital=50000.0,
            commission_rate=0.002
        )
        
        with patch('ktrdr.evaluation.backtesting_engine.MultiTimeframeBacktestEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_result = Mock()
            mock_engine.run_backtest.return_value = mock_result
            mock_engine_class.return_value = mock_engine
            
            result = run_quick_backtest(mock_model, price_data, features_data, custom_config)
            
            # Verify custom config was used
            mock_engine_class.assert_called_once_with(custom_config)
            assert result == mock_result


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_data_handling(self):
        """Test handling of empty data."""
        config = create_default_backtest_config()
        engine = MultiTimeframeBacktestEngine(config)
        
        empty_price_data = {'1h': pd.DataFrame()}
        empty_features_data = {'1h': pd.DataFrame()}
        
        # Should handle empty data gracefully
        aligned_data = engine._prepare_backtest_data(
            empty_price_data, empty_features_data, None, None
        )
        
        assert aligned_data.empty
    
    def test_missing_primary_timeframe(self):
        """Test handling of missing primary timeframe."""
        config = BacktestConfig(primary_timeframe="4h")
        engine = MultiTimeframeBacktestEngine(config)
        
        # Data only has 1h, not 4h
        price_data = {
            '1h': pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=10, freq='1h'),
                'close': range(10)
            })
        }
        
        with pytest.raises(ValueError, match="Primary timeframe .* not found"):
            engine._prepare_backtest_data(price_data, {}, None, None)
    
    def test_insufficient_data_for_execution_delay(self):
        """Test handling insufficient data for execution delay."""
        config = BacktestConfig(execution_delay=10)
        engine = MultiTimeframeBacktestEngine(config)
        
        mock_model = Mock()
        
        # Create very small dataset
        data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='1h'),
            'close': range(5),
            'rsi_14': range(5)
        })
        
        # Signal generation should return FLAT for early indices
        signal = engine._generate_signal(mock_model, data, 5, ['rsi_14'])
        assert signal == TradeDirection.FLAT
    
    def test_no_features_available(self, backtest_engine, mock_model, sample_price_data):
        """Test handling when no features are available."""
        # Data without feature columns
        data = sample_price_data['1h'][['timestamp', 'close']].copy()
        
        feature_cols = []  # No features
        
        signal = backtest_engine._generate_signal(mock_model, data, 10, feature_cols)
        assert signal == TradeDirection.FLAT
    
    def test_extreme_market_conditions(self, backtest_engine, sample_price_data):
        """Test handling of extreme market conditions."""
        # Create data with extreme price movements
        extreme_data = sample_price_data['1h'].copy()
        extreme_data.loc[10:20, 'close'] *= 2.0  # 100% price spike
        extreme_data.loc[30:40, 'close'] *= 0.1  # 90% price crash
        
        # Should not crash during position sizing calculations
        price = extreme_data.loc[15, 'close']  # Extreme high price
        size = backtest_engine._calculate_position_size(price, TradeDirection.LONG)
        
        assert size > 0
        assert size * price <= backtest_engine.current_equity  # Should not exceed available capital


if __name__ == "__main__":
    pytest.main([__file__])
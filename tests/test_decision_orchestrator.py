"""Tests for Decision Orchestrator (Phase 3)."""

import pytest
import pandas as pd
import numpy as np
import torch
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from ktrdr.decision import (
    DecisionOrchestrator, 
    DecisionContext, 
    PositionState,
    Signal, 
    Position,
    TradingDecision
)
from ktrdr.training import ModelStorage
from ktrdr.neural.models.mlp import MLPTradingModel


class TestPositionState:
    """Test position state tracking."""
    
    def test_position_state_initialization(self):
        """Test position state initialization."""
        state = PositionState("AAPL")
        
        assert state.symbol == "AAPL"
        assert state.position == Position.FLAT
        assert state.entry_price is None
        assert state.entry_time is None
        assert state.unrealized_pnl == 0.0
        assert state.holding_period is None
    
    def test_position_state_buy_signal(self):
        """Test position state update with buy signal."""
        state = PositionState("AAPL")
        
        # Create decision and current bar
        decision = TradingDecision(
            signal=Signal.BUY,
            confidence=0.8,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            reasoning={},
            current_position=Position.FLAT
        )
        
        current_bar = pd.Series({
            'open': 100.0,
            'high': 102.0,
            'low': 99.0,
            'close': 101.0,
            'volume': 1000
        }, name=pd.Timestamp("2024-01-01 10:00:00"))
        
        state.update_from_decision(decision, current_bar)
        
        assert state.position == Position.LONG
        assert state.entry_price == 101.0
        assert state.entry_time == pd.Timestamp("2024-01-01 10:00:00")
    
    def test_position_state_sell_signal(self):
        """Test position state update with sell signal."""
        state = PositionState("AAPL")
        
        # First, establish a long position
        buy_decision = TradingDecision(
            signal=Signal.BUY,
            confidence=0.8,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            reasoning={},
            current_position=Position.FLAT
        )
        
        buy_bar = pd.Series({
            'close': 100.0
        }, name=pd.Timestamp("2024-01-01 10:00:00"))
        
        state.update_from_decision(buy_decision, buy_bar)
        
        # Now sell
        sell_decision = TradingDecision(
            signal=Signal.SELL,
            confidence=0.8,
            timestamp=pd.Timestamp("2024-01-01 11:00:00"),
            reasoning={},
            current_position=Position.LONG
        )
        
        sell_bar = pd.Series({
            'close': 105.0
        }, name=pd.Timestamp("2024-01-01 11:00:00"))
        
        state.update_from_decision(sell_decision, sell_bar)
        
        assert state.position == Position.FLAT
        assert state.entry_price is None
        assert state.entry_time is None
        assert state.unrealized_pnl == 0.0


class TestDecisionOrchestrator:
    """Test decision orchestrator functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.models_dir = Path(self.temp_dir) / "models"
        self.strategies_dir = Path(self.temp_dir) / "strategies"
        self.strategies_dir.mkdir(parents=True)
        
        # Create test strategy config
        self.strategy_config = {
            'name': 'test_strategy',
            'indicators': [
                {'name': 'rsi', 'period': 14, 'source': 'close'},
                {'name': 'sma', 'period': 20, 'source': 'close'}
            ],
            'fuzzy_sets': {
                'rsi': {
                    'oversold': [0, 10, 30],
                    'neutral': [25, 50, 75],
                    'overbought': [70, 90, 100]
                }
            },
            'model': {
                'type': 'mlp',
                'architecture': {
                    'hidden_layers': [10, 5],
                    'activation': 'relu',
                    'dropout': 0.2
                }
            },
            'decisions': {
                'confidence_threshold': 0.6,
                'position_awareness': True
            },
            'orchestrator': {
                'max_position_size': 0.9,
                'modes': {
                    'backtest': {'confidence_threshold': 0.6},
                    'live': {'confidence_threshold': 0.8}
                }
            }
        }
        
        self.strategy_path = self.strategies_dir / "test_strategy.yaml"
        import yaml
        with open(self.strategy_path, 'w') as f:
            yaml.dump(self.strategy_config, f)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization without model."""
        orchestrator = DecisionOrchestrator(
            strategy_config_path=str(self.strategy_path),
            mode="backtest"
        )
        
        assert orchestrator.strategy_name == "test_strategy"
        assert orchestrator.mode == "backtest"
        assert orchestrator.model is None
        assert len(orchestrator.position_states) == 0
        assert len(orchestrator.decision_history) == 0
    
    def test_orchestrator_with_mock_model(self):
        """Test orchestrator configuration for model loading (without actual loading)."""
        # For now, just test that the orchestrator can be initialized with a model path
        # without actually loading it (since that requires complex setup)
        
        orchestrator = DecisionOrchestrator(
            strategy_config_path=str(self.strategy_path),
            mode="backtest"
        )
        
        # Test that the model loader is initialized
        assert orchestrator.model_loader is not None
        assert orchestrator.model is None  # No model loaded yet
        
        # Test that the orchestrator can handle model path parsing
        # (We'll test actual model loading in integration tests)
        test_path = "/models/test_strategy/AAPL_1h_v1"
        try:
            # This will fail because the path doesn't exist, but we can test the parsing
            orchestrator._load_model_from_path(test_path)
        except FileNotFoundError:
            pass  # Expected since we don't have a real model
        except Exception as e:
            if "Invalid model path format" in str(e):
                assert False, f"Model path parsing failed: {e}"
            # Other exceptions (like file not found) are expected
    
    def test_context_preparation(self):
        """Test decision context preparation."""
        orchestrator = DecisionOrchestrator(
            strategy_config_path=str(self.strategy_path),
            mode="backtest"
        )
        
        # Create sample data
        dates = pd.date_range("2024-01-01", periods=50, freq="1h")
        historical_data = pd.DataFrame({
            'open': np.random.uniform(95, 105, 50),
            'high': np.random.uniform(100, 110, 50),
            'low': np.random.uniform(90, 100, 50),
            'close': np.random.uniform(95, 105, 50),
            'volume': np.random.uniform(800, 1200, 50)
        }, index=dates)
        
        current_bar = historical_data.iloc[-1]
        
        indicators = {'rsi': 45.0, 'sma_20': 100.0}
        fuzzy_memberships = {'rsi_neutral_membership': 0.8}
        portfolio_state = {'total_value': 100000, 'available_capital': 50000}
        
        context = orchestrator._prepare_context(
            symbol="AAPL",
            current_bar=current_bar,
            historical_data=historical_data,
            indicators=indicators,
            fuzzy_memberships=fuzzy_memberships,
            portfolio_state=portfolio_state
        )
        
        assert isinstance(context, DecisionContext)
        assert context.current_position == Position.FLAT
        assert context.portfolio_value == 100000
        assert context.available_capital == 50000
        assert len(context.recent_bars) <= 20
    
    def test_orchestrator_logic_position_limit(self):
        """Test orchestrator logic for position size limits."""
        orchestrator = DecisionOrchestrator(
            strategy_config_path=str(self.strategy_path),
            mode="backtest"
        )
        
        # Create a buy decision
        decision = TradingDecision(
            signal=Signal.BUY,
            confidence=0.8,
            timestamp=pd.Timestamp.now(),
            reasoning={},
            current_position=Position.FLAT
        )
        
        # Create context with high position exposure
        context = DecisionContext(
            current_bar=pd.Series({'close': 100}),
            recent_bars=pd.DataFrame(),
            indicators={},
            fuzzy_memberships={},
            current_position=Position.FLAT,
            position_entry_price=None,
            position_holding_period=None,
            unrealized_pnl=None,
            portfolio_value=100000,
            available_capital=5000,  # Only 5% available (95% invested)
            recent_decisions=[],
            last_signal_time=None
        )
        
        final_decision = orchestrator._apply_orchestrator_logic(decision, context)
        
        # Should be overridden due to position limit
        assert final_decision.signal == Signal.HOLD
        assert 'orchestrator_override' in final_decision.reasoning
    
    def test_mode_specific_logic(self):
        """Test mode-specific decision logic."""
        # Test live mode with higher confidence requirement
        orchestrator = DecisionOrchestrator(
            strategy_config_path=str(self.strategy_path),
            mode="live"
        )
        
        decision = TradingDecision(
            signal=Signal.BUY,
            confidence=0.7,  # Below live threshold of 0.8
            timestamp=pd.Timestamp.now(),
            reasoning={},
            current_position=Position.FLAT
        )
        
        context = DecisionContext(
            current_bar=pd.Series({'close': 100}),
            recent_bars=pd.DataFrame(),
            indicators={},
            fuzzy_memberships={},
            current_position=Position.FLAT,
            position_entry_price=None,
            position_holding_period=None,
            unrealized_pnl=None,
            portfolio_value=100000,
            available_capital=50000,
            recent_decisions=[],
            last_signal_time=None
        )
        
        final_decision = orchestrator._apply_orchestrator_logic(decision, context)
        
        # Should be overridden due to live mode confidence requirement
        assert final_decision.signal == Signal.HOLD
        assert 'orchestrator_override' in final_decision.reasoning
    
    def test_state_updates(self):
        """Test state updates after decisions."""
        orchestrator = DecisionOrchestrator(
            strategy_config_path=str(self.strategy_path),
            mode="backtest"
        )
        
        decision = TradingDecision(
            signal=Signal.BUY,
            confidence=0.8,
            timestamp=pd.Timestamp.now(),
            reasoning={},
            current_position=Position.FLAT
        )
        
        context = DecisionContext(
            current_bar=pd.Series({'close': 100}, name=pd.Timestamp.now()),
            recent_bars=pd.DataFrame(),
            indicators={},
            fuzzy_memberships={},
            current_position=Position.FLAT,
            position_entry_price=None,
            position_holding_period=None,
            unrealized_pnl=None,
            portfolio_value=100000,
            available_capital=50000,
            recent_decisions=[],
            last_signal_time=None
        )
        
        orchestrator._update_state("AAPL", decision, context)
        
        # Check that position state was created and updated
        assert "AAPL" in orchestrator.position_states
        position_state = orchestrator.position_states["AAPL"]
        assert position_state.position == Position.LONG
        
        # Check that decision was added to history
        assert len(orchestrator.decision_history) == 1
        assert orchestrator.decision_history[0].signal == Signal.BUY
        assert orchestrator.decision_history[0].reasoning['symbol'] == "AAPL"
    
    def test_decision_history(self):
        """Test decision history tracking."""
        orchestrator = DecisionOrchestrator(
            strategy_config_path=str(self.strategy_path),
            mode="backtest"
        )
        
        # Add some decisions to history
        for i in range(5):
            decision = TradingDecision(
                signal=Signal.HOLD,
                confidence=0.5,
                timestamp=pd.Timestamp.now(),
                reasoning={'symbol': 'AAPL'},
                current_position=Position.FLAT
            )
            orchestrator.decision_history.append(decision)
        
        # Test getting all history
        history = orchestrator.get_decision_history()
        assert len(history) == 5
        
        # Test getting filtered history
        filtered_history = orchestrator.get_decision_history(symbol="AAPL", limit=3)
        assert len(filtered_history) == 3
        
        # Test getting history for non-existent symbol
        empty_history = orchestrator.get_decision_history(symbol="MSFT")
        assert len(empty_history) == 0


def create_sample_price_data(n_periods: int = 100) -> pd.DataFrame:
    """Create sample price data for testing."""
    dates = pd.date_range("2024-01-01", periods=n_periods, freq="1h")
    
    # Generate realistic price data
    returns = np.random.normal(0, 0.01, n_periods)
    prices = 100 * np.exp(np.cumsum(returns))
    
    return pd.DataFrame({
        'open': prices * np.random.uniform(0.995, 1.005, n_periods),
        'high': prices * np.random.uniform(1.001, 1.015, n_periods),
        'low': prices * np.random.uniform(0.985, 0.999, n_periods),
        'close': prices,
        'volume': np.random.uniform(800, 1200, n_periods)
    }, index=dates)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
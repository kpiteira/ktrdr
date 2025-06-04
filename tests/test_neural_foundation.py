"""Tests for Phase 1: Neural Network Foundation."""

import pytest
import torch
import pandas as pd
import numpy as np
from datetime import datetime

from ktrdr.decision import Signal, Position, TradingDecision, DecisionEngine
from ktrdr.neural import MLPTradingModel


class TestBaseTypes:
    """Test base enums and dataclasses."""
    
    def test_signal_enum(self):
        """Test Signal enum values."""
        assert Signal.BUY.value == "BUY"
        assert Signal.SELL.value == "SELL"
        assert Signal.HOLD.value == "HOLD"
    
    def test_position_enum(self):
        """Test Position enum values."""
        assert Position.LONG.value == "LONG"
        assert Position.SHORT.value == "SHORT"
        assert Position.FLAT.value == "FLAT"
    
    def test_trading_decision_creation(self):
        """Test TradingDecision creation and validation."""
        decision = TradingDecision(
            signal=Signal.BUY,
            confidence=0.85,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            reasoning={"test": "data"},
            current_position=Position.FLAT
        )
        
        assert decision.signal == Signal.BUY
        assert decision.confidence == 0.85
        assert isinstance(decision.timestamp, pd.Timestamp)
    
    def test_trading_decision_validation(self):
        """Test TradingDecision validation."""
        # Test invalid confidence
        with pytest.raises(ValueError, match="Confidence must be between"):
            TradingDecision(
                signal=Signal.BUY,
                confidence=1.5,  # Invalid
                timestamp=pd.Timestamp.now(),
                reasoning={},
                current_position=Position.FLAT
            )


class TestMLPModel:
    """Test Multi-Layer Perceptron model."""
    
    def test_model_creation(self):
        """Test MLP model creation with config."""
        config = {
            "architecture": {
                "hidden_layers": [30, 15, 8],
                "activation": "relu",
                "output_activation": "softmax",
                "dropout": 0.2
            }
        }
        
        model = MLPTradingModel(config)
        assert model.config == config
        assert model.model is None  # Not built yet
        assert not model.is_trained
    
    def test_model_building(self):
        """Test building the neural network architecture."""
        config = {
            "architecture": {
                "hidden_layers": [20, 10],
                "activation": "relu",
                "dropout": 0.1
            }
        }
        
        model = MLPTradingModel(config)
        nn_model = model.build_model(input_size=15)
        
        assert nn_model is not None
        assert isinstance(nn_model, torch.nn.Module)
        
        # Test forward pass with dummy data
        dummy_input = torch.randn(1, 15)
        output = nn_model(dummy_input)
        
        assert output.shape == (1, 3)  # 3 classes: BUY, HOLD, SELL
        assert torch.allclose(output.sum(), torch.tensor(1.0), atol=1e-6)  # Softmax sums to 1
    
    def test_feature_preparation(self):
        """Test feature preparation from fuzzy and indicator data."""
        config = {
            "architecture": {"hidden_layers": [10]},
            "features": {
                "include_price_context": True,
                "include_volume_context": True,
                "lookback_periods": 2
            }
        }
        
        model = MLPTradingModel(config)
        
        # Create sample data
        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        
        fuzzy_data = pd.DataFrame({
            "rsi_oversold_membership": [0.8, 0.6, 0.4, 0.2, 0.1],
            "rsi_neutral_membership": [0.2, 0.4, 0.6, 0.8, 0.9],
            "macd_positive_membership": [0.1, 0.3, 0.5, 0.7, 0.9]
        }, index=dates)
        
        indicators = pd.DataFrame({
            "close": [100, 101, 102, 101, 100],
            "sma_20": [99, 100, 101, 101, 101],
            "volume": [1000, 1100, 900, 1200, 1000]
        }, index=dates)
        
        features = model.prepare_features(fuzzy_data, indicators)
        
        assert isinstance(features, torch.Tensor)
        assert features.shape[0] == 5  # 5 time periods
        # Features: 3 fuzzy + price_ratio + roc + volume_ratio + 3 fuzzy lookback = 9
        assert features.shape[1] >= 9


class TestDecisionEngine:
    """Test decision engine functionality."""
    
    def test_engine_initialization(self):
        """Test decision engine initialization."""
        config = {
            "model": {
                "type": "mlp",
                "architecture": {"hidden_layers": [10]}
            },
            "decisions": {
                "confidence_threshold": 0.6,
                "position_awareness": True
            }
        }
        
        engine = DecisionEngine(config)
        
        assert engine.config == config
        assert engine.current_position == Position.FLAT
        assert engine.neural_model is not None
        assert isinstance(engine.neural_model, MLPTradingModel)
    
    def test_position_update(self):
        """Test position tracking updates."""
        config = {
            "model": {"type": "mlp", "architecture": {"hidden_layers": [10]}}
        }
        
        engine = DecisionEngine(config)
        
        # Initial state
        assert engine.current_position == Position.FLAT
        
        # Buy signal
        engine.update_position(Signal.BUY)
        assert engine.current_position == Position.LONG
        
        # Sell signal (close long)
        engine.update_position(Signal.SELL)
        assert engine.current_position == Position.FLAT
    
    def test_filter_logic(self):
        """Test signal filtering logic."""
        config = {
            "model": {"type": "mlp", "architecture": {"hidden_layers": [10]}},
            "decisions": {
                "confidence_threshold": 0.7,
                "position_awareness": True,
                "filters": {
                    "min_signal_separation": 2
                }
            }
        }
        
        engine = DecisionEngine(config)
        
        # Test confidence threshold
        filtered = engine._apply_position_logic(
            Signal.BUY, 
            confidence=0.5,  # Below threshold
            timestamp=pd.Timestamp.now()
        )
        assert filtered == Signal.HOLD
        
        # Test position awareness
        engine.current_position = Position.LONG
        filtered = engine._apply_position_logic(
            Signal.BUY,  # Already long
            confidence=0.8,
            timestamp=pd.Timestamp.now()
        )
        assert filtered == Signal.HOLD


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
# Getting Started Guide for Claude Code - KTRDR Implementation

## Overview
This guide provides step-by-step instructions for implementing the KTRDR neuro-fuzzy trading system using the Architecture Decision Records (ADRs) as blueprints.

## Prerequisites
- Existing KTRDR codebase with working data management, indicators, and fuzzy logic
- Python environment with required packages (torch, pandas, numpy, fastapi, etc.)
- Access to Interactive Brokers data (or sample CSV data for testing)

## Implementation Phases

### 🎯 Phase 1: Neural Network Foundation (2-3 hours)

**Goal**: Create the basic neural network decision-making infrastructure

#### Step 1.1: Create Module Structure
```bash
# Create the decision and neural network modules
mkdir -p ktrdr/decision
mkdir -p ktrdr/neural/models
mkdir -p ktrdr/training
```

#### Step 1.2: Implement Base Classes
**File**: `ktrdr/decision/base.py`
```python
# Copy from ADR-003: Signal, Position, TradingDecision enums and dataclasses
# These are the fundamental types used throughout the system
```

#### Step 1.3: Implement Neural Network Model
**File**: `ktrdr/neural/models/mlp.py`
```python
# Copy from ADR-003: MLPTradingModel class
# Start with basic implementation, test with dummy data
```

#### Step 1.4: Basic Decision Engine
**File**: `ktrdr/decision/engine.py`
```python
# Copy from ADR-003: DecisionEngine class
# This generates trading signals from neural network outputs
```

**Validation**: Create a unit test that initializes the model and makes a dummy decision

---

### 🚂 Phase 2: Training System (4-5 hours)

**Goal**: Build the system to train neural networks on historical data

#### Step 2.1: Implement ZigZag Labeler
**File**: `ktrdr/training/zigzag_labeler.py`
```python
# Copy from ADR-003/004: ZigZagLabeler class
# This creates "perfect" hindsight labels for supervised learning
```

**Quick Test**:
```python
# Test with sample price data
labeler = ZigZagLabeler(threshold=0.05)
labels = labeler.generate_labels(sample_price_data)
print(f"Label distribution: {labels.value_counts()}")
```

#### Step 2.2: Feature Engineering
**File**: `ktrdr/training/feature_engineering.py`
```python
# Copy from ADR-004: FeatureEngineer class
# Converts fuzzy values + indicators into neural network features
```

#### Step 2.3: Model Trainer
**File**: `ktrdr/training/model_trainer.py`
```python
# Copy from ADR-004: ModelTrainer class
# Handles the PyTorch training loop with early stopping
```

#### Step 2.4: Model Storage
**File**: `ktrdr/training/model_storage.py`
```python
# Copy from ADR-004: ModelStorage class
# Saves models with versioning: models/strategy_name/AAPL_1h_v1/
```

#### Step 2.5: Training Orchestrator
**File**: `ktrdr/training/train_strategy.py`
```python
# Copy from ADR-004: StrategyTrainer class
# Coordinates the complete training pipeline
```

#### Step 2.6: Training CLI
**File**: `ktrdr/training/cli.py`
```python
# Copy from ADR-004: CLI implementation
# Provides command-line interface for training
```

#### Step 2.7: Create Sample Strategy Config
**File**: `strategies/neuro_mean_reversion.yaml`
```yaml
# Copy the example configuration from ADR-003
# Start with simple RSI + MACD strategy
```

#### Step 2.8: Train Your First Model
```bash
# Run training on sample data
python -m ktrdr.training.cli \
    --strategy strategies/neuro_mean_reversion.yaml \
    --symbol AAPL \
    --timeframe 1h \
    --start-date 2023-01-01 \
    --end-date 2023-12-31

# Check that model was saved
ls models/neuro_mean_reversion/
# Should see: AAPL_1h_v1/
```

---

### 🎭 Phase 3: Decision Orchestration (2-3 hours)

**Goal**: Create the central coordinator that ties everything together

#### Step 3.1: Model Loader
**File**: `ktrdr/backtesting/model_loader.py`
```python
# Copy from ADR-005: ModelLoader class
# Note: Even though it's in backtesting module, it's used by orchestrator too
```

#### Step 3.2: Decision Orchestrator
**File**: `ktrdr/decision/orchestrator.py`
```python
# Copy from ADR-002: DecisionOrchestrator and PositionState classes
# This is the main coordinator for all trading decisions
```

#### Step 3.3: Integration Test
**File**: `tests/test_orchestrator_integration.py`
```python
def test_orchestrator_makes_decision():
    # Load sample data
    data = pd.read_csv("data/AAPL_1h_sample.csv", index_col=0, parse_dates=True)
    
    # Initialize orchestrator
    orchestrator = DecisionOrchestrator(
        strategy_config_path="strategies/neuro_mean_reversion.yaml",
        model_path="models/neuro_mean_reversion/AAPL_1h_v1/",
        mode="backtest"
    )
    
    # Make a decision
    decision = orchestrator.make_decision(
        symbol="AAPL",
        timeframe="1h",
        current_bar=data.iloc[-1],
        historical_data=data,
        portfolio_state={
            "total_value": 100000,
            "available_capital": 100000
        }
    )
    
    # Verify decision
    assert decision.signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
    assert 0 <= decision.confidence <= 1
    print(f"Decision: {decision.signal} (confidence: {decision.confidence})")
```

---

### 📊 Phase 4: Backtesting System (4-5 hours)

**Goal**: Build the historical simulation engine

#### Step 4.1: Position Manager
**File**: `ktrdr/backtesting/position_manager.py`
```python
# Copy from ADR-005: Position, Trade, PositionManager classes
# Tracks positions and generates trade records
```

#### Step 4.2: Performance Analytics
**File**: `ktrdr/backtesting/performance.py`
```python
# Copy from ADR-005: PerformanceMetrics, PerformanceTracker classes
# Calculates Sharpe ratio, drawdown, win rate, etc.
```

#### Step 4.3: Backtesting Engine
**File**: `ktrdr/backtesting/engine.py`
```python
# Copy from ADR-005: BacktestingEngine class
# Main event-driven simulation loop
```

#### Step 4.4: API Routes
**File**: `ktrdr/api/backtesting_routes.py`
```python
# Copy from ADR-005: FastAPI routes
# Add to your existing FastAPI app
```

#### Step 4.5: CLI Client
**File**: `ktrdr/backtesting/cli.py`
```python
# Copy from ADR-005: CLI implementation
# Uses the API to run backtests
```

#### Step 4.6: Run Your First Backtest
```bash
# Start the API server (if not already running)
uvicorn ktrdr.api.main:app --reload

# In another terminal, run backtest
python -m ktrdr.backtesting.cli \
    --strategy neuro_mean_reversion \
    --symbol AAPL \
    --timeframe 1h \
    --start-date 2024-01-01 \
    --end-date 2024-06-01 \
    --verbose

# You should see output like:
# BACKTEST RESULTS - neuro_mean_reversion on AAPL 1h
# ═══════════════════════════════════════════════════
# Performance Metrics:
# ┌─────────────────────┬──────────────┬────────────┐
# │ Total Return        │ $2,543.21    │ 2.54%      │
# │ Sharpe Ratio        │              │ 1.234      │
# │ Win Rate            │              │ 58.3%      │
# └─────────────────────┴──────────────┴────────────┘
```

---

## 🧪 Testing Strategy

### Unit Tests (Run after each phase)
```bash
# Phase 1: Test neural network
pytest tests/test_neural_model.py

# Phase 2: Test training pipeline
pytest tests/test_training.py

# Phase 3: Test orchestrator
pytest tests/test_orchestrator.py

# Phase 4: Test backtesting
pytest tests/test_backtesting.py
```

### Integration Test (Final validation)
```python
# Full pipeline test: train → backtest
# 1. Train a model on 2023 data
# 2. Backtest on 2024 data
# 3. Verify positive Sharpe ratio (or at least reasonable metrics)
```

---

## 🐛 Common Issues and Solutions

### Issue 1: Model not loading
```python
# Check model path exists
import os
model_path = "models/neuro_mean_reversion/AAPL_1h_v1/"
assert os.path.exists(model_path), f"Model not found at {model_path}"
```

### Issue 2: Feature dimension mismatch
```python
# Ensure feature count matches model input size
# Check the model's expected input size in model.pt metadata
```

### Issue 3: No trades in backtest
```python
# Check confidence threshold in strategy config
# Verify neural network is outputting varied signals (not all HOLD)
# Look at verbose output to see decision reasoning
```

---

## 📁 Final File Structure

After completing all phases, you should have:

```
ktrdr/
├── decision/
│   ├── __init__.py
│   ├── base.py           # Signal, Position enums
│   ├── engine.py         # DecisionEngine from ADR-003
│   └── orchestrator.py   # DecisionOrchestrator from ADR-002
├── neural/
│   ├── __init__.py
│   └── models/
│       ├── __init__.py
│       ├── base_model.py
│       └── mlp.py        # Neural network implementation
├── training/
│   ├── __init__.py
│   ├── zigzag_labeler.py
│   ├── feature_engineering.py
│   ├── model_trainer.py
│   ├── model_storage.py
│   ├── train_strategy.py
│   └── cli.py
├── backtesting/
│   ├── __init__.py
│   ├── engine.py
│   ├── position_manager.py
│   ├── performance.py
│   ├── model_loader.py
│   └── cli.py
├── api/
│   ├── backtesting_routes.py  # New routes
│   └── ...existing routes...
strategies/
├── neuro_mean_reversion.yaml
models/
└── neuro_mean_reversion/
    └── AAPL_1h_v1/
        ├── model.pt
        ├── config.yaml
        ├── metrics.json
        └── feature_importance.json
```

---

## 🚀 Next Steps After MVP

Once the MVP is working:

1. **Enhance the Neural Network**: Try LSTM or larger architectures
2. **Multi-Symbol Support**: Train on multiple symbols
3. **Paper Trading**: Connect to IB paper account
4. **Strategy Optimization**: Grid search for better parameters
5. **Risk Management**: Add stop losses and position sizing

---

## 💡 Tips for Claude Code

1. **Start Small**: Get Phase 1 working with dummy data before moving on
2. **Use Existing Code**: Copy implementations from ADRs as starting points
3. **Test Incrementally**: Verify each component works before integration
4. **Check Logs**: Add print statements to understand data flow
5. **Validate Shapes**: Always verify tensor/dataframe dimensions match

Remember: The goal is a working MVP that can train a model and backtest it. Optimization and enhancements come later!
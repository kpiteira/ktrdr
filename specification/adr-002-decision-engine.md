# ADR-002: Core Decision Engine Architecture

## Status
**Draft** - December 2024

## Context
The Core Decision Engine is the central orchestrator that ties together all KTRDR components. It coordinates the flow from market data through indicators and fuzzy logic to neural network decisions, while managing state and enforcing risk controls.

This document clarifies how the Decision Engine integrates with:
- **ADR-003**: Uses the neural network models and decision logic
- **ADR-004**: Leverages trained models created by the training system
- **ADR-005**: Provides decisions during backtesting simulation

## Decision

### Architectural Overview

The Decision Engine acts as the central coordinator, using a **pipeline pattern** with clear interfaces:

```
                           Decision Engine
                                 │
    ┌────────────┬───────────────┼───────────────┬─────────────┐
    ▼            ▼               ▼               ▼             ▼
DataManager  IndicatorEngine  FuzzyEngine  NeuralModel  PositionState
(Existing)    (Existing)      (Existing)   (ADR-003)    (Internal)
```

### Integration with Other ADRs

#### With ADR-003 (Neuro-Fuzzy Framework)
- **Uses**: `DecisionEngine` class defined in ADR-003
- **Extends**: Adds full orchestration around the decision logic
- **Key Integration**: Neural model inference for signal generation

#### With ADR-004 (Training System)
- **Uses**: Trained models saved by the training system
- **Key Integration**: `ModelLoader` to load trained models
- **Shared**: Feature engineering pipeline

#### With ADR-005 (Backtesting System)
- **Used By**: Backtesting engine calls decision engine
- **Key Integration**: Provides decisions during simulation
- **Shared**: Decision context and state management

### Core Architecture

```python
# ktrdr/decision/orchestrator.py
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import pandas as pd
from pathlib import Path
from enum import Enum

# Reuse enums from ADR-003
from ktrdr.decision.engine import Signal, Position, TradingDecision

@dataclass
class DecisionContext:
    """Complete context for making a trading decision"""
    # Market data
    current_bar: pd.Series
    recent_bars: pd.DataFrame  # Lookback window
    
    # Calculated features
    indicators: Dict[str, float]
    fuzzy_memberships: Dict[str, float]
    
    # Position state
    current_position: Position
    position_entry_price: Optional[float]
    position_holding_period: Optional[float]
    unrealized_pnl: Optional[float]
    
    # Account state
    portfolio_value: float
    available_capital: float
    
    # Historical context
    recent_decisions: List[TradingDecision]
    last_signal_time: Optional[pd.Timestamp]

class DecisionOrchestrator:
    """
    Central orchestrator that coordinates the complete decision pipeline.
    This is the main entry point for all trading decisions.
    """
    
    def __init__(self, 
                 strategy_config_path: str,
                 model_path: Optional[str] = None,
                 mode: str = "backtest"):  # backtest, paper, live
        """
        Initialize the decision orchestrator
        
        Args:
            strategy_config_path: Path to strategy YAML file
            model_path: Path to trained model (if None, loads latest)
            mode: Operating mode affecting behavior
        """
        self.mode = mode
        
        # Load strategy configuration
        self.strategy_config = self._load_strategy_config(strategy_config_path)
        self.strategy_name = self.strategy_config['name']
        
        # Initialize data pipeline components (existing)
        self.data_manager = DataManager()
        self.indicator_engine = IndicatorEngine()
        self.fuzzy_engine = FuzzyEngine()
        
        # Load trained model (from ADR-004)
        self.model_loader = ModelLoader()
        if model_path:
            self.model, _ = self.model_loader.load_model(model_path)
        else:
            # Load latest model for strategy/symbol/timeframe
            # This will be determined by backtesting/live config
            self.model = None  # Loaded per symbol in multi-symbol setup
        
        # Initialize decision engine (from ADR-003)
        self.decision_engine = DecisionEngine(
            strategy_config=self.strategy_config
        )
        if self.model:
            self.decision_engine.neural_model = self.model
        
        # State management
        self.position_states = {}  # symbol -> PositionState
        self.decision_history = []  # Recent decisions
        self.max_history = 100
        
    def make_decision(self, 
                     symbol: str, 
                     timeframe: str,
                     current_bar: pd.Series,
                     historical_data: pd.DataFrame,
                     portfolio_state: Dict[str, Any]) -> TradingDecision:
        """
        Main entry point for generating trading decisions.
        
        This method:
        1. Calculates indicators from historical data
        2. Generates fuzzy memberships
        3. Prepares feature vector
        4. Gets neural network decision
        5. Applies risk and position logic
        6. Returns final trading decision
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (must match model training)
            current_bar: Latest price bar
            historical_data: Historical bars including current
            portfolio_state: Current portfolio/account state
            
        Returns:
            TradingDecision with signal, confidence, and metadata
        """
        # Step 1: Calculate indicators
        indicators = self.indicator_engine.calculate_multiple(
            data=historical_data,
            configs=self.strategy_config['indicators']
        )
        
        # Step 2: Generate fuzzy memberships
        fuzzy_values = self.fuzzy_engine.evaluate_batch(
            indicators=indicators,
            fuzzy_config=self.strategy_config['fuzzy_sets']
        )
        
        # Step 3: Prepare decision context
        context = self._prepare_context(
            symbol=symbol,
            current_bar=current_bar,
            historical_data=historical_data,
            indicators=indicators.iloc[-1].to_dict(),
            fuzzy_memberships=fuzzy_values.iloc[-1].to_dict(),
            portfolio_state=portfolio_state
        )
        
        # Step 4: Load model if needed (for multi-symbol support)
        if not self.model:
            self.model = self._load_model_for_symbol(symbol, timeframe)
            self.decision_engine.neural_model = self.model
        
        # Step 5: Generate decision
        decision = self.decision_engine.generate_decision(
            current_data=current_bar,
            fuzzy_memberships=context.fuzzy_memberships,
            indicators=context.indicators
        )
        
        # Step 6: Apply orchestrator-level logic
        final_decision = self._apply_orchestrator_logic(decision, context)
        
        # Step 7: Update state
        self._update_state(symbol, final_decision, context)
        
        return final_decision
    
    def _prepare_context(self, 
                        symbol: str,
                        current_bar: pd.Series,
                        historical_data: pd.DataFrame,
                        indicators: Dict[str, float],
                        fuzzy_memberships: Dict[str, float],
                        portfolio_state: Dict[str, Any]) -> DecisionContext:
        """Prepare complete context for decision making"""
        
        # Get or create position state
        if symbol not in self.position_states:
            self.position_states[symbol] = PositionState(symbol)
        
        position_state = self.position_states[symbol]
        
        # Get recent decisions for this symbol
        recent_decisions = [
            d for d in self.decision_history[-20:]  # Last 20 decisions
            if hasattr(d, 'symbol') and d.symbol == symbol
        ]
        
        return DecisionContext(
            current_bar=current_bar,
            recent_bars=historical_data.tail(20),  # Last 20 bars
            indicators=indicators,
            fuzzy_memberships=fuzzy_memberships,
            current_position=position_state.position,
            position_entry_price=position_state.entry_price,
            position_holding_period=position_state.holding_period,
            unrealized_pnl=position_state.unrealized_pnl,
            portfolio_value=portfolio_state['total_value'],
            available_capital=portfolio_state['available_capital'],
            recent_decisions=recent_decisions,
            last_signal_time=position_state.last_signal_time
        )
    
    def _apply_orchestrator_logic(self, 
                                 decision: TradingDecision,
                                 context: DecisionContext) -> TradingDecision:
        """
        Apply additional orchestrator-level logic beyond the neural network.
        This includes risk checks and mode-specific behavior.
        """
        
        # Risk check: Maximum position size
        if self.mode != "backtest":  # More strict in live modes
            if context.available_capital < 1000:  # Minimum capital threshold
                decision.signal = Signal.HOLD
                decision.reasoning['risk_override'] = "Insufficient capital"
        
        # Mode-specific overrides
        if self.mode == "paper":
            # Could add paper-trading specific logic
            pass
        elif self.mode == "live":
            # Could add extra safety checks for live trading
            if decision.confidence < 0.7:  # Higher confidence required for live
                decision.signal = Signal.HOLD
                decision.reasoning['risk_override'] = "Confidence too low for live trading"
        
        return decision
    
    def _update_state(self, symbol: str, decision: TradingDecision, 
                     context: DecisionContext):
        """Update internal state after decision"""
        
        # Update position state
        position_state = self.position_states[symbol]
        position_state.update_from_decision(decision, context.current_bar)
        
        # Add to history
        self.decision_history.append(decision)
        if len(self.decision_history) > self.max_history:
            self.decision_history.pop(0)
    
    def _load_model_for_symbol(self, symbol: str, timeframe: str):
        """Load the appropriate model for a symbol"""
        # This enables multi-symbol support in the future
        return self.model_loader.load_model(
            strategy_name=self.strategy_name,
            symbol=symbol,
            timeframe=timeframe
        )[0]  # Return just the model

class PositionState:
    """Track position state for a single symbol"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.position = Position.FLAT
        self.entry_price = None
        self.entry_time = None
        self.last_signal_time = None
        self.unrealized_pnl = 0.0
        
    @property
    def holding_period(self) -> Optional[float]:
        """Holding period in hours"""
        if self.entry_time:
            return (pd.Timestamp.now() - self.entry_time).total_seconds() / 3600
        return None
    
    def update_from_decision(self, decision: TradingDecision, current_bar: pd.Series):
        """Update state based on decision"""
        if decision.signal != Signal.HOLD:
            self.last_signal_time = current_bar.name
            
            if decision.signal == Signal.BUY and self.position == Position.FLAT:
                self.position = Position.LONG
                self.entry_price = current_bar['close']
                self.entry_time = current_bar.name
            elif decision.signal == Signal.SELL and self.position == Position.LONG:
                self.position = Position.FLAT
                self.entry_price = None
                self.entry_time = None
```

### Implementation Flow for Claude Code

To implement the complete system, follow this order:

#### Phase 1: Neural Network Foundation
1. **Implement ADR-003 Decision Logic**
   ```python
   # Start with ktrdr/decision/engine.py from ADR-003
   # This provides Signal, Position, TradingDecision classes
   # and the basic DecisionEngine
   ```

2. **Implement Neural Network Model**
   ```python
   # ktrdr/neural/models/mlp.py from ADR-003
   # Basic MLP architecture that processes fuzzy inputs
   ```

#### Phase 2: Training System
3. **Implement ZigZag Labeler**
   ```python
   # ktrdr/training/zigzag_labeler.py from ADR-003/004
   # Generates training labels from price data
   ```

4. **Implement Training Pipeline**
   ```python
   # ktrdr/training/train_strategy.py from ADR-004
   # Complete pipeline: data → indicators → fuzzy → features → training
   ```

5. **Test Training**
   ```bash
   # Train a simple model
   python -m ktrdr.training.cli \
     --strategy strategies/neuro_mean_reversion.yaml \
     --symbol AAPL \
     --timeframe 1h
   ```

#### Phase 3: Decision Orchestration
6. **Implement Decision Orchestrator**
   ```python
   # ktrdr/decision/orchestrator.py (from this ADR)
   # Ties everything together
   ```

7. **Integration Test**
   ```python
   # Test that orchestrator can load model and make decisions
   orchestrator = DecisionOrchestrator(
       strategy_config_path="strategies/neuro_mean_reversion.yaml",
       model_path="models/neuro_mean_reversion/AAPL_1h_v1/"
   )
   
   decision = orchestrator.make_decision(
       symbol="AAPL",
       timeframe="1h", 
       current_bar=data.iloc[-1],
       historical_data=data,
       portfolio_state={"total_value": 100000, "available_capital": 100000}
   )
   ```

#### Phase 4: Backtesting Integration
8. **Implement Backtesting Engine**
   ```python
   # ktrdr/backtesting/engine.py from ADR-005
   # Uses DecisionOrchestrator in its main loop
   ```

9. **Complete Integration**
   ```python
   # In BacktestingEngine.run():
   decision = self.orchestrator.make_decision(
       symbol=self.config.symbol,
       timeframe=self.config.timeframe,
       current_bar=current_bar,
       historical_data=data[:idx+1],
       portfolio_state={
           "total_value": self.position_manager.get_portfolio_value(current_price),
           "available_capital": self.position_manager.current_capital
       }
   )
   ```

### Configuration Example

```yaml
# strategies/neuro_mean_reversion.yaml
name: "neuro_mean_reversion"
version: "1.0"

# ... indicators, fuzzy_sets, model config from ADR-003 ...

# Decision orchestrator settings
orchestrator:
  min_confidence: 0.6
  max_position_size: 0.95  # Use max 95% of capital
  signal_cooldown: 4  # Minimum bars between signals
  
  # Mode-specific settings
  modes:
    backtest:
      confidence_threshold: 0.6
    paper:
      confidence_threshold: 0.65
    live:
      confidence_threshold: 0.7
      require_confirmation: true
```

### API Integration

The Decision Orchestrator integrates with the API layer:

```python
# ktrdr/api/decision_routes.py
@router.post("/api/v1/decisions/evaluate")
async def evaluate_decision(
    symbol: str,
    timeframe: str,
    strategy: str,
    mode: str = "backtest"
):
    """Get a trading decision for current market conditions"""
    
    # Load data
    data = data_manager.load_data(symbol, timeframe, mode="tail")
    
    # Get decision
    orchestrator = DecisionOrchestrator(
        strategy_config_path=f"strategies/{strategy}.yaml",
        mode=mode
    )
    
    decision = orchestrator.make_decision(
        symbol=symbol,
        timeframe=timeframe,
        current_bar=data.iloc[-1],
        historical_data=data,
        portfolio_state=get_portfolio_state()  # From portfolio manager
    )
    
    return {
        "signal": decision.signal.value,
        "confidence": decision.confidence,
        "reasoning": decision.reasoning,
        "timestamp": decision.timestamp
    }
```

## Key Integration Points

### 1. With Existing KTRDR Modules
```python
# The orchestrator uses existing modules directly
self.data_manager = DataManager()        # Existing data management
self.indicator_engine = IndicatorEngine() # Existing indicators
self.fuzzy_engine = FuzzyEngine()        # Existing fuzzy logic
```

### 2. With Training System (ADR-004)
```python
# Load models created by training system
self.model_loader = ModelLoader()  # From ADR-004
self.model = self.model_loader.load_model(...)
```

### 3. With Backtesting (ADR-005)
```python
# Backtesting engine uses orchestrator
class BacktestingEngine:
    def __init__(self, config):
        self.orchestrator = DecisionOrchestrator(
            strategy_config_path=config.strategy_path,
            model_path=config.model_path,
            mode="backtest"
        )
    
    def run(self):
        # In main loop
        decision = self.orchestrator.make_decision(...)
```

## Implementation Checklist for Claude Code

### Immediate MVP Tasks
1. [ ] Create `ktrdr/decision/` module structure
2. [ ] Copy base classes from ADR-003 (Signal, Position, TradingDecision)
3. [ ] Implement DecisionOrchestrator class
4. [ ] Create PositionState tracking
5. [ ] Add DecisionContext dataclass
6. [ ] Integrate with existing modules (data, indicators, fuzzy)
7. [ ] Add mode-specific configuration
8. [ ] Create unit tests for orchestrator
9. [ ] Create integration test with dummy model
10. [ ] Document usage examples

### Integration Tasks
1. [ ] Modify training system to save model input size
2. [ ] Update backtesting engine to use orchestrator
3. [ ] Add orchestrator configuration to strategy YAML
4. [ ] Create example strategy configuration
5. [ ] Test full pipeline: train → backtest

## Consequences

### Positive Consequences
- **Clear integration**: Shows exactly how all pieces fit together
- **Single entry point**: All decisions go through orchestrator
- **Mode flexibility**: Same code for backtest/paper/live
- **State management**: Proper tracking of positions and history
- **Extensible**: Easy to add new risk rules or modes

### Negative Consequences
- **Complexity**: Another layer of abstraction
- **State management**: Must carefully manage state
- **Configuration**: More configuration options to manage

## Conclusion

The Decision Orchestrator provides the **critical glue** that connects all KTRDR components into a functioning trading system. It clearly shows how:

1. **Training creates models** (ADR-004)
2. **Models make decisions** (ADR-003)  
3. **Orchestrator coordinates everything** (this ADR)
4. **Backtesting validates strategies** (ADR-005)

This design provides a clear implementation path for Claude Code while maintaining the flexibility to evolve the system toward paper and live trading.
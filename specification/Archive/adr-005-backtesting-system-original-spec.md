# ADR-005: Backtesting System Design

## Status
**Draft** - December 2024

## Context
With the neuro-fuzzy strategy framework (ADR-003) and training system (ADR-004) in place, we need a robust backtesting system to evaluate trained models on historical data. This system must simulate realistic trading conditions while providing comprehensive performance metrics and detailed trade analysis.

The backtesting system serves as the critical validation step before paper trading, allowing us to understand strategy behavior, risk characteristics, and expected performance without risking capital.

## Decision

### Backtesting Architecture

The backtesting system follows an event-driven architecture that processes historical data bar-by-bar, maintaining full position state and generating detailed performance analytics:

```
Historical Data → Event Stream → Decision Engine → Position Manager → Performance Analytics
      ↓              ↓              ↓                ↓                  ↓
    OHLCV      Price Updates   Neural Network    Trade Execution    Metrics & Reports
                                Decisions         Simulation
```

### Core Components

#### 1. Backtesting Engine
**Module**: `ktrdr/backtesting/engine.py`
**Purpose**: Orchestrate the event-driven simulation

```python
# ktrdr/backtesting/engine.py
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import pandas as pd
from datetime import datetime
from pathlib import Path

@dataclass
class BacktestConfig:
    """Configuration for backtesting run"""
    model_path: Path
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005  # 0.05%
    verbose: bool = False

class BacktestingEngine:
    """
    Event-driven backtesting engine that simulates trading
    using trained neural network models
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        
        # Initialize components
        self.data_manager = DataManager()
        self.indicator_engine = IndicatorEngine()
        self.fuzzy_engine = FuzzyEngine()
        self.model_loader = ModelLoader()
        self.position_manager = PositionManager(
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage
        )
        self.performance_tracker = PerformanceTracker()
        
        # Load the trained model and its configuration
        self.model, self.strategy_config = self.model_loader.load_model(
            config.model_path
        )
        
        # Decision engine with loaded model
        self.decision_engine = DecisionEngine(
            model=self.model,
            strategy_config=self.strategy_config
        )
        
    def run(self) -> BacktestResults:
        """
        Execute the backtest simulation
        
        Returns comprehensive results including trades, metrics, and analysis
        """
        # Load historical data
        print(f"Loading data for {self.config.symbol} {self.config.timeframe}...")
        data = self.data_manager.load_data(
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            mode="full"
        )
        
        # Pre-calculate all indicators for efficiency
        print("Calculating indicators...")
        indicators = self.indicator_engine.calculate_multiple(
            data=data,
            configs=self.strategy_config['indicators']
        )
        
        # Pre-calculate fuzzy memberships
        print("Computing fuzzy memberships...")
        fuzzy_values = self.fuzzy_engine.evaluate_batch(
            indicators=indicators,
            fuzzy_config=self.strategy_config['fuzzy_sets']
        )
        
        # Initialize event loop
        print(f"Running backtest from {self.config.start_date} to {self.config.end_date}...")
        
        for idx in range(len(data)):
            # Create event for current bar
            event = self._create_price_event(data.iloc[idx], idx)
            
            # Get current features for decision
            current_features = self._prepare_features(
                data.iloc[:idx+1],
                indicators.iloc[:idx+1],
                fuzzy_values.iloc[:idx+1]
            )
            
            # Generate trading decision
            decision = self.decision_engine.generate_decision(
                current_features=current_features,
                current_price=event.close,
                current_position=self.position_manager.current_position
            )
            
            # Execute decision if action required
            if decision.signal != Signal.HOLD:
                trade = self.position_manager.execute_trade(
                    signal=decision.signal,
                    price=event.close,
                    timestamp=event.timestamp,
                    decision_metadata=decision.metadata
                )
                
                if trade and self.config.verbose:
                    print(f"{event.timestamp}: {decision.signal} @ {event.close:.2f} "
                          f"(confidence: {decision.confidence:.2f})")
            
            # Update position with current market price
            self.position_manager.update_position(event.close, event.timestamp)
            
            # Track performance metrics
            self.performance_tracker.update(
                timestamp=event.timestamp,
                price=event.close,
                portfolio_value=self.position_manager.get_portfolio_value(event.close),
                position=self.position_manager.current_position
            )
        
        # Generate final results
        results = self._generate_results()
        
        return results
    
    def _create_price_event(self, bar: pd.Series, index: int) -> PriceEvent:
        """Create a price event from a data bar"""
        return PriceEvent(
            timestamp=bar.name,
            open=bar['open'],
            high=bar['high'],
            low=bar['low'],
            close=bar['close'],
            volume=bar['volume'],
            bar_index=index
        )
    
    def _prepare_features(self, data: pd.DataFrame, 
                         indicators: pd.DataFrame,
                         fuzzy_values: pd.DataFrame) -> Dict[str, Any]:
        """Prepare features for the current decision point"""
        # Use the feature engineering from training
        feature_engineer = FeatureEngineer(
            self.strategy_config.get('features', {})
        )
        
        features = feature_engineer.prepare_features(
            data=data,
            indicators=indicators,
            fuzzy_values=fuzzy_values
        )
        
        # Return the last row (current features)
        return features.iloc[-1].to_dict()
    
    def _generate_results(self) -> BacktestResults:
        """Compile comprehensive backtest results"""
        trades = self.position_manager.get_trade_history()
        metrics = self.performance_tracker.calculate_metrics()
        equity_curve = self.performance_tracker.get_equity_curve()
        
        return BacktestResults(
            trades=trades,
            metrics=metrics,
            equity_curve=equity_curve,
            config=self.config,
            strategy_name=self.strategy_config['name']
        )
```

#### 2. Position Management
**Module**: `ktrdr/backtesting/position_manager.py`
**Purpose**: Track positions, execute trades, manage P&L

```python
# ktrdr/backtesting/position_manager.py
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class PositionStatus(Enum):
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class Position:
    """Detailed position tracking"""
    status: PositionStatus
    entry_price: float
    entry_time: datetime
    quantity: int
    current_price: float
    last_update_time: datetime
    unrealized_pnl: float = 0.0
    max_favorable_excursion: float = 0.0  # Best unrealized profit
    max_adverse_excursion: float = 0.0    # Worst unrealized loss
    
    @property
    def holding_period(self) -> float:
        """Holding period in hours"""
        if self.last_update_time and self.entry_time:
            return (self.last_update_time - self.entry_time).total_seconds() / 3600
        return 0.0
    
    def update(self, current_price: float, timestamp: datetime):
        """Update position with current market price"""
        self.current_price = current_price
        self.last_update_time = timestamp
        
        # Calculate unrealized P&L
        if self.status == PositionStatus.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        elif self.status == PositionStatus.SHORT:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity
        else:
            self.unrealized_pnl = 0.0
        
        # Track excursions
        self.max_favorable_excursion = max(self.max_favorable_excursion, self.unrealized_pnl)
        self.max_adverse_excursion = min(self.max_adverse_excursion, self.unrealized_pnl)

@dataclass
class Trade:
    """Completed trade record"""
    trade_id: int
    symbol: str
    side: str  # BUY or SELL
    entry_price: float
    entry_time: datetime
    exit_price: float
    exit_time: datetime
    quantity: int
    gross_pnl: float
    commission: float
    slippage: float
    net_pnl: float
    holding_period_hours: float
    max_favorable_excursion: float
    max_adverse_excursion: float
    decision_metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def return_pct(self) -> float:
        """Return percentage"""
        return (self.net_pnl / (self.entry_price * self.quantity)) * 100

class PositionManager:
    """Manages positions and trade execution with detailed tracking"""
    
    def __init__(self, initial_capital: float, commission: float, slippage: float):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        
        self.current_position: Optional[Position] = None
        self.trade_history: List[Trade] = []
        self.next_trade_id = 1
        
    @property
    def position_status(self) -> PositionStatus:
        """Current position status"""
        return self.current_position.status if self.current_position else PositionStatus.FLAT
    
    def execute_trade(self, signal: Signal, price: float, 
                     timestamp: datetime, decision_metadata: Dict[str, Any]) -> Optional[Trade]:
        """
        Execute a trade based on signal
        
        Handles:
        - Opening new positions
        - Closing existing positions
        - Reversing positions
        """
        executed_trade = None
        
        # Apply slippage to execution price
        if signal == Signal.BUY:
            execution_price = price * (1 + self.slippage)
        else:  # SELL
            execution_price = price * (1 - self.slippage)
        
        # Determine position size
        position_size = self._calculate_position_size(execution_price)
        
        # Handle based on current position
        if self.position_status == PositionStatus.FLAT:
            # Open new position
            if signal == Signal.BUY:
                self._open_position(PositionStatus.LONG, execution_price, 
                                  timestamp, position_size)
            elif signal == Signal.SELL:
                self._open_position(PositionStatus.SHORT, execution_price, 
                                  timestamp, position_size)
                
        elif self.position_status == PositionStatus.LONG:
            if signal == Signal.SELL:
                # Close long position
                executed_trade = self._close_position(execution_price, timestamp, 
                                                    decision_metadata)
                # Optionally open short
                # self._open_position(PositionStatus.SHORT, execution_price, 
                #                   timestamp, position_size)
                
        elif self.position_status == PositionStatus.SHORT:
            if signal == Signal.BUY:
                # Close short position
                executed_trade = self._close_position(execution_price, timestamp,
                                                    decision_metadata)
                # Optionally open long
                # self._open_position(PositionStatus.LONG, execution_price,
                #                   timestamp, position_size)
        
        return executed_trade
    
    def _calculate_position_size(self, price: float) -> int:
        """Calculate position size based on available capital"""
        # Simple sizing: use 95% of capital to leave room for commission/slippage
        max_shares = int((self.current_capital * 0.95) / price)
        return max(1, max_shares)
    
    def _open_position(self, position_type: PositionStatus, price: float,
                      timestamp: datetime, quantity: int):
        """Open a new position"""
        self.current_position = Position(
            status=position_type,
            entry_price=price,
            entry_time=timestamp,
            quantity=quantity,
            current_price=price,
            last_update_time=timestamp
        )
        
        # Deduct capital for position
        self.current_capital -= (price * quantity * (1 + self.commission))
    
    def _close_position(self, exit_price: float, timestamp: datetime,
                       decision_metadata: Dict[str, Any]) -> Trade:
        """Close current position and record trade"""
        position = self.current_position
        
        # Calculate P&L
        if position.status == PositionStatus.LONG:
            gross_pnl = (exit_price - position.entry_price) * position.quantity
            side = "BUY"
        else:  # SHORT
            gross_pnl = (position.entry_price - exit_price) * position.quantity
            side = "SELL"
        
        # Calculate costs
        entry_commission = position.entry_price * position.quantity * self.commission
        exit_commission = exit_price * position.quantity * self.commission
        total_commission = entry_commission + exit_commission
        
        slippage_cost = abs(position.entry_price * position.quantity * self.slippage) + \
                       abs(exit_price * position.quantity * self.slippage)
        
        net_pnl = gross_pnl - total_commission - slippage_cost
        
        # Create trade record
        trade = Trade(
            trade_id=self.next_trade_id,
            symbol=self.config.symbol,  # Would need to pass this in
            side=side,
            entry_price=position.entry_price,
            entry_time=position.entry_time,
            exit_price=exit_price,
            exit_time=timestamp,
            quantity=position.quantity,
            gross_pnl=gross_pnl,
            commission=total_commission,
            slippage=slippage_cost,
            net_pnl=net_pnl,
            holding_period_hours=position.holding_period,
            max_favorable_excursion=position.max_favorable_excursion,
            max_adverse_excursion=position.max_adverse_excursion,
            decision_metadata=decision_metadata
        )
        
        # Update capital
        self.current_capital += (exit_price * position.quantity * (1 - self.commission))
        
        # Record trade
        self.trade_history.append(trade)
        self.next_trade_id += 1
        
        # Clear position
        self.current_position = None
        
        return trade
    
    def update_position(self, current_price: float, timestamp: datetime):
        """Update current position with latest price"""
        if self.current_position:
            self.current_position.update(current_price, timestamp)
    
    def get_portfolio_value(self, current_price: float) -> float:
        """Calculate total portfolio value"""
        if self.current_position:
            position_value = self.current_position.quantity * current_price
            return self.current_capital + position_value
        return self.current_capital
    
    def get_trade_history(self) -> List[Trade]:
        """Get all completed trades"""
        return self.trade_history
```

#### 3. Performance Analytics
**Module**: `ktrdr/backtesting/performance.py`
**Purpose**: Calculate comprehensive performance metrics

```python
# ktrdr/backtesting/performance.py
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    # Returns
    total_return: float
    total_return_pct: float
    annualized_return: float
    
    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration_days: float
    volatility: float
    
    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: float
    
    # Trade timing
    average_holding_period_hours: float
    max_holding_period_hours: float
    min_holding_period_hours: float
    
    # Excursion analysis
    avg_max_favorable_excursion: float
    avg_max_adverse_excursion: float
    
    # Risk-adjusted metrics
    calmar_ratio: float
    risk_reward_ratio: float

class PerformanceTracker:
    """Track and calculate performance metrics during backtesting"""
    
    def __init__(self):
        self.equity_curve = []
        self.timestamps = []
        self.positions = []
        self.daily_returns = []
        
    def update(self, timestamp: datetime, price: float, 
               portfolio_value: float, position: PositionStatus):
        """Update tracking with current state"""
        self.timestamps.append(timestamp)
        self.equity_curve.append(portfolio_value)
        self.positions.append(position.value if position else "FLAT")
        
        # Calculate daily returns if we have previous day
        if len(self.equity_curve) > 1:
            daily_return = (portfolio_value - self.equity_curve[-2]) / self.equity_curve[-2]
            self.daily_returns.append(daily_return)
    
    def calculate_metrics(self, trades: List[Trade] = None) -> PerformanceMetrics:
        """Calculate all performance metrics"""
        if not self.equity_curve:
            return self._empty_metrics()
        
        # Basic returns
        initial_value = self.equity_curve[0]
        final_value = self.equity_curve[-1]
        total_return = final_value - initial_value
        total_return_pct = (total_return / initial_value) * 100
        
        # Annualized return
        days = (self.timestamps[-1] - self.timestamps[0]).days
        years = days / 365.25
        annualized_return = ((final_value / initial_value) ** (1/years) - 1) * 100 if years > 0 else 0
        
        # Risk metrics
        returns_array = np.array(self.daily_returns)
        volatility = np.std(returns_array) * np.sqrt(252) if len(returns_array) > 1 else 0
        
        # Sharpe ratio (assuming 0% risk-free rate)
        sharpe_ratio = (annualized_return / volatility) if volatility > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns_array[returns_array < 0]
        downside_deviation = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 1 else 0
        sortino_ratio = (annualized_return / downside_deviation) if downside_deviation > 0 else 0
        
        # Drawdown analysis
        equity_df = pd.DataFrame({
            'equity': self.equity_curve,
            'timestamp': self.timestamps
        })
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['cummax']) / equity_df['cummax']
        max_drawdown = equity_df['drawdown'].min() * 100
        
        # Drawdown duration
        drawdown_duration = self._calculate_max_drawdown_duration(equity_df)
        
        # Trade statistics (if trades provided)
        if trades:
            trade_metrics = self._calculate_trade_metrics(trades)
        else:
            trade_metrics = self._empty_trade_metrics()
        
        # Calmar ratio
        calmar_ratio = abs(annualized_return / max_drawdown) if max_drawdown != 0 else 0
        
        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_duration_days=drawdown_duration,
            volatility=volatility * 100,
            calmar_ratio=calmar_ratio,
            **trade_metrics
        )
    
    def _calculate_trade_metrics(self, trades: List[Trade]) -> Dict[str, Any]:
        """Calculate trade-specific metrics"""
        if not trades:
            return self._empty_trade_metrics()
        
        # Win/loss analysis
        winning_trades = [t for t in trades if t.net_pnl > 0]
        losing_trades = [t for t in trades if t.net_pnl < 0]
        
        total_trades = len(trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # Average win/loss
        avg_win = np.mean([t.net_pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.net_pnl for t in losing_trades]) if losing_trades else 0
        
        # Profit factor
        gross_profits = sum(t.net_pnl for t in winning_trades)
        gross_losses = abs(sum(t.net_pnl for t in losing_trades))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')
        
        # Holding periods
        holding_periods = [t.holding_period_hours for t in trades]
        avg_holding = np.mean(holding_periods) if holding_periods else 0
        max_holding = max(holding_periods) if holding_periods else 0
        min_holding = min(holding_periods) if holding_periods else 0
        
        # Excursion analysis
        mfe_values = [t.max_favorable_excursion for t in trades]
        mae_values = [t.max_adverse_excursion for t in trades]
        avg_mfe = np.mean(mfe_values) if mfe_values else 0
        avg_mae = np.mean(mae_values) if mae_values else 0
        
        # Risk-reward ratio
        risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'average_win': avg_win,
            'average_loss': avg_loss,
            'profit_factor': profit_factor,
            'average_holding_period_hours': avg_holding,
            'max_holding_period_hours': max_holding,
            'min_holding_period_hours': min_holding,
            'avg_max_favorable_excursion': avg_mfe,
            'avg_max_adverse_excursion': avg_mae,
            'risk_reward_ratio': risk_reward
        }
```

#### 4. Model Loading and Version Management
**Module**: `ktrdr/backtesting/model_loader.py`
**Purpose**: Load trained models with version management

```python
# ktrdr/backtesting/model_loader.py
from pathlib import Path
import torch
import yaml
import json
from typing import Tuple, Dict, Any, Optional

class ModelLoader:
    """Handle loading of trained models for backtesting"""
    
    def __init__(self, models_base_path: str = "models"):
        self.models_base = Path(models_base_path)
        
    def load_model(self, model_path: Optional[Path] = None, 
                   strategy_name: Optional[str] = None,
                   symbol: Optional[str] = None,
                   timeframe: Optional[str] = None,
                   version: Optional[int] = None) -> Tuple[torch.nn.Module, Dict[str, Any]]:
        """
        Load a model either by explicit path or by strategy/symbol/timeframe
        
        If model_path is provided, use it directly.
        Otherwise, find the model based on strategy/symbol/timeframe/version.
        If version is not specified, use the latest.
        """
        if model_path:
            # Use explicit path
            model_dir = Path(model_path)
        else:
            # Find model by parameters
            if not all([strategy_name, symbol, timeframe]):
                raise ValueError("Must provide either model_path or strategy_name/symbol/timeframe")
            
            model_dir = self._find_model_directory(strategy_name, symbol, timeframe, version)
        
        # Load model components
        model = self._load_pytorch_model(model_dir / "model.pt")
        config = self._load_config(model_dir / "config.yaml")
        metrics = self._load_metrics(model_dir / "metrics.json")
        
        print(f"Loaded model from: {model_dir}")
        print(f"Model metrics: Accuracy={metrics['test_metrics'].get('accuracy', 'N/A'):.3f}")
        
        return model, config
    
    def _find_model_directory(self, strategy_name: str, symbol: str, 
                             timeframe: str, version: Optional[int] = None) -> Path:
        """Find model directory, defaulting to latest version if not specified"""
        strategy_dir = self.models_base / strategy_name
        
        if not strategy_dir.exists():
            raise ValueError(f"Strategy directory not found: {strategy_dir}")
        
        if version is not None:
            # Use specific version
            model_dir = strategy_dir / f"{symbol}_{timeframe}_v{version}"
            if not model_dir.exists():
                raise ValueError(f"Model version not found: {model_dir}")
            return model_dir
        
        # Find latest version
        pattern = f"{symbol}_{timeframe}_v*"
        versions = list(strategy_dir.glob(pattern))
        
        if not versions:
            raise ValueError(f"No models found for {symbol} {timeframe} in {strategy_dir}")
        
        # Sort by version number and get latest
        versions.sort(key=lambda p: int(p.name.split('_v')[-1]))
        return versions[-1]
    
    def _load_pytorch_model(self, model_path: Path) -> torch.nn.Module:
        """Load PyTorch model from file"""
        checkpoint = torch.load(model_path, map_location='cpu')
        
        # Recreate model architecture from config
        model_config = checkpoint['model_config']
        model = self._create_model_from_config(model_config)
        
        # Load weights
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        
        return model
    
    def _create_model_from_config(self, model_config: Dict[str, Any]) -> torch.nn.Module:
        """Recreate model architecture from configuration"""
        # This would use the same model creation logic from training
        from ktrdr.neural.models.mlp import MLPTradingModel
        
        model_wrapper = MLPTradingModel(model_config)
        input_size = model_config.get('input_size', 15)  # Should be saved in config
        return model_wrapper.build_model(input_size)
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load strategy configuration"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _load_metrics(self, metrics_path: Path) -> Dict[str, Any]:
        """Load training metrics"""
        with open(metrics_path, 'r') as f:
            return json.load(f)
```

#### 5. API Layer
**Module**: `ktrdr/api/backtesting_routes.py`
**Purpose**: RESTful API for backtesting (CLI will use this)

```python
# ktrdr/api/backtesting_routes.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

router = APIRouter()

# Request/Response models
class BacktestRequest(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    model_version: Optional[int] = None  # None means latest
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.0005
    verbose: bool = False

class BacktestResponse(BaseModel):
    backtest_id: str
    status: str  # "running", "completed", "failed"
    progress: float  # 0.0 to 1.0
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class TradeRecord(BaseModel):
    trade_id: int
    symbol: str
    side: str
    entry_price: float
    entry_time: datetime
    exit_price: float
    exit_time: datetime
    quantity: int
    net_pnl: float
    return_pct: float
    holding_period_hours: float

class BacktestResults(BaseModel):
    backtest_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    
    # Performance metrics
    metrics: Dict[str, float]
    
    # Trade history
    trades: List[TradeRecord]
    
    # Equity curve data
    equity_curve: List[Dict[str, Any]]  # timestamp, value pairs
    
    # Summary statistics
    summary: Dict[str, Any]

# In-memory storage for async backtests (would use Redis in production)
backtest_jobs = {}

@router.post("/api/v1/backtests/", response_model=BacktestResponse)
async def create_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """
    Start a new backtest run
    
    The backtest runs asynchronously and returns a job ID for status checking
    """
    # Generate unique backtest ID
    backtest_id = str(uuid.uuid4())
    
    # Initialize job status
    backtest_jobs[backtest_id] = {
        "status": "running",
        "progress": 0.0,
        "request": request.dict(),
        "started_at": datetime.now()
    }
    
    # Start backtest in background
    background_tasks.add_task(run_backtest_job, backtest_id, request)
    
    return BacktestResponse(
        backtest_id=backtest_id,
        status="running",
        progress=0.0
    )

@router.get("/api/v1/backtests/{backtest_id}", response_model=BacktestResponse)
async def get_backtest_status(backtest_id: str):
    """Get the status and results of a backtest"""
    if backtest_id not in backtest_jobs:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    job = backtest_jobs[backtest_id]
    
    return BacktestResponse(
        backtest_id=backtest_id,
        status=job["status"],
        progress=job.get("progress", 0.0),
        results=job.get("results"),
        error=job.get("error")
    )

@router.get("/api/v1/backtests/{backtest_id}/trades", response_model=List[TradeRecord])
async def get_backtest_trades(backtest_id: str, 
                             limit: Optional[int] = None,
                             offset: int = 0):
    """Get detailed trade history from a completed backtest"""
    if backtest_id not in backtest_jobs:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    job = backtest_jobs[backtest_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Backtest not completed")
    
    trades = job["results"]["trades"]
    
    # Apply pagination
    if limit:
        trades = trades[offset:offset + limit]
    else:
        trades = trades[offset:]
    
    return trades

@router.get("/api/v1/backtests/{backtest_id}/equity_curve")
async def get_equity_curve(backtest_id: str, 
                          resolution: Optional[str] = "1h"):
    """Get equity curve data for visualization"""
    if backtest_id not in backtest_jobs:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    job = backtest_jobs[backtest_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Backtest not completed")
    
    # Return equity curve data
    # Could resample based on resolution parameter
    return {
        "backtest_id": backtest_id,
        "resolution": resolution,
        "data": job["results"]["equity_curve"]
    }

async def run_backtest_job(backtest_id: str, request: BacktestRequest):
    """Background task to run the actual backtest"""
    try:
        # Update progress
        backtest_jobs[backtest_id]["progress"] = 0.1
        
        # Create backtest configuration
        config = BacktestConfig(
            model_path=None,  # Will use latest
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage,
            verbose=request.verbose
        )
        
        # Initialize and run backtest
        engine = BacktestingEngine(config)
        
        # Update progress periodically (would need callbacks in real implementation)
        backtest_jobs[backtest_id]["progress"] = 0.5
        
        results = engine.run()
        
        # Convert results to API format
        api_results = {
            "metrics": results.metrics.__dict__,
            "trades": [t.__dict__ for t in results.trades],
            "equity_curve": results.equity_curve,
            "summary": {
                "total_trades": len(results.trades),
                "final_capital": results.metrics.total_return + request.initial_capital,
                "best_trade": max(results.trades, key=lambda t: t.net_pnl).__dict__ if results.trades else None,
                "worst_trade": min(results.trades, key=lambda t: t.net_pnl).__dict__ if results.trades else None
            }
        }
        
        # Update job status
        backtest_jobs[backtest_id].update({
            "status": "completed",
            "progress": 1.0,
            "results": api_results,
            "completed_at": datetime.now()
        })
        
    except Exception as e:
        # Handle errors
        backtest_jobs[backtest_id].update({
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now()
        })
```

#### 6. CLI Interface
**Module**: `ktrdr/backtesting/cli.py`
**Purpose**: Command-line interface using the API

```python
# ktrdr/backtesting/cli.py
import click
import requests
import json
import time
from tabulate import tabulate
from typing import Optional

API_BASE_URL = "http://localhost:8000"

@click.command()
@click.option('--strategy', '-s', required=True, help='Strategy name')
@click.option('--symbol', required=True, help='Trading symbol')
@click.option('--timeframe', '-t', default='1h', help='Timeframe')
@click.option('--start-date', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end-date', required=True, help='End date (YYYY-MM-DD)')
@click.option('--model-version', '-v', type=int, help='Model version (latest if not specified)')
@click.option('--initial-capital', default=100000.0, help='Starting capital')
@click.option('--commission', default=0.001, help='Commission rate')
@click.option('--slippage', default=0.0005, help='Slippage rate')
@click.option('--verbose', is_flag=True, help='Verbose output with trade details')
@click.option('--output', '-o', type=click.Path(), help='Save results to file')
def backtest(strategy: str, symbol: str, timeframe: str,
            start_date: str, end_date: str,
            model_version: Optional[int],
            initial_capital: float, commission: float, slippage: float,
            verbose: bool, output: Optional[str]):
    """Run a backtest for a trained strategy"""
    
    # Create backtest request
    request_data = {
        "strategy_name": strategy,
        "symbol": symbol,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "model_version": model_version,
        "initial_capital": initial_capital,
        "commission": commission,
        "slippage": slippage,
        "verbose": verbose
    }
    
    click.echo(f"Starting backtest for {strategy} on {symbol} {timeframe}...")
    
    # Start backtest
    response = requests.post(f"{API_BASE_URL}/api/v1/backtests/", json=request_data)
    if response.status_code != 200:
        click.echo(f"Error starting backtest: {response.text}")
        return
    
    backtest_id = response.json()["backtest_id"]
    
    # Poll for completion
    with click.progressbar(length=100, label='Running backtest') as bar:
        last_progress = 0
        while True:
            status_response = requests.get(f"{API_BASE_URL}/api/v1/backtests/{backtest_id}")
            status_data = status_response.json()
            
            # Update progress
            current_progress = int(status_data["progress"] * 100)
            bar.update(current_progress - last_progress)
            last_progress = current_progress
            
            if status_data["status"] == "completed":
                break
            elif status_data["status"] == "failed":
                click.echo(f"\nBacktest failed: {status_data['error']}")
                return
            
            time.sleep(1)
    
    # Get results
    results = status_data["results"]
    
    # Display summary metrics
    click.echo("\n" + "="*80)
    click.echo(f"BACKTEST RESULTS - {strategy} on {symbol} {timeframe}")
    click.echo("="*80)
    
    # Performance metrics table
    metrics = results["metrics"]
    metrics_table = [
        ["Total Return", f"${metrics['total_return']:,.2f}", f"{metrics['total_return_pct']:.2f}%"],
        ["Annualized Return", "", f"{metrics['annualized_return']:.2f}%"],
        ["Sharpe Ratio", "", f"{metrics['sharpe_ratio']:.3f}"],
        ["Max Drawdown", "", f"{metrics['max_drawdown']:.2f}%"],
        ["Win Rate", "", f"{metrics['win_rate']*100:.1f}%"],
        ["Profit Factor", "", f"{metrics['profit_factor']:.2f}"],
        ["Total Trades", "", f"{metrics['total_trades']}"],
        ["Avg Holding Period", "", f"{metrics['average_holding_period_hours']:.1f} hours"]
    ]
    
    click.echo("\nPerformance Metrics:")
    click.echo(tabulate(metrics_table, headers=["Metric", "Value", "Percentage"], 
                       tablefmt="grid"))
    
    # Trade statistics
    if verbose and results["trades"]:
        click.echo("\nTrade History:")
        trades_table = []
        for trade in results["trades"][:10]:  # Show first 10 trades
            trades_table.append([
                trade["trade_id"],
                trade["side"],
                f"${trade['entry_price']:.2f}",
                f"${trade['exit_price']:.2f}",
                f"${trade['net_pnl']:.2f}",
                f"{trade['return_pct']:.2f}%",
                f"{trade['holding_period_hours']:.1f}h"
            ])
        
        click.echo(tabulate(trades_table, 
                           headers=["ID", "Side", "Entry", "Exit", "P&L", "Return", "Duration"],
                           tablefmt="grid"))
        
        if len(results["trades"]) > 10:
            click.echo(f"\n... and {len(results['trades']) - 10} more trades")
    
    # Summary statistics
    summary = results["summary"]
    click.echo(f"\nSummary:")
    click.echo(f"  Final Capital: ${summary['final_capital']:,.2f}")
    click.echo(f"  Total Trades: {summary['total_trades']}")
    
    if summary["best_trade"]:
        click.echo(f"  Best Trade: ${summary['best_trade']['net_pnl']:.2f} "
                  f"({summary['best_trade']['return_pct']:.2f}%)")
    if summary["worst_trade"]:
        click.echo(f"  Worst Trade: ${summary['worst_trade']['net_pnl']:.2f} "
                  f"({summary['worst_trade']['return_pct']:.2f}%)")
    
    # Save results if requested
    if output:
        with open(output, 'w') as f:
            json.dump({
                "backtest_id": backtest_id,
                "request": request_data,
                "results": results
            }, f, indent=2, default=str)
        click.echo(f"\nResults saved to: {output}")

# Usage:
# python -m ktrdr.backtesting.cli --strategy neuro_mean_reversion --symbol AAPL --timeframe 1h --start-date 2023-01-01 --end-date 2024-01-01 --verbose
```

## Architecture for Future Evolution

### Multi-Timeframe Support (Future)
The architecture is designed to support intrabar decisions and multi-timeframe analysis:

```python
# Future: Multi-timeframe decision context
class MultiTimeframeContext:
    def __init__(self, primary_timeframe: str, context_timeframes: List[str]):
        self.primary = primary_timeframe
        self.contexts = context_timeframes
        
    def get_decision_context(self, timestamp: datetime) -> Dict[str, Any]:
        # Aggregate information from multiple timeframes
        # E.g., 5m bars within current 1h bar
        pass
```

### Intrabar Execution (Future)
```python
# Future: Intrabar price modeling
class IntrabarPriceModel:
    def get_execution_price(self, bar: PriceBar, signal_time: float) -> float:
        # Model price movement within bar
        # Could use OHLC patterns, volume distribution, etc.
        pass
```

## Integration Points

### With Training System (ADR-004)
- Loads models created by the training system
- Uses same feature engineering pipeline
- Maintains strategy configuration compatibility

### With Existing KTRDR Systems
- Uses DataManager for historical data
- Uses IndicatorEngine for technical indicators
- Uses FuzzyEngine for membership calculations
- Extends API with new backtesting endpoints

## Consequences

### Positive Consequences
- **API-first design**: Enables both CLI and future frontend integration
- **Comprehensive tracking**: All position details for deep analysis
- **Event-driven architecture**: Realistic simulation and future evolution
- **Detailed metrics**: Everything needed for strategy evaluation
- **Modular design**: Easy to extend and test components

### Negative Consequences
- **Single instrument limitation**: MVP focuses on one symbol at a time
- **Close-only execution**: May miss intrabar opportunities
- **Memory usage**: Stores full trade history in memory
- **No optimization**: Single backtest runs only

### Mitigation Strategies
- Architecture supports multi-symbol extension
- Designed for future intrabar execution
- Can add database persistence later
- Clear path to parameter optimization

## Future Evolution Ideas

### 1. Portfolio Backtesting
**Rationale**: Test strategies across multiple instruments simultaneously
**Benefits**:
- Diversification analysis
- Correlation insights
- Capital allocation strategies

### 2. Walk-Forward Analysis
**Rationale**: Test strategy robustness over time
**Implementation**:
- Rolling training windows
- Out-of-sample validation
- Parameter stability analysis

### 3. Monte Carlo Simulation
**Rationale**: Understand strategy behavior under different scenarios
**Features**:
- Random trade ordering
- Slippage/commission variations
- Market regime changes

### 4. Advanced Execution Modeling
**Rationale**: More realistic trade execution
**Options**:
- Order book simulation
- Market impact modeling
- Smart order routing

### 5. Risk Analysis Suite
**Rationale**: Deeper understanding of strategy risks
**Metrics**:
- Value at Risk (VaR)
- Conditional VaR
- Stress testing
- Scenario analysis

### 6. Real-time Backtesting
**Rationale**: Validate strategies as new data arrives
**Features**:
- Continuous validation
- Performance degradation alerts
- Automatic retraining triggers

## Implementation Notes

### MVP Checklist
- [ ] Implement event-driven backtesting engine
- [ ] Create position manager with full tracking
- [ ] Build performance analytics calculator
- [ ] Implement model loader with version management
- [ ] Create FastAPI endpoints
- [ ] Build CLI client using API
- [ ] Add comprehensive logging
- [ ] Write unit and integration tests
- [ ] Create example backtest runs
- [ ] Document API and CLI usage

### Performance Considerations
- Use numpy arrays for calculations where possible
- Consider chunking for very long backtests
- Implement progress callbacks for UI updates
- Cache indicator calculations

### Testing Strategy
- Unit tests for each component
- Integration tests for full backtest runs
- Performance tests with large datasets
- Comparison with known results

## Conclusion

The Backtesting System provides a **comprehensive framework** for evaluating trained neuro-fuzzy strategies with realistic market simulation. The API-first design ensures easy integration with both CLI and future frontend systems while maintaining the flexibility for advanced features.

**Key design principles**:
- **Event-driven simulation**: Realistic and extensible
- **Comprehensive tracking**: Every detail for analysis
- **API-first architecture**: Multiple client support
- **Future-ready design**: Clear evolution paths
- **Performance focus**: Efficient calculations

This design ensures that strategies can be thoroughly validated before moving to paper trading, with all the data needed to make informed decisions about strategy deployment.
"""Backtesting engine for strategy evaluation."""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import pandas as pd
from pathlib import Path
import time

from .position_manager import PositionManager, Trade
from .performance import PerformanceTracker, PerformanceMetrics
from .model_loader import ModelLoader
from ..decision.orchestrator import DecisionOrchestrator
from ..decision.base import Signal
from ..data.data_manager import DataManager


@dataclass
class BacktestConfig:
    """Configuration for backtesting run."""
    strategy_config_path: str
    model_path: Optional[str]
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005  # 0.05%
    verbose: bool = False


@dataclass
class BacktestResults:
    """Comprehensive backtesting results."""
    strategy_name: str
    symbol: str
    timeframe: str
    config: BacktestConfig
    trades: List[Trade]
    metrics: PerformanceMetrics
    equity_curve: pd.DataFrame
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    execution_time_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "execution_time_seconds": self.execution_time_seconds,
            "config": {
                "initial_capital": self.config.initial_capital,
                "commission": self.config.commission,
                "slippage": self.config.slippage,
                "start_date": self.config.start_date,
                "end_date": self.config.end_date
            },
            "metrics": self.metrics.to_dict(),
            "trade_count": len(self.trades),
            "equity_curve_length": len(self.equity_curve)
        }


class BacktestingEngine:
    """Event-driven backtesting engine that simulates trading using trained neural network models."""
    
    def __init__(self, config: BacktestConfig):
        """Initialize backtesting engine.
        
        Args:
            config: Backtesting configuration
        """
        self.config = config
        
        # Initialize components
        self.data_manager = DataManager()
        self.position_manager = PositionManager(
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage
        )
        self.performance_tracker = PerformanceTracker()
        
        # Initialize decision orchestrator
        self.orchestrator = DecisionOrchestrator(
            strategy_config_path=config.strategy_config_path,
            model_path=config.model_path,
            mode="backtest"
        )
        
        self.strategy_name = self.orchestrator.strategy_name
        
    def run(self) -> BacktestResults:
        """Execute the backtest simulation.
        
        Returns:
            Comprehensive results including trades, metrics, and analysis
        """
        start_time = pd.Timestamp.now()
        execution_start = time.time()
        
        if self.config.verbose:
            print(f"🚀 Starting backtest: {self.strategy_name}")
            print(f"📊 Symbol: {self.config.symbol} | Timeframe: {self.config.timeframe}")
            print(f"📅 Period: {self.config.start_date} to {self.config.end_date}")
            print(f"💰 Initial Capital: ${self.config.initial_capital:,.2f}")
            print("=" * 60)
        
        # Load historical data
        if self.config.verbose:
            print(f"📈 Loading data for {self.config.symbol} {self.config.timeframe}...")
        
        data = self._load_historical_data()
        
        if data.empty:
            raise ValueError(f"No data loaded for {self.config.symbol} {self.config.timeframe}")
        
        if self.config.verbose:
            print(f"✅ Loaded {len(data):,} bars from {data.index[0]} to {data.index[-1]}")
            print(f"🔧 Running simulation...")
        
        # Initialize tracking
        trades_executed = 0
        last_progress_update = 0
        
        # Main simulation loop
        for idx in range(len(data)):
            current_bar = data.iloc[idx]
            current_timestamp = current_bar.name
            current_price = current_bar['close']
            
            # Prepare historical data up to current point
            historical_data = data.iloc[:idx+1]
            
            # Portfolio state for decision making
            portfolio_state = {
                "total_value": self.position_manager.get_portfolio_value(current_price),
                "available_capital": self.position_manager.available_capital
            }
            
            # Generate trading decision using orchestrator
            try:
                decision = self.orchestrator.make_decision(
                    symbol=self.config.symbol,
                    timeframe=self.config.timeframe,
                    current_bar=current_bar,
                    historical_data=historical_data,
                    portfolio_state=portfolio_state
                )
            except Exception as e:
                if self.config.verbose:
                    print(f"⚠️  Decision error at {current_timestamp}: {e}")
                # Create a HOLD decision if error occurs
                from ..decision.base import TradingDecision, Position
                decision = TradingDecision(
                    signal=Signal.HOLD,
                    confidence=0.0,
                    timestamp=current_timestamp,
                    reasoning={"error": str(e)},
                    current_position=Position.FLAT
                )
            
            # Execute decision if action required
            if decision.signal != Signal.HOLD:
                trade = self.position_manager.execute_trade(
                    signal=decision.signal,
                    price=current_price,
                    timestamp=current_timestamp,
                    symbol=self.config.symbol,
                    decision_metadata={
                        "confidence": decision.confidence,
                        "reasoning": decision.reasoning
                    }
                )
                
                if trade:
                    trades_executed += 1
                    if self.config.verbose:
                        action = "🟢 BUY " if decision.signal == Signal.BUY else "🔴 SELL"
                        print(f"{current_timestamp.strftime('%Y-%m-%d %H:%M')} | {action} @ ${current_price:.2f} "
                              f"| Confidence: {decision.confidence:.2f} | Trade #{trades_executed}")
            
            # Update position with current market price
            self.position_manager.update_position(current_price, current_timestamp)
            
            # Track performance metrics
            portfolio_value = self.position_manager.get_portfolio_value(current_price)
            position_status = self.position_manager.current_position_status
            
            self.performance_tracker.update(
                timestamp=current_timestamp,
                price=current_price,
                portfolio_value=portfolio_value,
                position=position_status
            )
            
            # Progress update
            if self.config.verbose and idx > 0:
                progress = (idx / len(data)) * 100
                if progress - last_progress_update >= 10:  # Update every 10%
                    print(f"⏳ Progress: {progress:.0f}% | Portfolio: ${portfolio_value:,.2f} | Trades: {trades_executed}")
                    last_progress_update = progress
        
        # Generate final results
        execution_time = time.time() - execution_start
        end_time = pd.Timestamp.now()
        
        if self.config.verbose:
            print("=" * 60)
            print("✅ Backtest completed!")
        
        results = self._generate_results(start_time, end_time, execution_time)
        
        if self.config.verbose:
            self._print_summary(results)
        
        return results
    
    def _load_historical_data(self) -> pd.DataFrame:
        """Load historical data for backtesting.
        
        Returns:
            DataFrame with OHLCV data
        """
        # Load data using the data manager
        data = self.data_manager.load_data(
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            mode="full"
        )
        
        # Filter by date range if specified
        if self.config.start_date:
            start_date = pd.to_datetime(self.config.start_date)
            data = data[data.index >= start_date]
        
        if self.config.end_date:
            end_date = pd.to_datetime(self.config.end_date)
            data = data[data.index <= end_date]
        
        return data
    
    def _generate_results(self, 
                         start_time: pd.Timestamp, 
                         end_time: pd.Timestamp,
                         execution_time: float) -> BacktestResults:
        """Compile comprehensive backtest results.
        
        Args:
            start_time: Backtest start time
            end_time: Backtest end time
            execution_time: Execution time in seconds
            
        Returns:
            BacktestResults object
        """
        trades = self.position_manager.get_trade_history()
        equity_curve = self.performance_tracker.get_equity_curve()
        
        # Calculate performance metrics
        start_date = pd.to_datetime(self.config.start_date) if self.config.start_date else None
        end_date = pd.to_datetime(self.config.end_date) if self.config.end_date else None
        
        metrics = self.performance_tracker.calculate_metrics(
            trades=trades,
            initial_capital=self.config.initial_capital,
            start_date=start_date,
            end_date=end_date
        )
        
        return BacktestResults(
            strategy_name=self.strategy_name,
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            config=self.config,
            trades=trades,
            metrics=metrics,
            equity_curve=equity_curve,
            start_time=start_time,
            end_time=end_time,
            execution_time_seconds=execution_time
        )
    
    def _print_summary(self, results: BacktestResults):
        """Print backtest summary.
        
        Args:
            results: Backtest results
        """
        print(f"\n📊 BACKTEST RESULTS - {results.strategy_name}")
        print("=" * 60)
        
        # Performance metrics
        metrics = results.metrics
        print(f"💰 Performance Metrics:")
        print(f"   Total Return: ${metrics.total_return:,.2f} ({metrics.total_return_pct:.2f}%)")
        print(f"   Annualized Return: {metrics.annualized_return:.2f}%")
        print(f"   Sharpe Ratio: {metrics.sharpe_ratio:.3f}")
        print(f"   Max Drawdown: ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct:.2f}%)")
        print(f"   Volatility: {metrics.volatility:.2f}%")
        
        print(f"\n📈 Trade Statistics:")
        print(f"   Total Trades: {metrics.total_trades}")
        print(f"   Win Rate: {metrics.win_rate:.1f}% ({metrics.winning_trades}/{metrics.total_trades})")
        print(f"   Profit Factor: {metrics.profit_factor:.2f}")
        print(f"   Avg Win: ${metrics.avg_win:.2f} | Avg Loss: ${metrics.avg_loss:.2f}")
        print(f"   Largest Win: ${metrics.largest_win:.2f} | Largest Loss: ${metrics.largest_loss:.2f}")
        
        print(f"\n⏱️  Execution:")
        print(f"   Execution Time: {results.execution_time_seconds:.2f} seconds")
        print(f"   Data Points: {len(results.equity_curve):,}")
        
        # Final portfolio value
        final_value = results.equity_curve['portfolio_value'].iloc[-1] if len(results.equity_curve) > 0 else self.config.initial_capital
        print(f"\n🎯 Final Portfolio Value: ${final_value:,.2f}")
    
    def reset(self):
        """Reset the backtesting engine for a new run."""
        self.position_manager.reset()
        self.performance_tracker.reset()
        self.orchestrator.reset_state()
"""Backtesting engine for strategy evaluation."""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import pandas as pd
from pathlib import Path
import time

from .position_manager import PositionManager, Trade
from .performance import PerformanceTracker, PerformanceMetrics
from .model_loader import ModelLoader
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
    data_mode: str = "local"  # Data loading mode
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
        
        # Initialize decision orchestrator (lazy import to avoid circular dependency)
        from ..decision.orchestrator import DecisionOrchestrator
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
            print(f"🔍 DEBUG: Data range check - Start: {self.config.start_date}, End: {self.config.end_date}")
            print(f"🔍 DEBUG: Actual data range - Start: {data.index[0]}, End: {data.index[-1]}")
            print(f"🔍 DEBUG: Data length: {len(data)} bars")
        
        # Initialize tracking
        trades_executed = 0
        last_progress_update = 0
        
        # DEBUG: Track signal statistics
        signal_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
        non_hold_signals = []
        trade_attempts = []
        
        # Main simulation loop with progress tracking
        last_processed_timestamp = None
        repeated_timestamp_count = 0
        
        for idx in range(len(data)):
            current_bar = data.iloc[idx]
            current_timestamp = current_bar.name
            current_price = current_bar['close']
            
            # Debug: Check for infinite loops on the same timestamp
            if current_timestamp == last_processed_timestamp:
                repeated_timestamp_count += 1
                if repeated_timestamp_count > 5:
                    print(f"🚨 INFINITE LOOP DETECTED: Processing {current_timestamp} repeatedly ({repeated_timestamp_count} times)")
                    print(f"   Breaking to prevent infinite loop")
                    break
            else:
                repeated_timestamp_count = 0
                last_processed_timestamp = current_timestamp
            
            # Safety check: ensure we don't process beyond the configured end date
            if self.config.end_date:
                end_date = pd.to_datetime(self.config.end_date)
                if current_timestamp.tz is not None and end_date.tz is None:
                    end_date = end_date.tz_localize('UTC')
                elif current_timestamp.tz is None and end_date.tz is not None:
                    current_timestamp = current_timestamp.tz_localize('UTC')
                    
                if current_timestamp > end_date:
                    if self.config.verbose:
                        print(f"🛑 Breaking loop: {current_timestamp} exceeds end date {end_date}")
                    break
            
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
            
            # DEBUG: Track all signals
            signal_counts[decision.signal.value] += 1
            
            # Track decision for analysis (even HOLD decisions)
            if self.config.verbose and idx % max(1, len(data) // 10) == 0:  # Log every 10% of progress
                progress = (idx / len(data)) * 100
                signal_name = decision.signal.value
                print(f"⏳ {progress:.0f}% | {current_timestamp.strftime('%Y-%m-%d')} | Signal: {signal_name} | Confidence: {decision.confidence:.3f}")
            
            # Execute decision if action required
            if decision.signal != Signal.HOLD:
                # DEBUG: Log every non-HOLD signal
                non_hold_signals.append({
                    "timestamp": current_timestamp,
                    "signal": decision.signal.value,
                    "confidence": decision.confidence,
                    "price": current_price
                })
                
                if self.config.verbose:
                    print(f"🎯 NON-HOLD SIGNAL: {decision.signal.value} at {current_timestamp} "
                          f"| Confidence: {decision.confidence:.4f} | Price: ${current_price:.2f}")
                
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
                
                # DEBUG: Log trade execution result
                trade_attempts.append({
                    "timestamp": current_timestamp,
                    "signal": decision.signal.value,
                    "confidence": decision.confidence,
                    "price": current_price,
                    "trade_executed": trade is not None,
                    "trade_details": trade.__dict__ if trade else None
                })
                
                if trade:
                    trades_executed += 1
                    # Update the decision engine's position state
                    self.orchestrator.decision_engine.update_position(decision.signal, current_timestamp)
                    if self.config.verbose:
                        action = "🟢 BUY " if decision.signal == Signal.BUY else "🔴 SELL"
                        print(f"✅ ORDER EXECUTED: {current_timestamp.strftime('%Y-%m-%d %H:%M')} | {action} @ ${current_price:.2f} "
                              f"| Confidence: {decision.confidence:.2f} | Order #{trades_executed}")
                else:
                    if self.config.verbose:
                        print(f"❌ ORDER FAILED: {decision.signal.value} signal not executed at {current_timestamp}")
            
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
                    print(f"⏳ Progress: {progress:.0f}% | Portfolio: ${portfolio_value:,.2f} | Orders: {trades_executed}")
                    last_progress_update = progress
        
        # Force-close any open position at the end of the backtest
        # This prevents unrealized losses from skewing performance metrics
        final_bar = data.iloc[-1]
        final_price = final_bar['close']
        final_timestamp = final_bar.name if hasattr(final_bar.name, 'strftime') else pd.Timestamp(final_bar.name)
        
        forced_trade = self.position_manager.force_close_position(
            price=final_price,
            timestamp=final_timestamp,
            symbol=self.config.symbol,
            reason="End of backtest period"
        )
        
        if forced_trade:
            trades_executed += 1  # Count the forced closure
            if self.config.verbose:
                print(f"\n🔒 FORCED POSITION CLOSURE:")
                print(f"   Closed open position at end of backtest")
                print(f"   Entry: ${forced_trade.entry_price:.2f} @ {forced_trade.entry_time}")
                print(f"   Exit: ${forced_trade.exit_price:.2f} @ {forced_trade.exit_time}")
                print(f"   P&L: ${forced_trade.net_pnl:.2f}")
                print(f"   This trade is included in performance calculations")
        
        # Generate final results
        execution_time = time.time() - execution_start
        end_time = pd.Timestamp.now()
        
        if self.config.verbose:
            print("=" * 60)
            print("✅ Backtest completed!")
            
            # Summary of orders vs trades for clarity
            completed_trades = len(self.position_manager.get_trade_history())
            print(f"\n📋 EXECUTION SUMMARY:")
            print(f"   Orders executed: {trades_executed} (individual BUY/SELL operations)")
            print(f"   Trades completed: {completed_trades} (round-trip BUY→SELL pairs)")
            
            # DEBUG: Print detailed signal analysis
            print(f"\n🔍 SIGNAL ANALYSIS:")
            print(f"   Total bars processed: {len(data):,}")
            print(f"   HOLD signals: {signal_counts['HOLD']:,}")
            print(f"   BUY signals: {signal_counts['BUY']:,}")
            print(f"   SELL signals: {signal_counts['SELL']:,}")
            print(f"   Non-HOLD signals: {len(non_hold_signals):,}")
            print(f"   Order attempts: {len(trade_attempts):,}")
            print(f"   Successful orders: {trades_executed}")
            
            if non_hold_signals:
                print(f"\n📊 FIRST 5 NON-HOLD SIGNALS:")
                for i, signal in enumerate(non_hold_signals[:5]):
                    print(f"   {i+1}. {signal['timestamp']} | {signal['signal']} | "
                          f"Confidence: {signal['confidence']:.4f} | Price: ${signal['price']:.2f}")
            
            if trade_attempts:
                print(f"\n💼 ORDER EXECUTION ANALYSIS:")
                successful = sum(1 for t in trade_attempts if t['trade_executed'])
                failed = len(trade_attempts) - successful
                print(f"   Successful: {successful}")
                print(f"   Failed: {failed}")
                
                if failed > 0:
                    print(f"\n❌ FAILED ORDER ATTEMPTS:")
                    for i, attempt in enumerate([t for t in trade_attempts if not t['trade_executed']][:5]):
                        print(f"   {i+1}. {attempt['timestamp']} | {attempt['signal']} | "
                              f"Confidence: {attempt['confidence']:.4f} | Price: ${attempt['price']:.2f}")
        
        results = self._generate_results(start_time, end_time, execution_time)
        
        if self.config.verbose:
            self._print_summary(results)
        
        return results
    
    def _load_historical_data(self) -> pd.DataFrame:
        """Load historical data for backtesting.
        
        Returns:
            DataFrame with OHLCV data
        """
        # Load data using the data manager with specified mode
        data = self.data_manager.load_data(
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            mode=self.config.data_mode
        )
        
        # Filter by date range if specified
        if self.config.start_date:
            start_date = pd.to_datetime(self.config.start_date)
            # Make timezone-aware if needed to match data index
            if data.index.tz is not None and start_date.tz is None:
                start_date = start_date.tz_localize('UTC')
            data = data[data.index >= start_date]
        
        if self.config.end_date:
            end_date = pd.to_datetime(self.config.end_date)
            # Make timezone-aware if needed to match data index
            if data.index.tz is not None and end_date.tz is None:
                end_date = end_date.tz_localize('UTC')
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
        
        # Check if any trades were executed
        metrics = results.metrics
        if metrics.total_trades == 0:
            print("⚠️  NO TRADES EXECUTED")
            print("\n🔍 Analysis:")
            print("   • No trading signals were generated")
            print("   • Possible causes:")
            print("     - Model may need retraining with different parameters")
            print("     - Confidence thresholds may be too high")
            print("     - Market conditions don't match training period")
            print("     - Fuzzy membership functions may need adjustment")
            
            # Show decision statistics if available
            decision_stats = getattr(self.orchestrator, 'decision_history', [])
            if decision_stats:
                hold_count = sum(1 for d in decision_stats if d.signal.value == 'HOLD')
                buy_signals = sum(1 for d in decision_stats if d.signal.value == 'BUY')
                sell_signals = sum(1 for d in decision_stats if d.signal.value == 'SELL')
                
                print(f"\n📈 Signal Distribution:")
                print(f"   HOLD signals: {hold_count}")
                print(f"   BUY signals: {buy_signals}")
                print(f"   SELL signals: {sell_signals}")
                
                if len(decision_stats) > 0:
                    avg_confidence = sum(d.confidence for d in decision_stats) / len(decision_stats)
                    print(f"   Average confidence: {avg_confidence:.3f}")
            
            print(f"\n💡 Recommendations:")
            print("   • Review model training performance and validation accuracy")
            print("   • Consider adjusting confidence thresholds in strategy config")
            print("   • Verify fuzzy membership function parameters")
            print("   • Try different training periods or market conditions")
            
            final_value = results.equity_curve['portfolio_value'].iloc[-1] if len(results.equity_curve) > 0 else self.config.initial_capital
            print(f"\n🎯 Portfolio Value: ${final_value:,.2f} (unchanged)")
            return
        
        # Performance metrics (only show if trades were made)
        print(f"💰 Performance Metrics:")
        print(f"   Total Return: ${metrics.total_return:,.2f} ({metrics.total_return_pct*100:.2f}%)")
        print(f"   Annualized Return: {metrics.annualized_return*100:.2f}%")
        print(f"   Sharpe Ratio: {metrics.sharpe_ratio:.3f}")
        print(f"   Max Drawdown: ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct*100:.2f}%)")
        print(f"   Volatility: {metrics.volatility*100:.2f}%")
        
        print(f"\n📈 Trade Statistics:")
        print(f"   Total Trades: {metrics.total_trades}")
        print(f"   Win Rate: {metrics.win_rate*100:.1f}% ({metrics.winning_trades}/{metrics.total_trades})")
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
"""Backtesting engine for strategy evaluation."""

import time
from dataclasses import dataclass
from typing import Any, Optional, cast

import pandas as pd

from .. import get_logger
from ..data.data_manager import DataManager
from ..decision.base import Signal
from .performance import PerformanceMetrics, PerformanceTracker
from .position_manager import PositionManager, Trade

logger = get_logger(__name__)


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
    trades: list[Trade]
    metrics: PerformanceMetrics
    equity_curve: pd.DataFrame
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    execution_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
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
                "end_date": self.config.end_date,
            },
            "metrics": self.metrics.to_dict(),
            "trade_count": len(self.trades),
            "equity_curve_length": len(self.equity_curve),
        }


class BacktestingEngine:
    """Event-driven backtesting engine that simulates trading using trained neural network models."""

    def __init__(self, config: BacktestConfig):
        """Initialize backtesting engine.

        Args:
            config: Backtesting configuration
        """
        self.config = config
        self.progress_callback = (
            None  # Can be set by API service for real progress tracking
        )

        # Initialize components
        self.data_manager = DataManager()
        self.position_manager = PositionManager(
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage,
        )
        self.performance_tracker = PerformanceTracker()

        # Initialize decision orchestrator (lazy import to avoid circular dependency)
        from ..decision.orchestrator import DecisionOrchestrator

        self.orchestrator = DecisionOrchestrator(
            strategy_config_path=config.strategy_config_path,
            model_path=config.model_path,
            mode="backtest",
        )

        self.strategy_name = self.orchestrator.strategy_name

    def run(self) -> BacktestResults:
        """Execute the backtest simulation.

        Returns:
            Comprehensive results including trades, metrics, and analysis
        """
        start_time = pd.Timestamp.now()
        execution_start = time.time()

        logger.info(f"🚀 Starting backtest: {self.strategy_name}")
        logger.info(
            f"📊 Symbol: {self.config.symbol} | Timeframe: {self.config.timeframe}"
        )
        logger.info(f"📅 Period: {self.config.start_date} to {self.config.end_date}")
        logger.info(f"💰 Initial Capital: ${self.config.initial_capital:,.2f}")

        if self.config.verbose:
            print(f"🚀 Starting backtest: {self.strategy_name}")
            print(
                f"📊 Symbol: {self.config.symbol} | Timeframe: {self.config.timeframe}"
            )
            print(f"📅 Period: {self.config.start_date} to {self.config.end_date}")
            print(f"💰 Initial Capital: ${self.config.initial_capital:,.2f}")
            print("=" * 60)

        # Load historical data
        if self.config.verbose:
            print(
                f"📈 Loading data for {self.config.symbol} {self.config.timeframe}..."
            )

        data = self._load_historical_data()

        if data.empty:
            raise ValueError(
                f"No data loaded for {self.config.symbol} {self.config.timeframe}"
            )

        if self.config.verbose:
            print(
                f"✅ Loaded {len(data):,} bars from {data.index[0]} to {data.index[-1]}"
            )
            print("🚀 Pre-computing features for backtesting performance...")

        # PERFORMANCE OPTIMIZATION: Pre-compute all features for fast backtesting
        logger.info("🚀 Pre-computing indicators and fuzzy memberships...")
        self.orchestrator.prepare_feature_cache(data)
        logger.info("✅ Feature cache ready - backtesting should be much faster!")

        if self.config.verbose:
            print("✅ Feature cache prepared - backtesting optimized!")
            print("🔧 Running simulation...")
            print(
                f"🔍 DEBUG: Data range check - Start: {self.config.start_date}, End: {self.config.end_date}"
            )
            print(
                f"🔍 DEBUG: Actual data range - Start: {data.index[0]}, End: {data.index[-1]}"
            )
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

        logger.info(
            f"🚀 Starting main simulation loop with {len(data)} bars from {data.index[0]} to {data.index[-1]}"
        )
        logger.info(
            f"📊 Processing {len(data) - 50} bars (skipping first 50 for indicator warm-up)"
        )

        # Initial progress callback to set total bars (only processable bars, not warm-up bars)
        processable_bars = len(data) - 50  # Skip first 50 bars for indicator warm-up
        if self.progress_callback:
            try:
                self.progress_callback(
                    0,
                    processable_bars,
                    {
                        "portfolio_value": self.config.initial_capital,
                        "trades_executed": 0,
                    },
                )
            except Exception as e:
                logger.warning(f"Initial progress callback failed: {e}")

        # PERFORMANCE OPTIMIZATION: Start from bar 50 to align with FeatureCache
        # The first 50 bars are skipped because indicators need sufficient lookback data
        start_idx = 50

        for idx in range(start_idx, len(data)):
            current_bar = data.iloc[idx]
            current_timestamp = cast(pd.Timestamp, current_bar.name)
            current_price = current_bar["close"]

            # DEBUG: Log first few bars to ensure loop is running
            if idx < start_idx + 5:
                # logger.info(f"📊 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Processing bar {idx+1}/{len(data)}, Price: ${current_price:.2f}")  # Commented for performance
                pass

            # Debug: Check for infinite loops on the same timestamp
            if current_timestamp == last_processed_timestamp:
                repeated_timestamp_count += 1
                if repeated_timestamp_count > 5:
                    print(
                        f"🚨 INFINITE LOOP DETECTED: Processing {current_timestamp} repeatedly ({repeated_timestamp_count} times)"
                    )
                    print("   Breaking to prevent infinite loop")
                    break
            else:
                repeated_timestamp_count = 0
                last_processed_timestamp = current_timestamp

            # Safety check: ensure we don't process beyond the configured end date
            if self.config.end_date:
                end_date = pd.to_datetime(self.config.end_date)
                if current_timestamp.tz is not None and end_date.tz is None:
                    end_date = end_date.tz_localize("UTC")
                elif current_timestamp.tz is None and end_date.tz is not None:
                    current_timestamp = current_timestamp.tz_localize("UTC")

                if current_timestamp > end_date:
                    if self.config.verbose:
                        print(
                            f"🛑 Breaking loop: {current_timestamp} exceeds end date {end_date}"
                        )
                    break

            # Prepare historical data up to current point
            historical_data = data.iloc[: idx + 1]

            # Portfolio state for decision making
            portfolio_state = {
                "total_value": self.position_manager.get_portfolio_value(current_price),
                "available_capital": self.position_manager.available_capital,
            }

            # Generate trading decision using orchestrator
            logger.debug(
                f"🎯 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Calling orchestrator.make_decision for bar {idx+1}/{len(data)}"
            )

            try:
                decision = self.orchestrator.make_decision(
                    symbol=self.config.symbol,
                    timeframe=self.config.timeframe,
                    current_bar=current_bar,
                    historical_data=historical_data,
                    portfolio_state=portfolio_state,
                )
                logger.debug(
                    f"✅ [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Orchestrator returned: {decision.signal.value} (confidence: {decision.confidence:.4f})"
                )
            except Exception as e:
                # Check if this is a warm-up period error (normal and expected)
                # NOTE: We now start from bar 50, so warm-up errors should be rare
                is_warmup_error = (
                    "No fuzzy membership features found" in str(e)
                    or "likely warm-up period" in str(e)
                    or idx
                    < start_idx
                    + 10  # First 10 bars after start_idx might still have issues
                )

                if is_warmup_error:
                    # Log warm-up errors at DEBUG level - they're expected
                    logger.debug(
                        f"🔄 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Warm-up period - insufficient data: {e}"
                    )
                else:
                    # Log real errors at ERROR level
                    logger.error(
                        f"🚨 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Decision error: {e}"
                    )
                    logger.error(f"🚨 Error details: {type(e).__name__}: {str(e)}")

                    # Also print to console for immediate visibility (real errors only)
                    print(f"🚨 DECISION ERROR at {current_timestamp}: {e}")

                # Create a HOLD decision if error occurs
                from ..decision.base import Position, TradingDecision

                decision = TradingDecision(
                    signal=Signal.HOLD,
                    confidence=0.0,
                    timestamp=current_timestamp,
                    reasoning={"error": str(e), "warmup": is_warmup_error},
                    current_position=Position.FLAT,
                )

                if is_warmup_error:
                    logger.debug(
                        f"🔄 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Using HOLD during warm-up period"
                    )
                else:
                    logger.info(
                        f"🛑 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Created fallback HOLD decision due to error"
                    )

            # DEBUG: Track all signals
            signal_counts[decision.signal.value] += 1

            # Log signal distribution every 1000 bars for debugging
            if idx > start_idx and (idx - start_idx) % 1000 == 0:
                # logger.info(f"📊 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Signal counts so far: BUY={signal_counts['BUY']}, HOLD={signal_counts['HOLD']}, SELL={signal_counts['SELL']}")  # Commented for performance
                pass

            # Track decision for analysis (even HOLD decisions)
            if (
                self.config.verbose
                and (idx - start_idx) % max(1, (len(data) - start_idx) // 10) == 0
            ):  # Log every 10% of progress
                progress = ((idx - start_idx) / (len(data) - start_idx)) * 100
                signal_name = decision.signal.value
                print(
                    f"⏳ {progress:.0f}% | {current_timestamp.strftime('%Y-%m-%d')} | Signal: {signal_name} | Confidence: {decision.confidence:.3f}"
                )

            # Execute decision if action required
            if decision.signal != Signal.HOLD:
                logger.debug(
                    f"🎯 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Non-HOLD signal detected: {decision.signal.value}"
                )

                # CRITICAL DEBUG: Track position states before trade
                pm_position = self.position_manager.current_position_status
                de_position = self.orchestrator.decision_engine.current_position

                logger.debug(
                    f"🔍 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Position states - PositionManager: {pm_position.value}, DecisionEngine: {de_position.value}"
                )

                # CRITICAL: Validate signal logic
                if decision.signal == Signal.SELL and pm_position.value == "FLAT":
                    logger.error(
                        f"🚨 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] IMPOSSIBLE: SELL signal when PositionManager shows FLAT!"
                    )
                    logger.error(f"🚨 Signal source: {decision.reasoning}")
                if decision.signal == Signal.BUY and pm_position.value == "LONG":
                    logger.error(
                        f"🚨 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] IMPOSSIBLE: BUY signal when PositionManager shows LONG!"
                    )
                # DEBUG: Log every non-HOLD signal
                non_hold_signals.append(
                    {
                        "timestamp": current_timestamp,
                        "signal": decision.signal.value,
                        "confidence": decision.confidence,
                        "price": current_price,
                    }
                )

                if self.config.verbose:
                    print(
                        f"🎯 NON-HOLD SIGNAL: {decision.signal.value} at {current_timestamp} "
                        f"| Confidence: {decision.confidence:.4f} | Price: ${current_price:.2f}"
                    )

                trade = self.position_manager.execute_trade(
                    signal=decision.signal,
                    price=current_price,
                    timestamp=current_timestamp,
                    symbol=self.config.symbol,
                    decision_metadata={
                        "confidence": decision.confidence,
                        "reasoning": decision.reasoning,
                    },
                )

                # DEBUG: Log trade execution result
                trade_attempts.append(
                    {
                        "timestamp": current_timestamp,
                        "signal": decision.signal.value,
                        "confidence": decision.confidence,
                        "price": current_price,
                        "trade_executed": trade is not None,
                        "trade_details": trade.__dict__ if trade else None,
                    }
                )

                if trade:
                    trades_executed += 1

                    # CRITICAL DEBUG: Verify position states after trade
                    pm_position_after = self.position_manager.current_position_status

                    # Update the decision engine's position state
                    self.orchestrator.decision_engine.update_position(
                        decision.signal, current_timestamp
                    )

                    de_position_after = (
                        self.orchestrator.decision_engine.current_position
                    )

                    # DEBUG: Log detailed trade execution with position tracking
                    portfolio_after = self.position_manager.get_portfolio_value(
                        current_price
                    )
                    position_info = self.position_manager.get_position_summary()

                    action = "BUY" if decision.signal == Signal.BUY else "SELL"
                    logger.debug(
                        f"ORDER EXECUTED: {current_timestamp.strftime('%Y-%m-%d %H:%M')} | {action} @ ${current_price:.2f} "
                        f"| Confidence: {decision.confidence:.2f} | Order #{trades_executed}"
                    )

                    # CRITICAL: Log position synchronization
                    logger.debug(
                        f"🔄 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Position sync after trade - PM: {pm_position_after.value}, DE: {de_position_after.value}"
                    )

                    # FIXED: Only log DESYNC when positions are actually different (compare values)
                    if pm_position_after.value != de_position_after.value:
                        logger.error(
                            f"🚨 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] POSITION DESYNC! PositionManager: {pm_position_after.value} vs DecisionEngine: {de_position_after.value}"
                        )
                    else:
                        logger.debug(
                            f"✅ [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Positions synchronized: {pm_position_after.value}"
                        )

                    # CRITICAL: Portfolio value tracking
                    portfolio_change = portfolio_after - self.config.initial_capital
                    portfolio_pct = (
                        portfolio_change / self.config.initial_capital
                    ) * 100

                    logger.debug(
                        f"💰 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] Portfolio: ${portfolio_after:,.2f} | Change: ${portfolio_change:,.2f} ({portfolio_pct:+.2f}%) | Cash: ${position_info['capital']:,.2f}"
                    )

                    # Check for impossible portfolio states
                    if position_info["capital"] < 0:
                        logger.error(
                            f"🚨 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] IMPOSSIBLE: Negative cash ${position_info['capital']:,.2f}"
                        )
                    if portfolio_pct < -100:
                        logger.error(
                            f"🚨 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] IMPOSSIBLE: Portfolio loss > 100% ({portfolio_pct:.1f}%)"
                        )
                    if portfolio_after <= 0:
                        logger.error(
                            f"🚨 [{current_timestamp.strftime('%Y-%m-%d %H:%M')}] IMPOSSIBLE: Portfolio value ${portfolio_after:,.2f} <= 0"
                        )

                    if self.config.verbose:
                        action_emoji = (
                            "🟢 BUY " if decision.signal == Signal.BUY else "🔴 SELL"
                        )
                        print(
                            f"✅ ORDER EXECUTED: {current_timestamp.strftime('%Y-%m-%d %H:%M')} | {action_emoji} @ ${current_price:.2f} "
                            f"| Confidence: {decision.confidence:.2f} | Order #{trades_executed}"
                        )
                else:
                    if self.config.verbose:
                        print(
                            f"❌ ORDER FAILED: {decision.signal.value} signal not executed at {current_timestamp}"
                        )

            # Update position with current market price
            self.position_manager.update_position(current_price, current_timestamp)

            # Track performance metrics
            portfolio_value = self.position_manager.get_portfolio_value(current_price)
            position_status = self.position_manager.current_position_status

            # DEBUG: Log portfolio state every 1000 bars to track capital management
            if (idx - start_idx) % 1000 == 0 or self.config.verbose:
                position_summary = self.position_manager.get_position_summary()
                logger.debug(
                    f"Portfolio state [{idx}/{len(data)}]: Portfolio=${portfolio_value:,.2f}, "
                    f"Cash=${position_summary['capital']:,.2f}, Available=${position_summary['available_capital']:,.2f}, "
                    f"Position={position_status.value}"
                )

                # Check for impossible metrics early
                if portfolio_value < 0:
                    logger.error(
                        f"IMPOSSIBLE PORTFOLIO VALUE: ${portfolio_value:,.2f} detected at {current_timestamp}"
                    )
                if position_summary["capital"] < 0:
                    logger.error(
                        f"NEGATIVE CASH: ${position_summary['capital']:,.2f} detected at {current_timestamp}"
                    )

            self.performance_tracker.update(
                timestamp=current_timestamp,
                price=current_price,
                portfolio_value=portfolio_value,
                position=position_status,
            )

            # Progress update with REAL progress tracking
            if idx > start_idx:
                progress = ((idx - start_idx) / (len(data) - start_idx)) * 100
                if progress - last_progress_update >= 10:  # Update every 10%
                    total_trades = len(self.position_manager.get_trade_history())

                    # Log progress at info level
                    logger.info(
                        f"Progress: {progress:.0f}% | Portfolio: ${portfolio_value:,.2f} | "
                        f"Orders: {trades_executed} | Completed Trades: {total_trades}"
                    )

                    # Check for drawdown issues
                    if hasattr(self.performance_tracker, "get_current_drawdown"):
                        try:
                            current_dd = self.performance_tracker.get_current_drawdown()
                            if current_dd > 0.5:  # > 50% drawdown
                                logger.warning(
                                    f"High drawdown detected: {current_dd*100:.1f}%"
                                )
                        except Exception:
                            pass

                    # Additional sanity checks at progress milestones
                    if portfolio_value <= 0:
                        logger.error(
                            f"BANKRUPT: Portfolio value reached ${portfolio_value:,.2f} at {progress:.0f}% progress"
                        )
                        logger.warning(
                            "Should backtest terminate here? Current logic continues..."
                        )

                    # Verbose console output for user feedback
                    if self.config.verbose:
                        drawdown_info = ""
                        if hasattr(self.performance_tracker, "get_current_drawdown"):
                            try:
                                current_dd = (
                                    self.performance_tracker.get_current_drawdown()
                                )
                                if current_dd > 0.5:  # > 50% drawdown
                                    drawdown_info = (
                                        f" | 🚨 Drawdown: {current_dd*100:.1f}%"
                                    )
                            except Exception:
                                pass

                        print(
                            f"⏳ Progress: {progress:.0f}% | Portfolio: ${portfolio_value:,.2f} | "
                            f"Orders: {trades_executed} | Completed Trades: {total_trades}{drawdown_info}"
                        )

                    last_progress_update = progress

            # Call API progress callback with REAL data
            if (
                self.progress_callback and (idx - start_idx) % 100 == 0
            ):  # Update every 100 bars for API responsiveness
                try:
                    additional_data = {
                        "portfolio_value": portfolio_value,
                        "trades_executed": trades_executed,
                    }
                    # Progress callback expects current processed bars vs total processable bars
                    self.progress_callback(
                        idx - start_idx + 1, len(data) - start_idx, additional_data
                    )
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

        # Force-close any open position at the end of the backtest
        # This prevents unrealized losses from skewing performance metrics
        final_bar = data.iloc[-1]
        final_price = final_bar["close"]
        final_timestamp = cast(pd.Timestamp, (
            final_bar.name
            if hasattr(final_bar.name, "strftime")
            else pd.Timestamp(cast(str, final_bar.name))
        ))

        # CRITICAL DEBUG: Track force-close logic
        pm_final_position = self.position_manager.current_position_status
        logger.info(
            f"🔒 [{final_timestamp.strftime('%Y-%m-%d %H:%M')}] Force-close check - Position: {pm_final_position.value}"
        )

        if pm_final_position.value != "FLAT":
            logger.info(
                f"🔒 [{final_timestamp.strftime('%Y-%m-%d %H:%M')}] Force-closing {pm_final_position.value} position at ${final_price:.2f}"
            )

        forced_trade = self.position_manager.force_close_position(
            price=final_price,
            timestamp=final_timestamp,
            symbol=self.config.symbol,
            reason="End of backtest period",
        )

        if forced_trade:
            trades_executed += 1  # Count the forced closure
            if self.config.verbose:
                print("\n🔒 FORCED POSITION CLOSURE:")
                print("   Closed open position at end of backtest")
                print(
                    f"   Entry: ${forced_trade.entry_price:.2f} @ {forced_trade.entry_time}"
                )
                print(
                    f"   Exit: ${forced_trade.exit_price:.2f} @ {forced_trade.exit_time}"
                )
                print(f"   P&L: ${forced_trade.net_pnl:.2f}")
                print("   This trade is included in performance calculations")

        # Generate final results
        execution_time = time.time() - execution_start
        end_time = pd.Timestamp.now()

        if self.config.verbose:
            print("=" * 60)
            print("✅ Backtest completed!")

            # Summary of orders vs trades for clarity
            completed_trades = len(self.position_manager.get_trade_history())
            print("\n📋 EXECUTION SUMMARY:")
            print(
                f"   Orders executed: {trades_executed} (individual BUY/SELL operations)"
            )
            print(
                f"   Trades completed: {completed_trades} (round-trip BUY→SELL pairs)"
            )

            # DEBUG: Print detailed signal analysis
            print("\n🔍 SIGNAL ANALYSIS:")
            print(f"   Total bars in dataset: {len(data):,}")
            print(f"   Bars processed (after warm-up): {len(data) - 50:,}")
            print(f"   HOLD signals: {signal_counts['HOLD']:,}")
            print(f"   BUY signals: {signal_counts['BUY']:,}")
            print(f"   SELL signals: {signal_counts['SELL']:,}")
            print(f"   Non-HOLD signals: {len(non_hold_signals):,}")
            print(f"   Order attempts: {len(trade_attempts):,}")
            print(f"   Successful orders: {trades_executed}")

            if non_hold_signals:
                print("\n📊 FIRST 5 NON-HOLD SIGNALS:")
                for i, signal in enumerate(non_hold_signals[:5]):
                    print(
                        f"   {i+1}. {signal['timestamp']} | {signal['signal']} | "
                        f"Confidence: {signal['confidence']:.4f} | Price: ${signal['price']:.2f}"
                    )

            if trade_attempts:
                print("\n💼 ORDER EXECUTION ANALYSIS:")
                successful = sum(1 for t in trade_attempts if t["trade_executed"])
                failed = len(trade_attempts) - successful
                print(f"   Successful: {successful}")
                print(f"   Failed: {failed}")

                if failed > 0:
                    print("\n❌ FAILED ORDER ATTEMPTS:")
                    for i, attempt in enumerate(
                        [t for t in trade_attempts if not t["trade_executed"]][:5]
                    ):
                        print(
                            f"   {i+1}. {attempt['timestamp']} | {attempt['signal']} | "
                            f"Confidence: {attempt['confidence']:.4f} | Price: ${attempt['price']:.2f}"
                        )

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
            mode=self.config.data_mode,
        )

        # Filter by date range if specified
        if self.config.start_date:
            start_date = pd.to_datetime(self.config.start_date)
            # Make timezone-aware if needed to match data index
            if data.index.tz is not None and start_date.tz is None:
                start_date = start_date.tz_localize("UTC")
            data = data[data.index >= start_date]

        if self.config.end_date:
            end_date = pd.to_datetime(self.config.end_date)
            # Make timezone-aware if needed to match data index
            if data.index.tz is not None and end_date.tz is None:
                end_date = end_date.tz_localize("UTC")
            data = data[data.index <= end_date]

        return data

    def _generate_results(
        self, start_time: pd.Timestamp, end_time: pd.Timestamp, execution_time: float
    ) -> BacktestResults:
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
        start_date = (
            pd.to_datetime(self.config.start_date) if self.config.start_date else None
        )
        end_date = (
            pd.to_datetime(self.config.end_date) if self.config.end_date else None
        )

        metrics = self.performance_tracker.calculate_metrics(
            trades=trades,
            initial_capital=self.config.initial_capital,
            start_date=start_date,
            end_date=end_date,
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
            execution_time_seconds=execution_time,
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
            decision_stats = getattr(self.orchestrator, "decision_history", [])
            if decision_stats:
                hold_count = sum(1 for d in decision_stats if d.signal.value == "HOLD")
                buy_signals = sum(1 for d in decision_stats if d.signal.value == "BUY")
                sell_signals = sum(
                    1 for d in decision_stats if d.signal.value == "SELL"
                )

                print("\n📈 Signal Distribution:")
                print(f"   HOLD signals: {hold_count}")
                print(f"   BUY signals: {buy_signals}")
                print(f"   SELL signals: {sell_signals}")

                if len(decision_stats) > 0:
                    avg_confidence = sum(d.confidence for d in decision_stats) / len(
                        decision_stats
                    )
                    print(f"   Average confidence: {avg_confidence:.3f}")

            print("\n💡 Recommendations:")
            print("   • Review model training performance and validation accuracy")
            print("   • Consider adjusting confidence thresholds in strategy config")
            print("   • Verify fuzzy membership function parameters")
            print("   • Try different training periods or market conditions")

            final_value = (
                results.equity_curve["portfolio_value"].iloc[-1]
                if len(results.equity_curve) > 0
                else self.config.initial_capital
            )
            print(f"\n🎯 Portfolio Value: ${final_value:,.2f} (unchanged)")
            return

        # Performance metrics (only show if trades were made)
        print("💰 Performance Metrics:")
        print(
            f"   Total Return: ${metrics.total_return:,.2f} ({metrics.total_return_pct*100:.2f}%)"
        )
        print(f"   Annualized Return: {metrics.annualized_return*100:.2f}%")
        print(f"   Sharpe Ratio: {metrics.sharpe_ratio:.3f}")
        print(
            f"   Max Drawdown: ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct*100:.2f}%)"
        )
        print(f"   Volatility: {metrics.volatility*100:.2f}%")

        print("\n📈 Trade Statistics:")
        print(f"   Total Trades: {metrics.total_trades}")
        print(
            f"   Win Rate: {metrics.win_rate*100:.1f}% ({metrics.winning_trades}/{metrics.total_trades})"
        )
        print(f"   Profit Factor: {metrics.profit_factor:.2f}")
        print(f"   Avg Win: ${metrics.avg_win:.2f} | Avg Loss: ${metrics.avg_loss:.2f}")
        print(
            f"   Largest Win: ${metrics.largest_win:.2f} | Largest Loss: ${metrics.largest_loss:.2f}"
        )

        print("\n⏱️  Execution:")
        print(f"   Execution Time: {results.execution_time_seconds:.2f} seconds")
        print(f"   Data Points: {len(results.equity_curve):,}")

        # Final portfolio value
        final_value = (
            results.equity_curve["portfolio_value"].iloc[-1]
            if len(results.equity_curve) > 0
            else self.config.initial_capital
        )
        print(f"\n🎯 Final Portfolio Value: ${final_value:,.2f}")

    def reset(self):
        """Reset the backtesting engine for a new run."""
        self.position_manager.reset()
        self.performance_tracker.reset()
        self.orchestrator.reset_state()

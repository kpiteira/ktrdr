"""
Backtesting service for the KTRDR API.

This module provides the service layer for backtesting operations,
bridging the API endpoints with the core backtesting engine.
"""

import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import pandas as pd

from ktrdr import get_logger
from ktrdr.api.services.base import BaseService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import (
    OperationType,
    OperationMetadata,
    OperationProgress,
)
from ktrdr.backtesting.engine import BacktestingEngine
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.data.data_manager import DataManager
from ktrdr.errors import DataError, ValidationError
from ktrdr.decision.base import Signal

logger = get_logger(__name__)


class BacktestingService(BaseService):
    """Service for managing backtesting operations."""

    def __init__(self, operations_service: Optional[OperationsService] = None):
        """Initialize the backtesting service."""
        super().__init__()
        self.data_manager = DataManager()
        self.model_loader = ModelLoader()
        if operations_service is None:
            raise ValueError("OperationsService must be provided to BacktestingService")
        self.operations_service = operations_service

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the backtesting service.

        Returns:
            Dict[str, Any]: Health check information
        """
        active_operations, _, _ = await self.operations_service.list_operations(
            operation_type=OperationType.BACKTESTING, active_only=True
        )
        return {
            "service": "BacktestingService",
            "status": "ok",
            "active_backtests": len(active_operations),
            "data_manager_ready": self.data_manager is not None,
            "model_loader_ready": self.model_loader is not None,
        }

    async def start_backtest(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
    ) -> Dict[str, Any]:
        """
        Start a new backtest operation.

        Args:
            strategy_name: Name of the strategy to backtest
            symbol: Trading symbol
            timeframe: Timeframe for the backtest
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Initial capital amount

        Returns:
            Dict containing operation_id and initial status
        """
        # Create operation metadata
        metadata = OperationMetadata(
            symbol=symbol,
            timeframe=timeframe,
            start_date=pd.to_datetime(start_date).tz_localize("UTC"),
            end_date=pd.to_datetime(end_date).tz_localize("UTC"),
            parameters={
                "strategy_name": strategy_name,
                "initial_capital": initial_capital,
            },
        )

        # Create operation using operations service
        operation = await self.operations_service.create_operation(
            operation_type=OperationType.BACKTESTING, metadata=metadata
        )
        operation_id = operation.operation_id

        # Start backtest in background
        task = asyncio.create_task(
            self._run_backtest_async(
                operation_id,
                strategy_name,
                symbol,
                timeframe,
                start_date,
                end_date,
                initial_capital,
            )
        )

        # Register task with operations service for cancellation support
        await self.operations_service.start_operation(operation_id, task)

        return {
            "backtest_id": operation_id,
            "status": "starting",
            "message": f"Backtest {operation_id} started for {strategy_name}",
        }

    async def _run_backtest_async(
        self,
        operation_id: str,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float,
    ) -> None:
        """
        Run backtest asynchronously with data-driven progress tracking.
        """
        try:
            # Phase 1: Validation (5%)
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=5.0, current_step="Validating strategy configuration"
                ),
            )

            # Build strategy config path
            strategy_path = Path(f"strategies/{strategy_name}.yaml")
            if not strategy_path.exists():
                raise ValidationError(f"Strategy '{strategy_name}' not found")

            # Phase 2: Data loading preparation (10%)
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=10.0, current_step="Preparing data loading configuration"
                ),
            )

            # Create backtest configuration
            config = BacktestConfig(
                strategy_config_path=str(strategy_path),
                model_path=None,  # Let engine find latest model
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                commission=0.001,
                slippage=0.0005,
                data_mode="local",
                verbose=False,
            )

            # Estimate total bars for progress tracking
            total_bars = await self._estimate_total_bars(
                symbol, timeframe, start_date, end_date
            )

            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=15.0,
                    current_step=f"Loading {symbol} {timeframe} data",
                    items_total=total_bars,
                ),
            )

            # Create modified engine with progress callback
            engine = BacktestingEngine(config)

            # Run the backtest with progress tracking
            results = await self._run_backtest_with_progress(
                engine, operation_id, total_bars
            )

            # Results processing and completion (5%)
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=95.0, current_step="Processing backtest results"
                ),
            )

            # Convert results to dictionary format
            try:
                results_dict = results.to_dict()
                logger.info(
                    f"Successfully converted results to dict, keys: {results_dict.keys()}"
                )

                # Add trade details (like CLI does for verbose output)
                results_dict["trades"] = [
                    {
                        "trade_id": str(
                            trade.trade_id
                        ),  # Convert to string for Pydantic validation
                        "side": trade.side,
                        "entry_time": trade.entry_time.isoformat(),
                        "entry_price": trade.entry_price,
                        "exit_time": trade.exit_time.isoformat(),
                        "exit_price": trade.exit_price,
                        "quantity": trade.quantity,
                        "pnl": trade.net_pnl,
                        "pnl_percent": trade.return_pct,
                        "entry_reason": getattr(trade, "entry_reason", None),
                        "exit_reason": getattr(trade, "exit_reason", None),
                    }
                    for trade in results.trades
                ]
                logger.info(f"Added {len(results_dict['trades'])} trades to results")

                # Add equity curve data (like CLI does for detailed output)
                if (
                    hasattr(results, "equity_curve")
                    and results.equity_curve is not None
                ):
                    try:
                        # Convert equity curve to the format expected by the API
                        equity_df = results.equity_curve.reset_index()
                        logger.info(
                            f"Equity curve columns: {equity_df.columns.tolist()}"
                        )
                        logger.info(f"Equity curve index type: {type(equity_df.index)}")

                        # Handle different possible column names and index types
                        if "timestamp" in equity_df.columns:
                            timestamps = (
                                equity_df["timestamp"]
                                .dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                                .tolist()
                            )
                        elif hasattr(equity_df.index, "strftime"):
                            timestamps = equity_df.index.strftime(
                                "%Y-%m-%dT%H:%M:%S.%fZ"
                            ).tolist()
                        else:
                            # Fallback: convert to string
                            timestamps = [str(ts) for ts in equity_df.index]

                        # Get values column (try different possible names)
                        if "equity" in equity_df.columns:
                            values = equity_df["equity"].tolist()
                        elif "value" in equity_df.columns:
                            values = equity_df["value"].tolist()
                        elif "portfolio_value" in equity_df.columns:
                            values = equity_df["portfolio_value"].tolist()
                        else:
                            # Use first numeric column
                            numeric_cols = equity_df.select_dtypes(
                                include=["number"]
                            ).columns
                            values = (
                                equity_df[numeric_cols[0]].tolist()
                                if len(numeric_cols) > 0
                                else [0.0] * len(equity_df)
                            )

                        # Get drawdown column
                        if "drawdown" in equity_df.columns:
                            drawdowns = equity_df["drawdown"].tolist()
                        elif "max_drawdown" in equity_df.columns:
                            drawdowns = equity_df["max_drawdown"].tolist()
                        else:
                            drawdowns = [0.0] * len(equity_df)

                        results_dict["equity_curve"] = {
                            "timestamps": timestamps,
                            "values": values,
                            "drawdowns": drawdowns,
                        }
                        logger.info(
                            f"Added equity curve data with {len(results_dict['equity_curve']['timestamps'])} points"
                        )
                    except Exception as eq_e:
                        logger.error(
                            f"Failed to process equity curve: {eq_e}", exc_info=True
                        )
                        # Add empty equity curve to avoid 400 error
                        results_dict["equity_curve"] = {
                            "timestamps": [],
                            "values": [],
                            "drawdowns": [],
                        }
                else:
                    logger.warning("No equity curve data available in results")
                    results_dict["equity_curve"] = {
                        "timestamps": [],
                        "values": [],
                        "drawdowns": [],
                    }

            except Exception as e:
                logger.error(f"Failed to convert results to dict: {e}", exc_info=True)
                # Fallback to minimal results
                results_dict = {
                    "total_return": 0.0,
                    "total_trades": 0,
                    "initial_capital": initial_capital,
                    "final_value": initial_capital,
                    "trades": [],
                    "equity_curve": {"timestamps": [], "values": [], "drawdowns": []},
                }

            # Complete the operation with full results
            await self.operations_service.complete_operation(
                operation_id,
                result_summary=results_dict,  # Store full results for API access
            )

        except Exception as e:
            logger.error(f"Backtest {operation_id} failed: {str(e)}", exc_info=True)
            await self.operations_service.fail_operation(operation_id, str(e))

    async def _estimate_total_bars(
        self, symbol: str, timeframe: str, start_date: str, end_date: str
    ) -> int:
        """
        Estimate total bars for progress tracking.

        This is a rough estimate based on timeframe and date range.
        The actual data loading will provide the real count.
        """
        try:
            start = pd.to_datetime(start_date).tz_localize("UTC")
            end = pd.to_datetime(end_date).tz_localize("UTC")
            total_days = (end - start).days

            # Rough estimates based on timeframe (assumes market hours)
            if timeframe == "1m":
                return total_days * 390  # ~6.5 market hours * 60 minutes
            elif timeframe == "5m":
                return total_days * 78  # 390 / 5
            elif timeframe == "15m":
                return total_days * 26  # 390 / 15
            elif timeframe == "1h":
                return total_days * 7  # ~6.5 market hours
            elif timeframe == "4h":
                return total_days * 2  # 2 bars per day
            elif timeframe == "1d":
                return total_days  # 1 bar per day
            else:
                # Default fallback
                return max(100, total_days * 10)
        except Exception:
            # Fallback estimate
            return 1000

    def _load_data_with_warmup(self, engine):
        """
        Load historical data with warm-up period for indicators.

        This method loads extra data before the backtest start date to ensure
        indicators have sufficient historical data for accurate calculations.
        """
        # Calculate warm-up period needed (conservative estimate)
        # Most indicators need at most 50-100 bars for warm-up
        warmup_bars = 100

        # Convert warm-up bars to time period based on timeframe
        timeframe = engine.config.timeframe
        if timeframe == "1m":
            warmup_days = warmup_bars / 390  # ~390 minutes per trading day
        elif timeframe == "5m":
            warmup_days = warmup_bars / 78  # ~78 5-min bars per trading day
        elif timeframe == "15m":
            warmup_days = warmup_bars / 26  # ~26 15-min bars per trading day
        elif timeframe == "1h":
            warmup_days = warmup_bars / 7  # ~7 hours per trading day
        elif timeframe == "4h":
            warmup_days = warmup_bars / 2  # ~2 4-hour bars per trading day
        elif timeframe == "1d":
            warmup_days = warmup_bars  # 1 bar per day
        else:
            warmup_days = 50  # Default fallback

        # Ensure minimum warm-up period
        warmup_days = max(30, warmup_days)  # At least 30 days

        # Calculate extended start date (ensure UTC timezone consistency)
        original_start = pd.to_datetime(engine.config.start_date).tz_localize("UTC")
        extended_start = original_start - pd.Timedelta(days=warmup_days)

        # Load data with extended range
        try:
            # Use the engine's data manager to load extended data
            extended_data = engine.data_manager.load_data(
                symbol=engine.config.symbol,
                timeframe=engine.config.timeframe,
                start_date=extended_start.strftime("%Y-%m-%d"),
                end_date=engine.config.end_date,
                mode="local",  # Use local data first
            )

            if extended_data.empty:
                # Fallback to original data loading if extended range fails
                logger.warning(
                    f"Failed to load extended data range, falling back to original range"
                )
                return engine._load_historical_data()

            logger.info(
                f"Loaded {len(extended_data)} bars including {warmup_days:.0f} days warm-up period"
            )
            return extended_data

        except Exception as e:
            logger.warning(
                f"Failed to load extended data range: {e}, falling back to original range"
            )
            return engine._load_historical_data()

    async def _run_backtest_with_progress(
        self, engine, operation_id: str, estimated_bars: int
    ):
        """
        Run backtest with progress tracking based on data processing.

        This method modifies the backtesting engine to report progress
        based on bars processed during the main simulation loop.
        """
        # Load data first to get actual bar count
        data = self._load_data_with_warmup(engine)

        # Find the start index for actual backtest period
        backtest_start_date = pd.to_datetime(engine.config.start_date).tz_localize(
            "UTC"
        )
        backtest_start_idx = 0
        for i, timestamp in enumerate(data.index):
            if timestamp >= backtest_start_date:
                backtest_start_idx = i
                break

        actual_backtest_bars = len(data) - backtest_start_idx
        total_bars_loaded = len(data)

        # Update progress with actual bar count
        await self.operations_service.update_progress(
            operation_id,
            OperationProgress(
                percentage=20.0,
                current_step=f"Starting backtest simulation on {actual_backtest_bars:,} bars (loaded {total_bars_loaded:,} total with warm-up)",
                items_total=actual_backtest_bars,
            ),
        )

        # Run backtest with custom progress callback
        # We'll run it in a thread and periodically check a progress file
        import asyncio
        import time

        # Store progress tracking state
        progress_state = {"bars_processed": 0, "trades_executed": 0}

        # Monkey patch the engine to track progress
        original_run = engine.run

        def progress_aware_run():
            # Get the original run method's data loading and setup
            start_time = pd.Timestamp.now()
            execution_start = time.time()

            # Load data with warm-up period for indicators
            data = self._load_data_with_warmup(engine)
            if data.empty:
                raise ValueError(
                    f"No data loaded for {engine.config.symbol} {engine.config.timeframe}"
                )

            # Find the start index for actual backtest period
            # (data before this is warm-up data)
            backtest_start_date = pd.to_datetime(engine.config.start_date).tz_localize(
                "UTC"
            )
            backtest_start_idx = 0
            for i, timestamp in enumerate(data.index):
                if timestamp >= backtest_start_date:
                    backtest_start_idx = i
                    break

            logger.info(
                f"Loaded {len(data)} total bars, backtest starts at index {backtest_start_idx}"
            )

            # Initialize tracking (same as original engine)
            trades_executed = 0

            # Main simulation loop with progress tracking
            # Only iterate over the actual backtest period, but always pass full historical data
            for idx in range(backtest_start_idx, len(data)):
                current_bar = data.iloc[idx]
                current_timestamp = current_bar.name
                current_price = current_bar["close"]

                # Update progress state (relative to backtest period)
                bars_in_backtest_period = idx - backtest_start_idx + 1
                total_backtest_bars = len(data) - backtest_start_idx
                progress_state["bars_processed"] = bars_in_backtest_period

                # Prepare historical data up to current point (includes warm-up data)
                historical_data = data.iloc[: idx + 1]

                # Portfolio state for decision making
                portfolio_state = {
                    "total_value": engine.position_manager.get_portfolio_value(
                        current_price
                    ),
                    "available_capital": engine.position_manager.available_capital,
                }

                # Get trading signal from decision orchestrator
                decision = engine.orchestrator.make_decision(
                    symbol=engine.config.symbol,
                    timeframe=engine.config.timeframe,
                    current_bar=current_bar,
                    historical_data=historical_data,
                    portfolio_state=portfolio_state,
                )

                # Execute trade if signal is actionable
                if decision.signal in [Signal.BUY, Signal.SELL]:
                    trade = engine.position_manager.execute_trade(
                        signal=decision.signal,
                        price=current_price,
                        timestamp=current_timestamp,
                        symbol=engine.config.symbol,
                        decision_metadata={
                            "confidence": decision.confidence,
                            "reasoning": decision.reasoning,
                        },
                    )

                    if trade:
                        trades_executed += 1
                        progress_state["trades_executed"] = trades_executed

                # Update portfolio value tracking
                current_position = engine.position_manager.current_position
                engine.performance_tracker.update(
                    timestamp=current_timestamp,
                    price=current_price,
                    portfolio_value=engine.position_manager.get_portfolio_value(current_price),
                    position=current_position,
                )

            # Build final results (same as original)
            end_time = pd.Timestamp.now()
            execution_time = time.time() - execution_start

            trades = engine.position_manager.get_trade_history()
            metrics = engine.performance_tracker.calculate_metrics(
                trades=trades,
                initial_capital=engine.config.initial_capital,
                start_date=pd.to_datetime(engine.config.start_date),
                end_date=pd.to_datetime(engine.config.end_date),
            )
            equity_curve = engine.performance_tracker.get_equity_curve()

            from ktrdr.backtesting.engine import BacktestResults

            return BacktestResults(
                strategy_name=engine.strategy_name,
                symbol=engine.config.symbol,
                timeframe=engine.config.timeframe,
                config=engine.config,
                trades=trades,
                metrics=metrics,
                equity_curve=equity_curve,
                start_time=start_time,
                end_time=end_time,
                execution_time_seconds=execution_time,
            )

        # Replace the run method
        engine.run = progress_aware_run

        # Run with progress monitoring
        task = asyncio.create_task(asyncio.to_thread(engine.run))

        # Monitor progress while running
        last_progress = 20.0
        while not task.done():
            await asyncio.sleep(1.0)  # Check every second

            bars_processed = progress_state["bars_processed"]
            trades_executed = progress_state["trades_executed"]

            if bars_processed > 0:
                # Progress from 20% to 90% based on bars processed
                data_progress = (
                    bars_processed / actual_backtest_bars
                ) * 70  # 70% range for data processing
                current_progress = 20.0 + data_progress

                if (
                    current_progress > last_progress + 1
                ):  # Only update if significant change
                    await self.operations_service.update_progress(
                        operation_id,
                        OperationProgress(
                            percentage=min(current_progress, 90.0),
                            current_step=f"Processing bar {bars_processed:,}/{actual_backtest_bars:,} ({trades_executed} trades)",
                            items_processed=bars_processed,
                            items_total=actual_backtest_bars,
                        ),
                    )
                    last_progress = current_progress

        # Get the results
        results = await task
        return results

    async def get_backtest_status(self, backtest_id: str) -> Dict[str, Any]:
        """
        Get the current status of a backtest.

        Args:
            backtest_id: The backtest identifier (operation ID)

        Returns:
            Dict containing current backtest status
        """
        # Get operation info from operations service
        operation = await self.operations_service.get_operation(backtest_id)
        if not operation:
            raise ValidationError(f"Backtest {backtest_id} not found")

        # Extract strategy info from metadata
        strategy_name = operation.metadata.parameters.get("strategy_name", "unknown")

        # Return status compatible with existing API
        return {
            "backtest_id": operation.operation_id,
            "strategy_name": strategy_name,
            "symbol": operation.metadata.symbol,
            "timeframe": operation.metadata.timeframe,
            "status": operation.status.value,
            "progress": int(operation.progress.percentage),
            "started_at": (
                operation.started_at.isoformat() if operation.started_at else None
            ),
            "completed_at": (
                operation.completed_at.isoformat() if operation.completed_at else None
            ),
            "error": operation.error_message,
        }

    async def get_backtest_results(self, backtest_id: str) -> Dict[str, Any]:
        """
        Get the full results of a completed backtest.

        Args:
            backtest_id: The backtest identifier (operation ID)

        Returns:
            Dict containing backtest results
        """
        # Get operation info from operations service
        operation = await self.operations_service.get_operation(backtest_id)
        if not operation:
            raise ValidationError(f"Backtest {backtest_id} not found")

        if operation.status.value != "completed":
            raise ValidationError(f"Backtest {backtest_id} is not completed yet")

        # For now, we'll use a simple approach where detailed results are stored
        # in the operation's result_summary. For very large results, we might
        # need a separate storage mechanism in the future.
        if not operation.result_summary:
            raise DataError(f"No results available for backtest {backtest_id}")

        results = operation.result_summary

        # Format results for API response
        # The results structure has nested metrics and trade_count at top level
        metrics_data = results.get("metrics", {})
        config_data = results.get("config", {})

        # Calculate final value from initial capital + total return
        initial_capital = config_data.get("initial_capital", 100000)
        total_return = metrics_data.get("total_return", 0)
        final_value = initial_capital + total_return

        # Extract metadata
        strategy_name = operation.metadata.parameters.get("strategy_name", "unknown")
        initial_capital = operation.metadata.parameters.get("initial_capital", 100000)

        return {
            "backtest_id": backtest_id,
            "strategy_name": strategy_name,
            "symbol": operation.metadata.symbol,
            "timeframe": operation.metadata.timeframe,
            "start_date": (
                operation.metadata.start_date.strftime("%Y-%m-%d")
                if operation.metadata.start_date
                else None
            ),
            "end_date": (
                operation.metadata.end_date.strftime("%Y-%m-%d")
                if operation.metadata.end_date
                else None
            ),
            "metrics": {
                "total_return": metrics_data.get("total_return", 0),
                "annualized_return": metrics_data.get("annualized_return", 0),
                "sharpe_ratio": metrics_data.get("sharpe_ratio", 0),
                "max_drawdown": metrics_data.get("max_drawdown", 0),
                "win_rate": metrics_data.get("win_rate", 0),
                "profit_factor": metrics_data.get("profit_factor", 0),
                "total_trades": metrics_data.get(
                    "total_trades", results.get("trade_count", 0)
                ),
            },
            "summary": {
                "initial_capital": initial_capital,
                "final_value": initial_capital + total_return,
                "total_pnl": total_return,
                "winning_trades": metrics_data.get("winning_trades", 0),
                "losing_trades": metrics_data.get("losing_trades", 0),
            },
        }

    async def get_backtest_trades(self, backtest_id: str) -> List[Dict[str, Any]]:
        """
        Get the list of trades from a backtest.

        Args:
            backtest_id: The backtest identifier (operation ID)

        Returns:
            List of trade records
        """
        # Get operation info from operations service
        operation = await self.operations_service.get_operation(backtest_id)
        if not operation:
            raise ValidationError(f"Backtest {backtest_id} not found")

        if operation.status.value != "completed":
            raise ValidationError(f"Backtest {backtest_id} is not completed yet")

        # Get results from operation
        if not operation.result_summary or "trades" not in operation.result_summary:
            return []

        # Format trades for API response
        trades = []
        raw_trades = operation.result_summary["trades"]
        logger.info(f"Raw trades data: {len(raw_trades)} trades found")

        for trade in raw_trades:
            formatted_trade = {
                "trade_id": trade.get("trade_id"),
                "entry_time": trade.get("entry_time"),
                "exit_time": trade.get("exit_time"),
                "side": trade.get("side"),
                "entry_price": trade.get("entry_price"),
                "exit_price": trade.get("exit_price"),
                "quantity": trade.get("quantity"),
                "pnl": trade.get("pnl"),
                "pnl_percent": trade.get("pnl_percent"),
                "entry_reason": trade.get("entry_reason"),
                "exit_reason": trade.get("exit_reason"),
            }
            trades.append(formatted_trade)

        logger.info(f"Returning {len(trades)} formatted trades")
        return trades

    async def get_equity_curve(self, backtest_id: str) -> Dict[str, Any]:
        """
        Get the equity curve data from a backtest.

        Args:
            backtest_id: The backtest identifier (operation ID)

        Returns:
            Dict containing equity curve data
        """
        # Get operation info from operations service
        operation = await self.operations_service.get_operation(backtest_id)
        if not operation:
            raise ValidationError(f"Backtest {backtest_id} not found")

        if operation.status.value != "completed":
            raise ValidationError(f"Backtest {backtest_id} is not completed yet")

        # Get results from operation
        if (
            not operation.result_summary
            or "equity_curve" not in operation.result_summary
        ):
            raise DataError(
                f"No equity curve data available for backtest {backtest_id}"
            )

        equity_curve = operation.result_summary["equity_curve"]

        # Convert to API format
        return {
            "timestamps": equity_curve.get("timestamps", []),
            "values": equity_curve.get("values", []),
            "drawdowns": equity_curve.get("drawdowns", []),
        }

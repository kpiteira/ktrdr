"""
Backtesting service for the KTRDR API.

This module provides the service layer for backtesting operations,
bridging the API endpoints with the core backtesting engine.
"""

import asyncio
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ktrdr import get_logger
from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationProgress,
    OperationType,
)
from ktrdr.api.services.base import BaseService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.data.data_manager import DataManager
from ktrdr.errors import DataError, ValidationError

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

    async def health_check(self) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
            mode="backtesting",
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
                    percentage=5.0, 
                    current_step="Validating strategy configuration",
                    steps_completed=0,
                    steps_total=10,
                    items_processed=0,
                    items_total=None,
                    current_item=None
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
                    percentage=10.0, 
                    current_step="Preparing data loading configuration",
                    steps_completed=1,
                    steps_total=10,
                    items_processed=0,
                    items_total=None,
                    current_item=None
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
                    steps_completed=2,
                    steps_total=10,
                    items_processed=0,
                    items_total=total_bars,
                    current_item=None
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
                    percentage=95.0, 
                    current_step="Processing backtest results",
                    steps_completed=9,
                    steps_total=10,
                    items_processed=0,
                    items_total=None,
                    current_item=None
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

    async def _run_backtest_with_progress(
        self, engine, operation_id: str, estimated_bars: int
    ):
        """
        Run backtest with REAL progress tracking based on actual bars processed.
        """
        # Update progress: starting backtest
        await self.operations_service.update_progress(
            operation_id,
            OperationProgress(
                percentage=20.0,
                current_step="Starting backtest with proven engine",
                steps_completed=2,
                steps_total=10,
                items_processed=0,
                items_total=None,
                current_item=None
            ),
        )

        logger.info(f"Starting real backtest with proven engine: {engine}")

        # Create shared progress state for thread communication
        progress_state = {
            "current_bar": 0,
            "total_bars": estimated_bars,
            "portfolio_value": 0,
            "trades_executed": 0,
            "last_update": 0,
        }

        # Create a progress callback that gets REAL progress from the engine
        def progress_callback(
            current_bar: int, total_bars: int, additional_data: Optional[dict[Any, Any]] = None
        ):
            """Real progress callback based on actual bars processed."""
            try:
                progress_state["current_bar"] = current_bar
                progress_state["total_bars"] = total_bars
                if additional_data:
                    progress_state["portfolio_value"] = additional_data.get(
                        "portfolio_value", 0
                    )
                    progress_state["trades_executed"] = additional_data.get(
                        "trades_executed", 0
                    )
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

        # Set the progress callback on the engine
        engine.progress_callback = progress_callback

        # Run the backtesting engine in a thread
        task = asyncio.create_task(asyncio.to_thread(engine.run))

        # Monitor REAL progress from the engine
        last_reported_percentage = 20.0

        while not task.done():
            await asyncio.sleep(1.0)  # Check every second for responsive updates

            # Calculate REAL progress based on actual bars processed
            current_bar = progress_state["current_bar"]
            total_bars = progress_state["total_bars"]

            if total_bars > 0:
                # Calculate percentage: 20% (start) + 70% (processing) = 90% max
                bar_progress = (current_bar / total_bars) * 70.0
                real_percentage = min(20.0 + bar_progress, 90.0)

                # Only update if progress increased by at least 2%
                if real_percentage - last_reported_percentage >= 2.0:
                    portfolio_value = progress_state["portfolio_value"]
                    trades_executed = progress_state["trades_executed"]

                    # Create meaningful progress description
                    step_desc = f"Processing bar {current_bar:,} of {total_bars:,}"
                    if portfolio_value > 0:
                        step_desc += f" | Portfolio: ${portfolio_value:,.0f}"
                    if trades_executed > 0:
                        step_desc += f" | Trades: {trades_executed}"

                    await self.operations_service.update_progress(
                        operation_id,
                        OperationProgress(
                            percentage=real_percentage,
                            current_step=step_desc,
                            steps_completed=3,
                            steps_total=10,
                            items_processed=current_bar,
                            items_total=total_bars,
                            current_item=None
                        ),
                    )
                    last_reported_percentage = real_percentage
                    logger.debug(
                        f"Real progress update: {real_percentage:.1f}% ({current_bar}/{total_bars} bars)"
                    )

        # Get the real results from the proven engine
        results = await task
        logger.info("Real backtest completed successfully")
        return results

    async def get_backtest_status(self, backtest_id: str) -> dict[str, Any]:
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

    async def get_backtest_results(self, backtest_id: str) -> dict[str, Any]:
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
        initial_capital + total_return

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
                "max_drawdown": metrics_data.get("max_drawdown_pct", 0)
                * 100,  # Convert to percentage for display
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

    async def get_backtest_trades(self, backtest_id: str) -> list[dict[str, Any]]:
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

    async def get_equity_curve(self, backtest_id: str) -> dict[str, Any]:
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

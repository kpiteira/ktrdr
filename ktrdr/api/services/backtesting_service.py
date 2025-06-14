"""
Backtesting service for the KTRDR API.

This module provides the service layer for backtesting operations,
bridging the API endpoints with the core backtesting engine.
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import pandas as pd

from ktrdr import get_logger
from ktrdr.api.services.base import BaseService
from ktrdr.backtesting.engine import BacktestingEngine
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.data.data_manager import DataManager
from ktrdr.errors import DataError, ValidationError

logger = get_logger(__name__)


class BacktestingService(BaseService):
    """Service for managing backtesting operations."""

    def __init__(self):
        """Initialize the backtesting service."""
        super().__init__()
        self.data_manager = DataManager()
        self.model_loader = ModelLoader()
        # Track active backtests
        self._active_backtests: Dict[str, Dict[str, Any]] = {}

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the backtesting service.

        Returns:
            Dict[str, Any]: Health check information
        """
        return {
            "service": "BacktestingService",
            "status": "ok",
            "active_backtests": len(self._active_backtests),
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
            Dict containing backtest_id and initial status
        """
        # Generate unique backtest ID
        backtest_id = str(uuid.uuid4())

        # Record backtest start
        self._active_backtests[backtest_id] = {
            "id": backtest_id,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "status": "starting",
            "progress": 0,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "results": None,
            "error": None,
        }

        # Start backtest in background
        asyncio.create_task(
            self._run_backtest_async(
                backtest_id,
                strategy_name,
                symbol,
                timeframe,
                start_date,
                end_date,
                initial_capital,
            )
        )

        return {
            "backtest_id": backtest_id,
            "status": "starting",
            "message": f"Backtest {backtest_id} started for {strategy_name}",
        }

    async def _run_backtest_async(
        self,
        backtest_id: str,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float,
    ) -> None:
        """
        Run backtest asynchronously using the CLI code path to ensure consistency.

        This method uses the exact same approach as the CLI to avoid divergence.
        """
        try:
            # Update status to running
            self._active_backtests[backtest_id]["status"] = "running"
            self._active_backtests[backtest_id]["progress"] = 10

            # Build strategy config path (same as CLI does it)
            strategy_path = Path(f"strategies/{strategy_name}.yaml")
            if not strategy_path.exists():
                raise ValidationError(f"Strategy '{strategy_name}' not found")

            self._active_backtests[backtest_id]["progress"] = 20

            # Create backtest configuration (exactly like CLI does)
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

            self._active_backtests[backtest_id]["progress"] = 30

            # Create and run backtesting engine (exactly like CLI does)
            engine = BacktestingEngine(config)

            self._active_backtests[backtest_id]["progress"] = 50

            # Run the backtest using the existing engine
            results = await asyncio.to_thread(engine.run)

            self._active_backtests[backtest_id]["progress"] = 90

            # Convert results to dictionary format (exactly like CLI does)
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

            self._active_backtests[backtest_id]["progress"] = 100
            self._active_backtests[backtest_id]["status"] = "completed"
            self._active_backtests[backtest_id][
                "completed_at"
            ] = datetime.now().isoformat()
            self._active_backtests[backtest_id]["results"] = results_dict

        except Exception as e:
            logger.error(f"Backtest {backtest_id} failed: {str(e)}", exc_info=True)
            self._active_backtests[backtest_id]["status"] = "failed"
            self._active_backtests[backtest_id]["error"] = str(e)

    async def get_backtest_status(self, backtest_id: str) -> Dict[str, Any]:
        """
        Get the current status of a backtest.

        Args:
            backtest_id: The backtest identifier

        Returns:
            Dict containing current backtest status
        """
        if backtest_id not in self._active_backtests:
            raise ValidationError(f"Backtest {backtest_id} not found")

        backtest = self._active_backtests[backtest_id]

        # Return status without full results (those are fetched separately)
        return {
            "backtest_id": backtest["id"],
            "strategy_name": backtest["strategy_name"],
            "symbol": backtest["symbol"],
            "timeframe": backtest["timeframe"],
            "status": backtest["status"],
            "progress": backtest["progress"],
            "started_at": backtest["started_at"],
            "completed_at": backtest["completed_at"],
            "error": backtest["error"],
        }

    async def get_backtest_results(self, backtest_id: str) -> Dict[str, Any]:
        """
        Get the full results of a completed backtest.

        Args:
            backtest_id: The backtest identifier

        Returns:
            Dict containing backtest results
        """
        if backtest_id not in self._active_backtests:
            raise ValidationError(f"Backtest {backtest_id} not found")

        backtest = self._active_backtests[backtest_id]

        if backtest["status"] != "completed":
            raise ValidationError(f"Backtest {backtest_id} is not completed yet")

        if backtest["results"] is None:
            raise DataError(f"No results available for backtest {backtest_id}")

        results = backtest["results"]

        # Format results for API response
        # The results structure has nested metrics and trade_count at top level
        metrics_data = results.get("metrics", {})
        config_data = results.get("config", {})

        # Calculate final value from initial capital + total return
        initial_capital = config_data.get("initial_capital", 100000)
        total_return = metrics_data.get("total_return", 0)
        final_value = initial_capital + total_return

        return {
            "backtest_id": backtest_id,
            "strategy_name": backtest["strategy_name"],
            "symbol": backtest["symbol"],
            "timeframe": backtest["timeframe"],
            "start_date": backtest["start_date"],
            "end_date": backtest["end_date"],
            "metrics": {
                "total_return": metrics_data.get("total_return", 0),
                "annualized_return": metrics_data.get("annualized_return", 0),
                "sharpe_ratio": metrics_data.get("sharpe_ratio", 0),
                "max_drawdown": metrics_data.get("max_drawdown", 0),
                "win_rate": metrics_data.get("win_rate", 0),
                "profit_factor": metrics_data.get("profit_factor", 0),
                "total_trades": metrics_data.get(
                    "total_trades", results.get("trade_count", 0)
                ),  # Use metrics.total_trades first, fallback to top-level trade_count
            },
            "summary": {
                "initial_capital": initial_capital,
                "final_value": final_value,  # Calculate correctly: initial + total_return
                "total_pnl": total_return,  # total_pnl should be same as total_return
                "winning_trades": metrics_data.get("winning_trades", 0),
                "losing_trades": metrics_data.get("losing_trades", 0),
            },
        }

    async def get_backtest_trades(self, backtest_id: str) -> List[Dict[str, Any]]:
        """
        Get the list of trades from a backtest.

        Args:
            backtest_id: The backtest identifier

        Returns:
            List of trade records
        """
        if backtest_id not in self._active_backtests:
            raise ValidationError(f"Backtest {backtest_id} not found")

        backtest = self._active_backtests[backtest_id]

        if backtest["status"] != "completed":
            raise ValidationError(f"Backtest {backtest_id} is not completed yet")

        if backtest["results"] is None or "trades" not in backtest["results"]:
            return []

        # Format trades for API response
        trades = []
        raw_trades = backtest["results"]["trades"]
        logger.info(f"Raw trades data: {len(raw_trades)} trades found")
        logger.info(
            f"First trade sample: {raw_trades[0] if raw_trades else 'No trades'}"
        )

        for i, trade in enumerate(raw_trades):
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
            if i == 0:  # Log first trade for debugging
                logger.info(f"Formatted first trade: {formatted_trade}")
            trades.append(formatted_trade)

        logger.info(f"Returning {len(trades)} formatted trades")
        return trades

    async def get_equity_curve(self, backtest_id: str) -> Dict[str, Any]:
        """
        Get the equity curve data from a backtest.

        Args:
            backtest_id: The backtest identifier

        Returns:
            Dict containing equity curve data
        """
        if backtest_id not in self._active_backtests:
            raise ValidationError(f"Backtest {backtest_id} not found")

        backtest = self._active_backtests[backtest_id]

        if backtest["status"] != "completed":
            raise ValidationError(f"Backtest {backtest_id} is not completed yet")

        if backtest["results"] is None or "equity_curve" not in backtest["results"]:
            raise DataError(
                f"No equity curve data available for backtest {backtest_id}"
            )

        equity_curve = backtest["results"]["equity_curve"]

        # Convert to API format
        return {
            "timestamps": equity_curve.get("timestamps", []),
            "values": equity_curve.get("values", []),
            "drawdowns": equity_curve.get("drawdowns", []),
        }

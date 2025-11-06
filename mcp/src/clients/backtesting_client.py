"""Backtesting API client"""

from typing import Any

from .base import BaseAPIClient


class BacktestingAPIClient(BaseAPIClient):
    """API client for backtesting operations"""

    async def start_backtest(
        self,
        model_path: str,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        commission: float = 0.001,
        slippage: float = 0.001,
    ) -> dict[str, Any]:
        """Start backtest operation (async, returns operation_id)"""
        payload = {
            "model_path": model_path,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "commission": commission,
            "slippage": slippage,
        }

        response = await self._request("POST", "/backtests/start", json=payload)

        # Backtesting endpoint returns structure: {success, operation_id, status, ...}
        # Same pattern as training - no nested 'data' field
        # The _request method already validates success and raises on error
        return response

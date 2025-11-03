"""Data API client"""

from typing import Any, Optional

from .base import BaseAPIClient


class DataAPIClient(BaseAPIClient):
    """API client for data operations"""

    async def get_cached_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        trading_hours_only: bool = False,
        include_extended: bool = False,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """Get cached OHLCV data (synchronous, local only)"""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if trading_hours_only:
            params["trading_hours_only"] = trading_hours_only
        if include_extended:
            params["include_extended"] = include_extended

        response = await self._request(
            "GET", f"/data/{symbol}/{timeframe}", params=params
        )

        # TODO: Replace client-side limiting with proper backend pagination
        # This is a temporary workaround - backend should handle pagination with limit/offset
        # like operations_client.list_operations() does
        if limit and "data" in response and "dates" in response["data"]:
            data = response["data"]
            if len(data["dates"]) > limit:
                data["dates"] = data["dates"][-limit:]
                data["ohlcv"] = data["ohlcv"][-limit:] if data["ohlcv"] else []
                if data.get("points"):
                    data["points"] = data["points"][-limit:]
                if "metadata" in data:
                    data["metadata"]["points"] = len(data["dates"])
                    data["metadata"]["limited_by_client"] = True

        return response

    async def load_data_operation(
        self,
        symbol: str,
        timeframe: str = "1h",
        mode: str = "local",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Trigger data loading operation (async, returns operation_id)"""
        payload = {"symbol": symbol, "timeframe": timeframe, "mode": mode}
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date

        response = await self._request("POST", "/data/acquire/download", json=payload)

        # CRITICAL: Must have operation_id for tracking
        return self._extract_or_raise(response, operation="data loading")

    async def get_data_info(self, symbol: str) -> dict[str, Any]:
        """Get data information for a symbol"""
        return await self._request("GET", f"/data/info/{symbol}")

    async def get_symbols(self) -> list[dict[str, Any]]:
        """Get available trading symbols"""
        response = await self._request("GET", "/symbols")
        return self._extract_list(response)  # Simple extraction

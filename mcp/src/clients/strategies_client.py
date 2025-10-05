"""Strategies API client"""

from typing import Any

from .base import BaseAPIClient


class StrategiesAPIClient(BaseAPIClient):
    """API client for strategies operations"""

    async def list_strategies(self) -> dict[str, Any]:
        """List all available strategies"""
        response = await self._request("GET", "/strategies/")
        return response

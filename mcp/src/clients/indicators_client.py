"""Indicators API client"""

from typing import Any

from .base import BaseAPIClient


class IndicatorsAPIClient(BaseAPIClient):
    """API client for indicators operations"""

    async def list_indicators(self) -> list[dict[str, Any]]:
        """List all available indicators"""
        response = await self._request("GET", "/indicators/")
        return self._extract_list(response)  # Simple extraction

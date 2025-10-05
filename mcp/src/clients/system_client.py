"""System API client for health and diagnostics"""

from typing import Any

from .base import BaseAPIClient


class SystemAPIClient(BaseAPIClient):
    """API client for system-level operations (health, diagnostics, etc.)"""

    async def health_check(self) -> dict[str, Any]:
        """Check backend API health status"""
        return await self._request("GET", "/health")

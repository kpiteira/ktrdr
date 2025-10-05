"""Operations management API client"""

from typing import Any, Optional

from .base import BaseAPIClient


class OperationsAPIClient(BaseAPIClient):
    """API client for operations management"""

    async def list_operations(
        self,
        operation_type: Optional[str] = None,
        status: Optional[str] = None,
        active_only: bool = False,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List operations with filters"""
        params = {"limit": limit, "offset": offset}
        if operation_type:
            params["operation_type"] = operation_type
        if status:
            params["status"] = status
        if active_only:
            params["active_only"] = active_only

        return await self._request("GET", "/operations", params=params)

    async def get_operation_status(self, operation_id: str) -> dict[str, Any]:
        """Get detailed operation status"""
        return await self._request("GET", f"/operations/{operation_id}")

    async def cancel_operation(
        self, operation_id: str, reason: Optional[str] = None
    ) -> dict[str, Any]:
        """Cancel a running operation"""
        payload = {"reason": reason} if reason else None
        return await self._request(
            "DELETE", f"/operations/{operation_id}", json=payload
        )

    async def get_operation_results(self, operation_id: str) -> dict[str, Any]:
        """Get operation results (summary)"""
        return await self._request("GET", f"/operations/{operation_id}/results")

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
        # Return full response (tests expect success + data fields)
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

    async def get_operation_metrics(self, operation_id: str) -> dict[str, Any]:
        """
        Get domain-specific metrics for an operation (M1: API Contract).

        For training operations: returns epoch history, best epoch, overfitting indicators
        For other operations: returns operation-specific metrics

        In M1, returns empty structure. In M2, will return populated metrics.

        Args:
            operation_id: Operation ID

        Returns:
            dict: Response with metrics data

        Example:
            metrics = await client.get_operation_metrics("op-training-123")
            if metrics["data"]["metrics"].get("is_overfitting"):
                print("Overfitting detected!")
        """
        return await self._request("GET", f"/operations/{operation_id}/metrics")

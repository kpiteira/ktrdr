"""Training API client"""

from typing import Any, Optional

from .base import BaseAPIClient


class TrainingAPIClient(BaseAPIClient):
    """API client for training operations"""

    async def start_neural_training(
        self,
        symbols: list[str],
        timeframes: list[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> dict[str, Any]:
        """Start neural network training (async, returns operation_id)"""
        payload = {
            "symbols": symbols,
            "timeframes": timeframes,
            "strategy_name": strategy_name,
        }
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        if task_id:
            payload["task_id"] = task_id
        if detailed_analytics:
            payload["detailed_analytics"] = detailed_analytics

        response = await self._request("POST", "/trainings/start", json=payload)

        # Training endpoint returns flat structure: {success, task_id, status, ...}
        # No nested 'data' field, so return full response
        # The _request method already validates success and raises on error
        return response

    async def get_training_status(self, task_id: str) -> dict[str, Any]:
        """Get neural network training status"""
        return await self._request("GET", f"/trainings/{task_id}")

    async def get_model_performance(self, task_id: str) -> dict[str, Any]:
        """Get trained model performance metrics"""
        return await self._request("GET", f"/trainings/{task_id}/performance")

    async def list_trained_models(self) -> list[dict[str, Any]]:
        """List all trained models"""
        response = await self._request("GET", "/models")
        # Backend returns {models: [...]} instead of {data: [...]}
        return self._extract_list(response, field="models")

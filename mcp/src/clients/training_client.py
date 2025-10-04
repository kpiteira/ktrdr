"""Training API client"""

from typing import Any, Optional

from .base import BaseAPIClient


class TrainingAPIClient(BaseAPIClient):
    """API client for training operations"""

    async def start_neural_training(
        self,
        symbols: list[str],
        timeframe: str,
        config: dict[str, Any],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Start neural network training (async, returns operation_id)"""
        payload = {"symbols": symbols, "timeframe": timeframe, "config": config}
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        if task_id:
            payload["task_id"] = task_id

        return await self._request("POST", "/api/v1/trainings/start", json=payload)

    async def get_training_status(self, task_id: str) -> dict[str, Any]:
        """Get neural network training status"""
        return await self._request("GET", f"/api/v1/trainings/{task_id}")

    async def get_model_performance(self, task_id: str) -> dict[str, Any]:
        """Get trained model performance metrics"""
        return await self._request(
            "GET", f"/api/v1/trainings/{task_id}/performance"
        )

    async def list_trained_models(self) -> list[dict[str, Any]]:
        """List all trained models"""
        response = await self._request("GET", "/api/v1/models")
        return response.get("models", [])

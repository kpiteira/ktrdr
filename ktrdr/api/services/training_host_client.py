"""
Training Host Service Client

Client for communicating with the training host service to enable GPU acceleration.
Provides a bridge between the Docker backend and the host-based training service.
"""

import asyncio
import time
from typing import Any, Optional

import httpx

from ktrdr.logging import get_logger

logger = get_logger(__name__)


class TrainingHostServiceError(Exception):
    """Exception raised for training host service errors."""

    pass


class TrainingHostClient:
    """
    Client for communicating with the training host service.

    Provides methods to start, monitor, and manage training sessions on the host service,
    enabling GPU acceleration while maintaining compatibility with the existing API.
    """

    def __init__(self, base_url: str = "http://localhost:5002", timeout: float = 30.0):
        """
        Initialize the training host client.

        Args:
            base_url: Base URL of the training host service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def is_available(self) -> bool:
        """
        Check if the training host service is available.

        Returns:
            True if service is healthy and available
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/health")

            if response.status_code == 200:
                data = response.json()
                return data.get("healthy", False)
            return False

        except Exception as e:
            logger.debug(f"Training host service not available: {str(e)}")
            return False

    async def get_service_info(self) -> dict[str, Any]:
        """
        Get training host service information.

        Returns:
            Service information including GPU availability
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/")

            if response.status_code == 200:
                return response.json()
            else:
                raise TrainingHostServiceError(
                    f"Failed to get service info: {response.status_code}"
                )

        except httpx.RequestError as e:
            raise TrainingHostServiceError(f"Connection error: {str(e)}") from e

    async def start_training_session(self, config: dict[str, Any]) -> str:
        """
        Start a training session on the host service.

        Args:
            config: Training configuration containing:
                - strategy_config: Strategy configuration from YAML
                - symbol: Trading symbol
                - timeframes: List of timeframes
                - training_params: Training parameters (epochs, validation_split, etc.)
                - data_config: Data loading configuration

        Returns:
            Session ID for the started training session
        """
        try:
            # Prepare request payload for host service
            # Support both single symbol and multi-symbol configurations
            symbols = config.get(
                "symbols", [config.get("symbol")] if config.get("symbol") else ["AAPL"]
            )

            request_payload = {
                "model_configuration": {
                    "strategy_config": config.get("strategy_config", {}),
                    "symbols": symbols,  # Multi-symbol support
                    "timeframes": config.get("timeframes", []),
                    "model_type": config.get("model_type", "mlp"),
                    "multi_symbol": config.get("multi_symbol", len(symbols) > 1),
                },
                "training_configuration": {
                    "epochs": config.get("epochs", 100),
                    "validation_split": config.get("validation_split", 0.2),
                    "batch_size": config.get("batch_size", 32),
                    "learning_rate": config.get("learning_rate", 0.001),
                    "early_stopping": config.get("early_stopping", True),
                    "start_date": config.get("start_date"),
                    "end_date": config.get("end_date"),
                },
                "data_configuration": {
                    "symbols": symbols,  # Multi-symbol support
                    "timeframes": config.get("timeframes", []),
                    "data_source": config.get("data_source", "local"),
                    "indicators": config.get("indicators", []),
                    "fuzzy_config": config.get("fuzzy_config", {}),
                },
                "gpu_configuration": {
                    "enable_gpu": config.get("enable_gpu", True),
                    "memory_fraction": config.get("gpu_memory_fraction", 0.8),
                    "mixed_precision": config.get("mixed_precision", True),
                },
            }

            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/training/start", json=request_payload
            )

            if response.status_code == 200:
                data = response.json()
                session_id = data["session_id"]
                logger.info(f"Started training session {session_id} on host service")
                return session_id
            else:
                error_detail = response.json().get("detail", "Unknown error")
                raise TrainingHostServiceError(
                    f"Failed to start training: {error_detail}"
                )

        except httpx.RequestError as e:
            raise TrainingHostServiceError(f"Connection error: {str(e)}") from e

    async def get_training_status(self, session_id: str) -> dict[str, Any]:
        """
        Get the status of a training session.

        Args:
            session_id: ID of the training session

        Returns:
            Training status including progress, metrics, and resource usage
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/training/status/{session_id}")

            if response.status_code == 200:
                return response.json()
            else:
                error_detail = response.json().get("detail", "Unknown error")
                raise TrainingHostServiceError(
                    f"Failed to get training status: {error_detail}"
                )

        except httpx.RequestError as e:
            raise TrainingHostServiceError(f"Connection error: {str(e)}") from e

    async def stop_training_session(
        self, session_id: str, save_checkpoint: bool = True
    ) -> dict[str, Any]:
        """
        Stop a training session.

        Args:
            session_id: ID of the training session to stop
            save_checkpoint: Whether to save a checkpoint before stopping

        Returns:
            Stop operation result
        """
        try:
            request_payload = {
                "session_id": session_id,
                "save_checkpoint": save_checkpoint,
            }

            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/training/stop", json=request_payload
            )

            if response.status_code == 200:
                logger.info(f"Stopped training session {session_id}")
                return response.json()
            else:
                error_detail = response.json().get("detail", "Unknown error")
                raise TrainingHostServiceError(
                    f"Failed to stop training: {error_detail}"
                )

        except httpx.RequestError as e:
            raise TrainingHostServiceError(f"Connection error: {str(e)}") from e

    async def list_training_sessions(self) -> list[dict[str, Any]]:
        """
        List all training sessions on the host service.

        Returns:
            List of training session summaries
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/training/sessions")

            if response.status_code == 200:
                data = response.json()
                return data.get("sessions", [])
            else:
                error_detail = response.json().get("detail", "Unknown error")
                raise TrainingHostServiceError(
                    f"Failed to list sessions: {error_detail}"
                )

        except httpx.RequestError as e:
            raise TrainingHostServiceError(f"Connection error: {str(e)}") from e

    async def cleanup_session(self, session_id: str) -> dict[str, Any]:
        """
        Clean up a completed training session.

        Args:
            session_id: ID of the session to clean up

        Returns:
            Cleanup operation result
        """
        try:
            client = await self._get_client()
            response = await client.delete(
                f"{self.base_url}/training/sessions/{session_id}"
            )

            if response.status_code == 200:
                logger.info(f"Cleaned up training session {session_id}")
                return response.json()
            else:
                error_detail = response.json().get("detail", "Unknown error")
                raise TrainingHostServiceError(
                    f"Failed to cleanup session: {error_detail}"
                )

        except httpx.RequestError as e:
            raise TrainingHostServiceError(f"Connection error: {str(e)}") from e

    async def wait_for_completion(
        self,
        session_id: str,
        poll_interval: float = 2.0,
        timeout: Optional[float] = None,
        progress_callback: Optional[callable] = None,
    ) -> dict[str, Any]:
        """
        Wait for a training session to complete, polling for status updates.

        Args:
            session_id: ID of the training session
            poll_interval: Interval between status polls in seconds
            timeout: Maximum time to wait in seconds (None for no timeout)
            progress_callback: Optional callback function for progress updates

        Returns:
            Final training status
        """
        start_time = time.time()
        last_progress = None

        while True:
            try:
                status = await self.get_training_status(session_id)

                # Call progress callback if provided and progress changed
                if progress_callback and status.get("progress") != last_progress:
                    progress_callback(status)
                    last_progress = status.get("progress")

                # Check if training is complete
                if status["status"] in ["completed", "failed", "stopped"]:
                    logger.info(
                        f"Training session {session_id} finished with status: {status['status']}"
                    )
                    return status

                # Check timeout
                if timeout and (time.time() - start_time) > timeout:
                    raise TrainingHostServiceError(
                        f"Training session {session_id} timed out after {timeout} seconds"
                    )

                # Wait before next poll
                await asyncio.sleep(poll_interval)

            except TrainingHostServiceError:
                # Re-raise service errors
                raise
            except Exception as e:
                logger.warning(
                    f"Error polling training status for session {session_id}: {str(e)}"
                )
                await asyncio.sleep(poll_interval)

    def map_to_operation_progress(self, status: dict[str, Any]) -> dict[str, Any]:
        """
        Map host service status to operation progress format.

        Args:
            status: Host service training status

        Returns:
            Progress in operation format compatible with existing API
        """
        progress = status.get("progress", {})
        metrics = status.get("metrics", {})

        # Calculate overall progress percentage
        epoch = progress.get("epoch", 0)
        total_epochs = progress.get("total_epochs", 1)
        batch = progress.get("batch", 0)
        total_batches = progress.get("total_batches", 1)
        total_batches = total_batches if total_batches > 0 else 1

        # Calculate progress: epoch progress + within-epoch progress
        epoch_progress = (epoch / total_epochs) if total_epochs > 0 else 0
        batch_progress = (
            (batch / total_batches) / total_epochs if total_epochs > 0 else 0
        )
        overall_progress = min(100.0, (epoch_progress + batch_progress) * 100)

        # Map status
        status_mapping = {
            "initializing": "in_progress",
            "running": "in_progress",
            "completed": "completed",
            "failed": "failed",
            "stopped": "failed",  # Map stopped to failed for operation status
        }

        operation_status = status_mapping.get(status.get("status"), "in_progress")

        # Create operation progress format
        operation_progress = {
            "status": operation_status,
            "progress_percentage": overall_progress,
            "current_step": f"Epoch {epoch}/{total_epochs}",
            "details": {
                "epoch": epoch,
                "total_epochs": total_epochs,
                "batch": batch,
                "total_batches": total_batches,
                "session_id": status.get("session_id"),
                "gpu_usage": status.get("gpu_usage", {}),
                "metrics": metrics,
                "error": status.get("error"),
            },
        }

        return operation_progress


# Singleton instance for global use
_training_host_client: Optional[TrainingHostClient] = None


def get_training_host_client(
    base_url: str = "http://localhost:5002",
) -> TrainingHostClient:
    """
    Get or create a global training host client instance.

    Args:
        base_url: Base URL of the training host service

    Returns:
        TrainingHostClient instance
    """
    global _training_host_client
    if _training_host_client is None:
        _training_host_client = TrainingHostClient(base_url)
    return _training_host_client


async def close_training_host_client():
    """Close the global training host client."""
    global _training_host_client
    if _training_host_client:
        await _training_host_client.close()
        _training_host_client = None

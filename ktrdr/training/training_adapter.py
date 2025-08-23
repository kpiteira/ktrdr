"""
Training Adapter

This adapter bridges the training layer to local or host service training, implementing
a clean interface pattern mirroring the IB data adapter.

The adapter handles:
- Training request routing (local vs host service)
- HTTP communication with training host service
- Error translation from host service to generic training errors
- Progress forwarding and status management
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json

from ktrdr.logging import get_logger
from ktrdr.errors import DataError, ConnectionError as KtrdrConnectionError

# HTTP client for host service communication
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = get_logger(__name__)


class TrainingProviderError(Exception):
    """Base exception for training provider errors."""

    def __init__(self, message: str, provider: str = "Training"):
        self.message = message
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class TrainingProviderConnectionError(TrainingProviderError):
    """Exception for training provider connection errors."""

    pass


class TrainingProviderDataError(TrainingProviderError):
    """Exception for training provider data errors."""

    pass


class TrainingAdapter:
    """
    Adapter that provides clean interface for training operations using local or host service.

    This adapter provides a clean interface between the training layer and the
    training implementation, handling connection management, error translation,
    and request routing.
    """

    def __init__(
        self, use_host_service: bool = False, host_service_url: Optional[str] = None
    ):
        """
        Initialize training adapter.

        Args:
            use_host_service: Whether to use host service instead of local training
            host_service_url: URL of the training host service (e.g., http://localhost:5002)
        """
        self.use_host_service = use_host_service
        self.host_service_url = host_service_url or "http://localhost:5002"

        # Validate configuration
        if use_host_service and not HTTPX_AVAILABLE:
            raise TrainingProviderError(
                "httpx library required for host service mode but not available",
                provider="Training",
            )

        # Initialize appropriate components based on mode
        if not use_host_service:
            # Local training mode (existing behavior)
            from .train_strategy import StrategyTrainer

            self.local_trainer = StrategyTrainer()
            logger.info(f"TrainingAdapter initialized for local training")
        else:
            # Host service mode
            self.local_trainer = None
            logger.info(
                f"TrainingAdapter initialized for host service at {self.host_service_url}"
            )

        # Statistics
        self.requests_made = 0
        self.errors_encountered = 0
        self.last_request_time: Optional[datetime] = None

    async def _call_host_service_post(
        self, endpoint: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make POST request to host service."""
        if not self.use_host_service:
            raise RuntimeError("Host service not enabled")

        url = f"{self.host_service_url}{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise TrainingProviderConnectionError(
                f"Host service request failed: {str(e)}", provider="Training"
            )
        except Exception as e:
            raise TrainingProviderError(
                f"Host service communication error: {str(e)}", provider="Training"
            )

    async def _call_host_service_get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make GET request to host service."""
        if not self.use_host_service:
            raise RuntimeError("Host service not enabled")

        url = f"{self.host_service_url}{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params or {})
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise TrainingProviderConnectionError(
                f"Host service request failed: {str(e)}", provider="Training"
            )
        except Exception as e:
            raise TrainingProviderError(
                f"Host service communication error: {str(e)}", provider="Training"
            )

    async def train_multi_symbol_strategy(
        self,
        strategy_config_path: str,
        symbols: List[str],
        timeframes: List[str],
        start_date: str,
        end_date: str,
        validation_split: float = 0.2,
        data_mode: str = "local",
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Train a multi-symbol strategy using local trainer or host service.

        Args:
            strategy_config_path: Path to strategy configuration file
            symbols: List of trading symbols
            timeframes: List of timeframes
            start_date: Start date for training data
            end_date: End date for training data
            validation_split: Validation split ratio
            data_mode: Data loading mode
            progress_callback: Optional progress callback function

        Returns:
            Dictionary with training results
        """
        try:
            # Update statistics
            self.requests_made += 1
            self.last_request_time = datetime.now(timezone.utc)

            if self.use_host_service:
                # Use host service for training
                logger.info(
                    f"Starting training via host service for {symbols} on {timeframes}"
                )

                response = await self._call_host_service_post(
                    "/training/start",
                    {
                        "model_configuration": {
                            "strategy_config": strategy_config_path,
                            "symbols": symbols,
                            "timeframes": timeframes,
                            "model_type": "mlp",
                            "multi_symbol": len(symbols) > 1,
                        },
                        "training_configuration": {
                            "validation_split": validation_split,
                            "start_date": start_date,
                            "end_date": end_date,
                            "data_mode": data_mode,
                        },
                        "data_configuration": {
                            "symbols": symbols,
                            "timeframes": timeframes,
                            "data_source": data_mode,
                        },
                        "gpu_configuration": {
                            "enable_gpu": True,
                            "memory_fraction": 0.8,
                            "mixed_precision": True,
                        },
                    },
                )

                if not response.get("session_id"):
                    raise TrainingProviderDataError(
                        f"Training start failed: {response.get('message', 'Unknown error')}",
                        provider="Training",
                    )

                session_id = response["session_id"]
                logger.info(f"Training session {session_id} started on host service")

                # Return immediately with session_id (no background polling - operations service will poll)
                return {
                    "success": True,
                    "session_id": session_id,
                    "training_started": True,
                    "host_service_used": True,
                    "message": f"Training session {session_id} started on host service",
                }

            else:
                # Use local training (existing behavior)
                logger.info(f"Starting local training for {symbols} on {timeframes}")

                return self.local_trainer.train_multi_symbol_strategy(
                    strategy_config_path=strategy_config_path,
                    symbols=symbols,
                    timeframes=timeframes,
                    start_date=start_date,
                    end_date=end_date,
                    validation_split=validation_split,
                    data_mode=data_mode,
                    progress_callback=progress_callback,
                )

        except TrainingProviderError:
            # Re-raise provider errors
            self.errors_encountered += 1
            raise
        except Exception as e:
            # Wrap other exceptions
            self.errors_encountered += 1
            raise TrainingProviderError(
                f"Training failed: {str(e)}", provider="Training"
            )

    async def get_training_status(self, session_id: str) -> Dict[str, Any]:
        """Get status of a training session (host service only)."""
        if not self.use_host_service:
            raise TrainingProviderError(
                "Status checking only available for host service mode"
            )

        return await self._call_host_service_get(f"/training/status/{session_id}")

    async def stop_training(self, session_id: str) -> Dict[str, Any]:
        """Stop a training session (host service only)."""
        if not self.use_host_service:
            raise TrainingProviderError(
                "Training stopping only available for host service mode"
            )

        return await self._call_host_service_post(
            "/training/stop", {"session_id": session_id, "save_checkpoint": True}
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get adapter usage statistics."""
        return {
            "requests_made": self.requests_made,
            "errors_encountered": self.errors_encountered,
            "last_request_time": (
                self.last_request_time.isoformat() if self.last_request_time else None
            ),
            "error_rate": (
                self.errors_encountered / self.requests_made
                if self.requests_made > 0
                else 0.0
            ),
            "mode": "host_service" if self.use_host_service else "local",
        }

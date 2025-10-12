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

from datetime import datetime, timezone
from typing import Any, Optional

from ktrdr.async_infrastructure.cancellation import CancellationToken
from ktrdr.async_infrastructure.service_adapter import (
    AsyncServiceAdapter,
    HostServiceConfig,
)
from ktrdr.logging import get_logger

# HTTP client for host service communication - Now handled by AsyncServiceAdapter
HTTPX_AVAILABLE = True  # Assume available since AsyncServiceAdapter handles this

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


class TrainingAdapter(AsyncServiceAdapter):
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

        # Initialize AsyncServiceAdapter for host service mode
        if use_host_service:
            config = HostServiceConfig(
                base_url=self.host_service_url,
                connection_pool_limit=5,  # Training-specific: 5 connections for training operations
            )
            AsyncServiceAdapter.__init__(self, config)

        # TrainingAdapter is now HOST-SERVICE-ONLY
        # Local training uses LocalTrainingOrchestrator directly, not this adapter
        if not use_host_service:
            raise TrainingProviderError(
                "TrainingAdapter no longer supports local training. "
                "Use LocalTrainingOrchestrator for local training execution.",
                provider="Training",
            )

        logger.info(
            f"TrainingAdapter initialized for host service at {self.host_service_url}"
        )

        # Statistics
        self.requests_made = 0
        self.errors_encountered = 0
        self.last_request_time: Optional[datetime] = None

    # AsyncServiceAdapter abstract method implementations
    def get_service_name(self) -> str:
        """Return service identifier for logging and metrics."""
        return "Training Service"

    def get_service_type(self) -> str:
        """Return service type identifier for categorization."""
        return "training"

    def get_base_url(self) -> str:
        """Return service base URL from configuration."""
        return self.host_service_url

    async def get_health_check_endpoint(self) -> str:
        """Return endpoint for health checking."""
        return "/health"

    async def _ensure_client_initialized(self) -> None:
        """Ensure HTTP client is initialized (for long-lived adapter pattern)."""
        if self.use_host_service and self._http_client is None:
            await self._setup_connection_pool()

    async def _call_host_service_post(
        self, endpoint: str, data: dict[str, Any], cancellation_token=None
    ) -> dict[str, Any]:
        """Make POST request to host service using AsyncServiceAdapter."""
        if not self.use_host_service:
            raise RuntimeError("Host service not enabled")

        # Ensure HTTP client is initialized
        await self._ensure_client_initialized()

        try:
            return await AsyncServiceAdapter._call_host_service_post(
                self, endpoint, data, cancellation_token
            )
        except Exception as e:
            # Translate AsyncServiceAdapter errors to TrainingProvider errors for compatibility
            self._translate_host_service_error(e)
            # This line should never be reached since _translate_host_service_error always raises
            raise  # pragma: no cover

    async def _call_host_service_get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        cancellation_token=None,
    ) -> dict[str, Any]:
        """Make GET request to host service using AsyncServiceAdapter."""
        if not self.use_host_service:
            raise RuntimeError("Host service not enabled")

        # Ensure HTTP client is initialized
        await self._ensure_client_initialized()

        try:
            return await AsyncServiceAdapter._call_host_service_get(
                self, endpoint, params, cancellation_token
            )
        except Exception as e:
            # Translate AsyncServiceAdapter errors to TrainingProvider errors for compatibility
            self._translate_host_service_error(e)
            # This line should never be reached since _translate_host_service_error always raises
            raise  # pragma: no cover

    def _translate_host_service_error(self, error: Exception) -> None:
        """Translate AsyncServiceAdapter errors to TrainingProvider errors for compatibility."""
        from ktrdr.async_infrastructure.service_adapter import (
            HostServiceConnectionError,
            HostServiceError,
            HostServiceTimeoutError,
        )

        if isinstance(error, HostServiceConnectionError):
            raise TrainingProviderConnectionError(
                f"Host service connection failed: {error.message}", provider="Training"
            ) from error
        elif isinstance(error, HostServiceTimeoutError):
            raise TrainingProviderConnectionError(
                f"Host service timeout: {error.message}", provider="Training"
            ) from error
        elif isinstance(error, HostServiceError):
            raise TrainingProviderError(
                f"Host service error: {error.message}", provider="Training"
            ) from error
        else:
            raise TrainingProviderError(
                f"Host service communication error: {str(error)}", provider="Training"
            ) from error

    async def train_multi_symbol_strategy(
        self,
        strategy_config_path: str,
        symbols: list[str],
        timeframes: list[str],
        start_date: str,
        end_date: str,
        validation_split: float = 0.2,
        data_mode: str = "local",
        progress_callback=None,
        cancellation_token: CancellationToken | None = None,
        training_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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

                # Build training configuration from provided config dict
                training_configuration = {
                    "validation_split": validation_split,
                }

                # Merge in additional training config fields (e.g., epochs, batch_size)
                if training_config:
                    training_configuration.update(training_config)

                # Load strategy YAML file
                with open(strategy_config_path) as f:
                    strategy_yaml_content = f.read()

                response = await self._call_host_service_post(
                    "/training/start",
                    data={
                        "strategy_yaml": strategy_yaml_content,
                        # Runtime overrides
                        "symbols": symbols,
                        "timeframes": timeframes,
                        "start_date": start_date,
                        "end_date": end_date,
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
                # TrainingAdapter is host-service-only
                raise TrainingProviderError(
                    "TrainingAdapter does not support local training. "
                    "This code path should not be reached. "
                    "Use LocalTrainingOrchestrator for local training.",
                    provider="Training",
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
            ) from e

    async def get_training_status(self, session_id: str) -> dict[str, Any]:
        """Get status of a training session (host service only)."""
        if not self.use_host_service:
            raise TrainingProviderError(
                "Status checking only available for host service mode"
            )

        return await self._call_host_service_get(f"/training/status/{session_id}")

    async def stop_training(self, session_id: str) -> dict[str, Any]:
        """Stop a training session (host service only)."""
        if not self.use_host_service:
            raise TrainingProviderError(
                "Training stopping only available for host service mode"
            )

        return await self._call_host_service_post(
            "/training/stop", {"session_id": session_id, "save_checkpoint": True}
        )

    def get_statistics(self) -> dict[str, Any]:
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

"""
Training Manager

This module provides the TrainingManager class for managing training operations
with automatic routing between local training and training host service.

The manager handles:
- Environment variable configuration (USE_TRAINING_HOST_SERVICE)
- Training adapter initialization and management
- Simple interface for training operations
"""

import os
from typing import Any

from ktrdr.logging import get_logger
from ktrdr.managers.base import ServiceOrchestrator

from .training_adapter import TrainingAdapter

logger = get_logger(__name__)


class TrainingManager(ServiceOrchestrator[TrainingAdapter]):
    """
    Manager for training operations with automatic host service routing.

    This manager mirrors the DataManager pattern for IB integration, providing
    a clean interface for training operations while handling the complexity of
    routing between local training and training host service.
    """

    def __init__(self):
        """Initialize training manager with environment-based configuration."""
        # Initialize ServiceOrchestrator base class
        super().__init__()

        # training_adapter is now available through self.adapter (from ServiceOrchestrator)
        # Keep old attribute name for backward compatibility
        self.training_adapter = self.adapter

    def _initialize_adapter(self) -> TrainingAdapter:
        """Initialize training adapter based on environment variables."""
        try:
            # Environment variable override for enabled flag (quick toggle)
            env_enabled = os.getenv("USE_TRAINING_HOST_SERVICE", "").lower()

            if env_enabled in ("true", "1", "yes"):
                use_host_service = True
                # Use environment URL if provided
                host_service_url = os.getenv(
                    "TRAINING_HOST_SERVICE_URL", "http://localhost:5002"
                )

                logger.info(
                    f"Training integration enabled using host service at {host_service_url}"
                )

            elif env_enabled in ("false", "0", "no"):
                use_host_service = False
                host_service_url = None

                logger.info("Training integration enabled (local training)")

            else:
                # Default to local training if not explicitly set
                use_host_service = False
                host_service_url = None

                logger.info("Training integration enabled (local training - default)")

            # Initialize TrainingAdapter with configuration
            return TrainingAdapter(
                use_host_service=use_host_service, host_service_url=host_service_url
            )

        except Exception as e:
            logger.warning(
                f"Failed to load training host service config, using local training: {e}"
            )
            # Fallback to local training
            return TrainingAdapter(use_host_service=False)

    def _get_service_name(self) -> str:
        """Get the service name for logging and configuration."""
        return "Training"

    def _get_default_host_url(self) -> str:
        """Get the default host service URL."""
        return "http://localhost:5002"

    def _get_env_var_prefix(self) -> str:
        """Get environment variable prefix."""
        return "TRAINING"

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
    ) -> dict[str, Any]:
        """
        Train a multi-symbol strategy using the configured adapter.

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
        # Get current cancellation token from ServiceOrchestrator
        cancellation_token = self.get_current_cancellation_token()

        return await self.training_adapter.train_multi_symbol_strategy(
            strategy_config_path=strategy_config_path,
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
            data_mode=data_mode,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token,
        )

    async def get_training_status(self, session_id: str) -> dict[str, Any]:
        """
        Get status of a training session (host service only).

        Args:
            session_id: Training session ID

        Returns:
            Training status information
        """
        return await self.training_adapter.get_training_status(session_id)

    async def stop_training(self, session_id: str) -> dict[str, Any]:
        """
        Stop a training session (host service only).

        Args:
            session_id: Training session ID

        Returns:
            Stop operation result
        """
        return await self.training_adapter.stop_training(session_id)

    def get_adapter_statistics(self) -> dict[str, Any]:
        """Get training adapter usage statistics."""
        return self.training_adapter.get_statistics()

    # Note: is_using_host_service and get_host_service_url are inherited from ServiceOrchestrator
    # The ServiceOrchestrator base class provides these methods using self.adapter

    # Note: get_configuration_info is inherited from ServiceOrchestrator
    # The ServiceOrchestrator base class provides this method with training-specific details

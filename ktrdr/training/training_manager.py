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
from typing import Dict, List, Optional, Any
from pathlib import Path

from ktrdr.logging import get_logger
from .training_adapter import TrainingAdapter

logger = get_logger(__name__)


class TrainingManager:
    """
    Manager for training operations with automatic host service routing.

    This manager mirrors the DataManager pattern for IB integration, providing
    a clean interface for training operations while handling the complexity of
    routing between local training and training host service.
    """

    def __init__(self):
        """Initialize training manager with environment-based configuration."""

        # Simple environment variable handling (mirror IB pattern exactly)
        self.training_adapter = self._initialize_training_adapter()

    def _initialize_training_adapter(self) -> TrainingAdapter:
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
        return await self.training_adapter.train_multi_symbol_strategy(
            strategy_config_path=strategy_config_path,
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
            data_mode=data_mode,
            progress_callback=progress_callback,
        )

    async def get_training_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get status of a training session (host service only).

        Args:
            session_id: Training session ID

        Returns:
            Training status information
        """
        return await self.training_adapter.get_training_status(session_id)

    async def stop_training(self, session_id: str) -> Dict[str, Any]:
        """
        Stop a training session (host service only).

        Args:
            session_id: Training session ID

        Returns:
            Stop operation result
        """
        return await self.training_adapter.stop_training(session_id)

    def get_adapter_statistics(self) -> Dict[str, Any]:
        """Get training adapter usage statistics."""
        return self.training_adapter.get_statistics()

    def is_using_host_service(self) -> bool:
        """Check if training manager is configured to use host service."""
        return self.training_adapter.use_host_service

    def get_host_service_url(self) -> Optional[str]:
        """Get host service URL if using host service."""
        if self.training_adapter.use_host_service:
            return self.training_adapter.host_service_url
        return None

    def get_configuration_info(self) -> Dict[str, Any]:
        """Get current configuration information."""
        return {
            "mode": "host_service" if self.is_using_host_service() else "local",
            "host_service_url": self.get_host_service_url(),
            "environment_variables": {
                "USE_TRAINING_HOST_SERVICE": os.getenv("USE_TRAINING_HOST_SERVICE"),
                "TRAINING_HOST_SERVICE_URL": os.getenv("TRAINING_HOST_SERVICE_URL"),
            },
            "statistics": self.get_adapter_statistics(),
        }

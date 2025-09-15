"""
Training Manager - DummyService Pattern Implementation

This module implements TrainingManager following the exact DummyService pattern
from ktrdr/api/services/dummy_service.py, providing perfect UX with zero boilerplate.

The manager inherits ServiceOrchestrator[TrainingAdapter] and provides:
- Automatic operations tracking via operations service integration
- Structured progress reporting with TrainingProgressRenderer
- Unified cancellation support coordination
- Environment-based configuration (USE_TRAINING_HOST_SERVICE)
- Training adapter initialization and management
- Zero boilerplate - ServiceOrchestrator handles ALL async complexity

Key Features (DummyService Pattern):
- ServiceOrchestrator handles ALL async complexity automatically
- Training methods are single start_managed_operation() calls
- Domain logic in clean _run_*_async() methods with ServiceOrchestrator cancellation
- Perfect UX with smooth progress and instant cancellation
- API response formatting for CLI compatibility
"""

import os
from typing import Any

from ktrdr.logging import get_logger
from ktrdr.managers.base import ServiceOrchestrator

from .training_adapter import TrainingAdapter

logger = get_logger(__name__)


class TrainingManager(ServiceOrchestrator[TrainingAdapter]):
    """
    Training manager following exact DummyService pattern.

    This service demonstrates the ServiceOrchestrator pattern for training:
    - ServiceOrchestrator handles ALL complexity (operations, progress, cancellation)
    - Training methods are just one call to ServiceOrchestrator
    - Domain logic is clean and focused
    - Perfect UX with zero effort

    This follows exactly the same pattern as DummyService and DataManager.
    """

    def _initialize_adapter(self) -> TrainingAdapter:
        """
        Initialize training adapter based on environment variables.

        Required by ServiceOrchestrator - follows same pattern as DataManager.
        """
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
        """Return service name for logging and configuration."""
        return "Training"

    def _get_default_host_url(self) -> str:
        """Default host URL for training service."""
        return "http://localhost:5002"

    def _get_env_var_prefix(self) -> str:
        """Environment variable prefix for training service."""
        return "TRAINING"

    async def train_multi_symbol_strategy_async(
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
        Train multi-symbol strategy with full ServiceOrchestrator management.

        ServiceOrchestrator handles ALL complexity:
        - Operation creation & tracking via operations service
        - Progress reporting integration with TrainingProgressRenderer
        - Cancellation support coordination
        - API response formatting for CLI compatibility
        - Background task execution management

        Args:
            strategy_config_path: Path to strategy configuration file
            symbols: List of trading symbols
            timeframes: List of timeframes
            start_date: Start date for training data
            end_date: End date for training data
            validation_split: Validation split ratio
            data_mode: Data loading mode
            progress_callback: Optional progress callback (for backward compatibility)

        Returns:
            API response dict with operation_id for async tracking:
            {
                "operation_id": "op_xxx",
                "status": "started",
                "message": "Started train_multi_symbol_strategy operation"
            }
        """
        logger.info(f"Starting train_multi_symbol_strategy for {symbols} on {timeframes} via ServiceOrchestrator")

        # ServiceOrchestrator handles EVERYTHING - one method call like DummyService!
        return await self.start_managed_operation(
            operation_name="train_multi_symbol_strategy",
            operation_type="TRAINING",
            operation_func=self._run_training_async,
            # Pass parameters to domain logic
            strategy_config_path=strategy_config_path,
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
            data_mode=data_mode,
            metadata={
                "symbol": symbols[0] if symbols else "N/A",
                "timeframe": timeframes[0] if timeframes else "N/A",
                "mode": data_mode,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    async def _run_training_async(
        self,
        strategy_config_path: str,
        symbols: list[str],
        timeframes: list[str],
        start_date: str,
        end_date: str,
        validation_split: float = 0.2,
        data_mode: str = "local",
        **kwargs,
    ) -> dict[str, Any]:
        """
        The actual training work - clean domain logic with cancellation support.

        This method demonstrates the perfect pattern for domain logic:
        - Simple, focused implementation
        - Uses ServiceOrchestrator's cancellation system
        - Reports progress via ServiceOrchestrator's progress system
        - Clean error handling with meaningful status returns
        - No async infrastructure code - just domain logic

        ServiceOrchestrator provides all the infrastructure:
        - Progress tracking and reporting
        - Cancellation token management
        - Background task coordination
        - API response formatting

        Args:
            strategy_config_path: Path to strategy configuration file
            symbols: List of trading symbols
            timeframes: List of timeframes
            start_date: Start date for training data
            end_date: End date for training data
            validation_split: Validation split ratio
            data_mode: Data loading mode
            **kwargs: Additional parameters

        Returns:
            Results dict with status, progress info, and meaningful messages
        """
        logger.debug("Starting training domain logic")

        # ServiceOrchestrator provides cancellation - just check it!
        cancellation_token = self.get_current_cancellation_token()

        logger.info(
            f"Training {len(symbols)} symbols on {len(timeframes)} timeframes "
            f"from {start_date} to {end_date}"
        )

        try:
            # Use existing TrainingAdapter with ServiceOrchestrator cancellation
            result = await self.adapter.train_multi_symbol_strategy(
                strategy_config_path=strategy_config_path,
                symbols=symbols,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date,
                validation_split=validation_split,
                data_mode=data_mode,
                progress_callback=self.update_operation_progress,
                cancellation_token=cancellation_token,
            )

            # Check for cancellation after training
            if cancellation_token and cancellation_token.is_cancelled():
                logger.info("Training was cancelled")
                return {
                    "status": "cancelled",
                    "message": "Training was cancelled",
                    "symbols_processed": symbols,
                }

            # Format API response like DataManager does
            logger.info("Training completed successfully")
            return self._format_training_api_response(result)

        except Exception as e:
            # Check if cancellation caused the error
            if cancellation_token and cancellation_token.is_cancelled():
                logger.info("Training cancelled due to cancellation request")
                return {
                    "status": "cancelled",
                    "message": "Training cancelled",
                    "error": str(e),
                }
            else:
                logger.error(f"Training failed: {e}")
                raise

    def _format_training_api_response(self, adapter_result: dict[str, Any]) -> dict[str, Any]:
        """
        Format adapter response for API compatibility.

        Args:
            adapter_result: Raw result from TrainingAdapter

        Returns:
            Formatted response for API consumption
        """
        # Preserve all training results and add API formatting
        formatted_result = {
            "status": "success",
            **adapter_result,
        }

        # Add ServiceOrchestrator metadata
        formatted_result["service"] = "Training"
        formatted_result["training_completed"] = True

        return formatted_result

    async def get_training_status(self, session_id: str) -> dict[str, Any]:
        """
        Get status of a training session (host service only).

        Args:
            session_id: Training session ID

        Returns:
            Training status information
        """
        return await self.adapter.get_training_status(session_id)

    async def stop_training(self, session_id: str) -> dict[str, Any]:
        """
        Stop a training session (host service only).

        Args:
            session_id: Training session ID

        Returns:
            Stop operation result
        """
        return await self.adapter.stop_training(session_id)

    # Note: ServiceOrchestrator provides get_adapter_statistics(), is_using_host_service(),
    # get_host_service_url(), and get_configuration_info() automatically.
    # No need to reimplement them - they work with self.adapter automatically.

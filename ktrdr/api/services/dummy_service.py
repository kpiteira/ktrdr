"""
DummyService - The Perfect Async Service Reference Implementation.

This module implements DummyService as the ultimate demonstration of how
ServiceOrchestrator should work. It shows the "most awesome yet simple"
async service that eliminates ALL complexity through ServiceOrchestrator.

Key Features:
- ServiceOrchestrator handles ALL async complexity
- Zero boilerplate - minimal code with maximum power
- Perfect UX - smooth progress and instant cancellation
- Clean domain logic - just a simple loop with progress
- Template pattern - exactly how all future services should look

This is THE reference implementation for the ServiceOrchestrator pattern.
"""

import asyncio
from typing import Any

from ktrdr.logging import get_logger
from ktrdr.managers.base import ServiceOrchestrator

logger = get_logger(__name__)


class DummyService(ServiceOrchestrator[None]):
    """
    The perfect async service - simple, clean, powerful.

    This service demonstrates the ServiceOrchestrator pattern at its finest:
    - ServiceOrchestrator handles ALL complexity (operations, progress, cancellation)
    - Service methods are just one call to ServiceOrchestrator
    - Domain logic is clean and focused
    - Perfect UX with zero effort

    This is exactly how all future async services should be built.
    """

    def _initialize_adapter(self) -> None:
        """No adapter needed for dummy service - it's just a demonstration."""
        return None

    def _get_service_name(self) -> str:
        """Return service name for logging and configuration."""
        return "DummyService"

    def _get_default_host_url(self) -> str:
        """Default host URL (not used for dummy service)."""
        return "http://localhost:8000"

    def _get_env_var_prefix(self) -> str:
        """Environment variable prefix (not used for dummy service)."""
        return "DUMMY"

    async def start_dummy_task(self) -> dict[str, Any]:
        """
        Start dummy task with full ServiceOrchestrator management.

        ServiceOrchestrator handles ALL complexity:
        - Operation creation & tracking via operations service
        - Progress reporting integration
        - Cancellation support coordination
        - API response formatting for CLI compatibility
        - Background task execution management

        Simple operation: 200 seconds duration (100 iterations, 2 seconds each)
        No parameters needed - this is a demonstration service.

        Returns:
            API response dict with operation_id for async tracking:
            {
                "operation_id": "op_xxx",
                "status": "started",
                "message": "Started dummy_task operation"
            }
        """
        logger.info("Starting awesome dummy task via ServiceOrchestrator")

        # ServiceOrchestrator handles EVERYTHING - one method call!
        return await self.start_managed_operation(
            operation_name="dummy_task",
            operation_type="DUMMY",  # For OperationType enum
            operation_func=self._run_dummy_task_async,
        )

    def run_dummy_task_sync(self) -> dict[str, Any]:
        """
        Run dummy task synchronously (for CLI direct usage).

        ServiceOrchestrator still handles progress and cancellation,
        but returns results directly instead of operation tracking.
        Perfect for CLI commands that want immediate feedback.

        Simple operation: 200 seconds duration (100 iterations, 2 seconds each)
        No parameters needed - this is a demonstration service.

        Returns:
            Direct results dict from the operation:
            {
                "status": "success",
                "iterations_completed": 100,
                "total_duration_seconds": 200,
                "message": "Completed all 100 iterations!"
            }
        """
        logger.info("Running dummy task synchronously via ServiceOrchestrator")

        # ServiceOrchestrator handles sync execution with progress/cancellation
        return self.run_sync_operation(
            operation_name="dummy_task", operation_func=self._run_dummy_task_async
        )

    async def _run_dummy_task_async(self) -> dict[str, Any]:
        """
        The actual work - clean domain logic with cancellation support.

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

        Returns:
            Results dict with status, progress info, and meaningful messages
        """
        logger.debug("Starting dummy task domain logic")

        duration_seconds = 200  # Simple: hardcoded 200s as per specification
        iterations = duration_seconds // 2  # 2 seconds per iteration = 100 iterations

        logger.info(
            f"Dummy task: {iterations} iterations over {duration_seconds} seconds"
        )

        for i in range(iterations):
            # ServiceOrchestrator provides cancellation - just check it!
            cancellation_token = self.get_current_cancellation_token()
            if cancellation_token and cancellation_token.is_cancelled():
                logger.info(f"Dummy task cancelled after {i} iterations")
                return {
                    "status": "cancelled",
                    "iterations_completed": i,
                    "message": f"Stopped after {i} iterations",
                }

            # Do the actual work (simulate with sleep)
            await asyncio.sleep(2)  # 2 seconds per iteration as specified

            # Report progress via ServiceOrchestrator's progress system
            self.update_operation_progress(
                step=i + 1,
                message=f"Working hard on iteration {i+1}!",
                items_processed=i + 1,
                context={
                    "current_step": f"Iteration {i+1}/{iterations}",
                    "current_item": f"Processing step {i+1}",
                },
            )

            logger.debug(f"Completed iteration {i+1}/{iterations}")

        # Success! Clean completion
        logger.info(f"Dummy task completed successfully: {iterations} iterations")
        return {
            "status": "success",
            "iterations_completed": iterations,
            "total_duration_seconds": duration_seconds,
            "message": f"Completed all {iterations} iterations!",
        }

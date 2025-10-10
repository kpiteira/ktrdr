"""Tests for the local training runner orchestration.

REFACTORED: LocalTrainingRunner is now a thin wrapper around LocalTrainingOrchestrator.
These tests verify the wrapper delegates correctly. More detailed orchestrator tests
are in tests/integration/training/test_local_orchestrator.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.api.models.operations import OperationMetadata
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.local_runner import LocalTrainingRunner
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.async_infrastructure.cancellation import CancellationError
from ktrdr.async_infrastructure.progress import GenericProgressManager


class _MutableToken:
    """Simple cancellation token for testing."""

    def __init__(self) -> None:
        self.cancelled = False

    def is_cancelled(self) -> bool:
        return self.cancelled


def _make_context(
    total_epochs: int = 2, total_batches: int | None = 10
) -> TrainingOperationContext:
    metadata = OperationMetadata(
        symbol="EURUSD",
        timeframe="1h",
        mode="local",
        parameters={"operation_name": "training", "service_name": "TrainingService"},
    )
    return TrainingOperationContext(
        operation_id="op-456",
        strategy_name="sample",
        strategy_path=Path("/tmp/sample.yaml"),
        strategy_config={},
        symbols=["EURUSD"],
        timeframes=["1h"],
        start_date=None,
        end_date=None,
        training_config={"epochs": total_epochs},
        analytics_enabled=False,
        use_host_service=False,
        training_mode="local",
        total_epochs=total_epochs,
        total_batches=total_batches,
        metadata=metadata,
    )


@pytest.mark.asyncio
async def test_local_runner_delegates_to_orchestrator():
    """Test that LocalTrainingRunner delegates to LocalTrainingOrchestrator."""
    manager = GenericProgressManager(callback=lambda _: None)
    manager.start_operation("training", total_steps=2)

    context = _make_context(total_epochs=2, total_batches=10)
    bridge = TrainingProgressBridge(context=context, progress_manager=manager)
    token = _MutableToken()

    # Create runner
    runner = LocalTrainingRunner(
        context=context,
        progress_bridge=bridge,
        cancellation_token=token,
    )

    # Mock the orchestrator's run method
    mock_result = {
        "model_path": "models/test.pth",
        "training_metrics": {"epochs_completed": 2},
        "session_info": {"operation_id": "op-456"},
    }

    with patch.object(runner._orchestrator, "run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        # Run training
        result = await runner.run()

        # Verify orchestrator was called
        mock_run.assert_called_once()

        # Verify result was returned
        assert result == mock_result
        assert result["training_metrics"]["epochs_completed"] == 2


@pytest.mark.asyncio
async def test_local_runner_propagates_cancellation():
    """Test that LocalTrainingRunner propagates cancellation from orchestrator."""
    manager = GenericProgressManager(callback=lambda _: None)
    manager.start_operation("training", total_steps=1)

    context = _make_context(total_epochs=1, total_batches=1)
    token = _MutableToken()
    token.cancelled = True

    bridge = TrainingProgressBridge(
        context=context,
        progress_manager=manager,
        cancellation_token=token,
    )

    runner = LocalTrainingRunner(
        context=context,
        progress_bridge=bridge,
        cancellation_token=token,
    )

    # Mock orchestrator to raise CancellationError
    with patch.object(runner._orchestrator, "run", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = CancellationError("Training cancelled")

        # Verify CancellationError is propagated
        with pytest.raises(CancellationError):
            await runner.run()

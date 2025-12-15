"""Unit tests for TrainingWorkerAdapter.

Tests the adapter that connects the agent orchestrator to the
existing TrainingService for real model training.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def mock_operations_service():
    """Create a mock OperationsService."""
    return AsyncMock()


@pytest.fixture
def mock_training_service():
    """Create a mock TrainingService."""
    return AsyncMock()


@pytest.fixture
def sample_strategy_yaml(tmp_path):
    """Create a sample strategy YAML file for testing."""
    strategy_content = """
name: "test_momentum_v1"
description: "Test strategy for unit tests"
training_data:
  symbols:
    mode: "multi_symbol"
    list:
      - "AAPL"
      - "MSFT"
  timeframes:
    mode: "multi_timeframe"
    list:
      - "1h"
      - "4h"
model:
  training:
    epochs: 50
    batch_size: 32
"""
    strategy_file = tmp_path / "test_strategy.yaml"
    strategy_file.write_text(strategy_content)
    return str(strategy_file)


def _make_operation(
    status: OperationStatus,
    result_summary: dict | None = None,
    error_message: str | None = None,
    progress: OperationProgress | None = None,
) -> OperationInfo:
    """Helper to create mock OperationInfo objects."""
    from datetime import datetime, timezone

    return OperationInfo(
        operation_id="op_training_test_123",
        operation_type=OperationType.TRAINING,
        status=status,
        created_at=datetime.now(timezone.utc),
        result_summary=result_summary or {},
        error_message=error_message,
        progress=progress or OperationProgress(),
        metadata=OperationMetadata(),
    )


class TestTrainingWorkerAdapter:
    """Tests for TrainingWorkerAdapter."""

    @pytest.mark.asyncio
    async def test_polls_until_completed_returns_metrics(
        self, mock_operations_service, mock_training_service, sample_strategy_yaml
    ):
        """Polls until COMPLETED status returns metrics."""
        from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter

        # Set up training service to return operation ID
        mock_training_service.start_training.return_value = {
            "operation_id": "op_training_test_123",
            "success": True,
        }

        # Set up operations service to return RUNNING then COMPLETED
        mock_operations_service.get_operation.side_effect = [
            _make_operation(OperationStatus.RUNNING),
            _make_operation(
                OperationStatus.COMPLETED,
                result_summary={
                    "accuracy": 0.65,
                    "final_loss": 0.35,
                    "initial_loss": 0.85,
                    "model_path": "/app/models/test_momentum_v1/model.pt",
                },
            ),
        ]

        adapter = TrainingWorkerAdapter(
            operations_service=mock_operations_service,
            training_service=mock_training_service,
        )
        # Use short poll interval for tests
        adapter.POLL_INTERVAL = 0.01

        result = await adapter.run(
            parent_operation_id="op_agent_research_123",
            strategy_path=sample_strategy_yaml,
        )

        assert result["success"] is True
        assert result["accuracy"] == 0.65
        assert result["final_loss"] == 0.35
        assert result["initial_loss"] == 0.85
        assert result["model_path"] == "/app/models/test_momentum_v1/model.pt"

    @pytest.mark.asyncio
    async def test_raises_worker_error_on_failed_status(
        self, mock_operations_service, mock_training_service, sample_strategy_yaml
    ):
        """Raises WorkerError on FAILED status."""
        from ktrdr.agents.workers.training_adapter import (
            TrainingWorkerAdapter,
            WorkerError,
        )

        mock_training_service.start_training.return_value = {
            "operation_id": "op_training_test_123",
            "success": True,
        }

        mock_operations_service.get_operation.return_value = _make_operation(
            OperationStatus.FAILED,
            error_message="Training failed: GPU out of memory",
        )

        adapter = TrainingWorkerAdapter(
            operations_service=mock_operations_service,
            training_service=mock_training_service,
        )
        adapter.POLL_INTERVAL = 0.01

        with pytest.raises(WorkerError) as exc_info:
            await adapter.run(
                parent_operation_id="op_agent_research_123",
                strategy_path=sample_strategy_yaml,
            )

        assert "Training failed" in str(exc_info.value)
        assert "GPU out of memory" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_cancelled_error_on_cancelled_status(
        self, mock_operations_service, mock_training_service, sample_strategy_yaml
    ):
        """Raises CancelledError on CANCELLED status."""
        from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter

        mock_training_service.start_training.return_value = {
            "operation_id": "op_training_test_123",
            "success": True,
        }

        mock_operations_service.get_operation.return_value = _make_operation(
            OperationStatus.CANCELLED,
        )

        adapter = TrainingWorkerAdapter(
            operations_service=mock_operations_service,
            training_service=mock_training_service,
        )
        adapter.POLL_INTERVAL = 0.01

        with pytest.raises(asyncio.CancelledError):
            await adapter.run(
                parent_operation_id="op_agent_research_123",
                strategy_path=sample_strategy_yaml,
            )

    @pytest.mark.asyncio
    async def test_passes_strategy_config_to_training_service(
        self, mock_operations_service, mock_training_service, sample_strategy_yaml
    ):
        """Passes strategy config to TrainingService."""
        from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter

        mock_training_service.start_training.return_value = {
            "operation_id": "op_training_test_123",
            "success": True,
        }

        mock_operations_service.get_operation.return_value = _make_operation(
            OperationStatus.COMPLETED,
            result_summary={
                "accuracy": 0.65,
                "final_loss": 0.35,
                "initial_loss": 0.85,
                "model_path": "/app/models/test/model.pt",
            },
        )

        adapter = TrainingWorkerAdapter(
            operations_service=mock_operations_service,
            training_service=mock_training_service,
        )
        adapter.POLL_INTERVAL = 0.01

        await adapter.run(
            parent_operation_id="op_agent_research_123",
            strategy_path=sample_strategy_yaml,
        )

        # Verify TrainingService was called with correct params from YAML
        mock_training_service.start_training.assert_called_once()
        call_kwargs = mock_training_service.start_training.call_args.kwargs

        assert call_kwargs["strategy_name"] == "test_momentum_v1"
        assert call_kwargs["symbols"] == ["AAPL", "MSFT"]
        assert call_kwargs["timeframes"] == ["1h", "4h"]

    @pytest.mark.asyncio
    async def test_cancels_child_on_parent_cancellation(
        self, mock_operations_service, mock_training_service, sample_strategy_yaml
    ):
        """Cancels training operation if parent is cancelled."""
        from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter

        mock_training_service.start_training.return_value = {
            "operation_id": "op_training_test_123",
            "success": True,
        }

        # Make get_operation hang so we can cancel
        async def slow_get_operation(op_id):
            await asyncio.sleep(10)
            return _make_operation(OperationStatus.RUNNING)

        mock_operations_service.get_operation.side_effect = slow_get_operation

        adapter = TrainingWorkerAdapter(
            operations_service=mock_operations_service,
            training_service=mock_training_service,
        )
        adapter.POLL_INTERVAL = 0.01

        # Start the run and then cancel it
        task = asyncio.create_task(
            adapter.run(
                parent_operation_id="op_agent_research_123",
                strategy_path=sample_strategy_yaml,
            )
        )

        await asyncio.sleep(0.05)  # Let it start
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Verify cancel was called on the child operation
        mock_operations_service.cancel_operation.assert_called_once_with(
            "op_training_test_123", "Parent cancelled"
        )

    @pytest.mark.asyncio
    async def test_returns_training_op_id_in_result(
        self, mock_operations_service, mock_training_service, sample_strategy_yaml
    ):
        """Returns training_op_id in result."""
        from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter

        mock_training_service.start_training.return_value = {
            "operation_id": "op_training_test_123",
            "success": True,
        }

        mock_operations_service.get_operation.return_value = _make_operation(
            OperationStatus.COMPLETED,
            result_summary={
                "accuracy": 0.65,
                "final_loss": 0.35,
                "initial_loss": 0.85,
                "model_path": "/app/models/test/model.pt",
            },
        )

        adapter = TrainingWorkerAdapter(
            operations_service=mock_operations_service,
            training_service=mock_training_service,
        )
        adapter.POLL_INTERVAL = 0.01

        result = await adapter.run(
            parent_operation_id="op_agent_research_123",
            strategy_path=sample_strategy_yaml,
        )

        assert result["training_op_id"] == "op_training_test_123"


class TestTrainingWorkerAdapterEdgeCases:
    """Edge case tests for TrainingWorkerAdapter."""

    @pytest.mark.asyncio
    async def test_handles_missing_optional_config_fields(
        self, mock_operations_service, mock_training_service, tmp_path
    ):
        """Uses defaults for missing optional config fields."""
        from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter

        # Minimal strategy with no training_data section
        strategy_content = """
name: "minimal_test"
description: "Minimal test strategy"
"""
        strategy_file = tmp_path / "minimal.yaml"
        strategy_file.write_text(strategy_content)

        mock_training_service.start_training.return_value = {
            "operation_id": "op_training_test_123",
            "success": True,
        }

        mock_operations_service.get_operation.return_value = _make_operation(
            OperationStatus.COMPLETED,
            result_summary={
                "accuracy": 0.65,
                "final_loss": 0.35,
                "initial_loss": 0.85,
                "model_path": "/app/models/test/model.pt",
            },
        )

        adapter = TrainingWorkerAdapter(
            operations_service=mock_operations_service,
            training_service=mock_training_service,
        )
        adapter.POLL_INTERVAL = 0.01

        result = await adapter.run(
            parent_operation_id="op_agent_research_123",
            strategy_path=str(strategy_file),
        )

        # Should use defaults
        call_kwargs = mock_training_service.start_training.call_args.kwargs
        assert call_kwargs["strategy_name"] == "minimal_test"
        # Defaults for symbols and timeframes
        assert "symbols" in call_kwargs
        assert "timeframes" in call_kwargs
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_logs_progress_during_polling(
        self, mock_operations_service, mock_training_service, sample_strategy_yaml
    ):
        """Logs progress information during polling."""
        from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter

        mock_training_service.start_training.return_value = {
            "operation_id": "op_training_test_123",
            "success": True,
        }

        # Return progress updates then completion
        mock_operations_service.get_operation.side_effect = [
            _make_operation(
                OperationStatus.RUNNING,
                progress=OperationProgress(percentage=25, current_step="Epoch 5/20"),
            ),
            _make_operation(
                OperationStatus.RUNNING,
                progress=OperationProgress(percentage=75, current_step="Epoch 15/20"),
            ),
            _make_operation(
                OperationStatus.COMPLETED,
                result_summary={
                    "accuracy": 0.65,
                    "final_loss": 0.35,
                    "initial_loss": 0.85,
                    "model_path": "/app/models/test/model.pt",
                },
            ),
        ]

        adapter = TrainingWorkerAdapter(
            operations_service=mock_operations_service,
            training_service=mock_training_service,
        )
        adapter.POLL_INTERVAL = 0.01

        result = await adapter.run(
            parent_operation_id="op_agent_research_123",
            strategy_path=sample_strategy_yaml,
        )

        assert result["success"] is True
        # Verify all polling calls happened
        assert mock_operations_service.get_operation.call_count == 3

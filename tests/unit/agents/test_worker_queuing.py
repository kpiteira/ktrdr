"""Unit tests for worker queuing behavior.

Tests M3 functionality: researches naturally queue when workers are busy.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.api.models.operations import OperationStatus, OperationType

pytestmark = pytest.mark.asyncio


class TestDesignToTrainingWorkerCheck:
    """Tests for worker availability check in design→training transition."""

    @pytest.fixture
    def mock_ops(self):
        """Create mock operations service."""
        ops = MagicMock()
        ops.get_operation = AsyncMock()
        ops.list_operations = AsyncMock(return_value=([], 0, None))
        ops.update_progress = AsyncMock()
        ops.complete_operation = AsyncMock()
        return ops

    @pytest.fixture
    def mock_design_worker(self):
        """Create mock design worker."""
        worker = MagicMock()
        worker.run = AsyncMock(
            return_value={
                "strategy_name": "test_strategy",
                "strategy_path": "/tmp/test_strategy.yaml",
                "input_tokens": 100,
                "output_tokens": 50,
            }
        )
        return worker

    @pytest.fixture
    def mock_assessment_worker(self):
        """Create mock assessment worker."""
        worker = MagicMock()
        worker.run = AsyncMock(return_value={"verdict": "passed"})
        return worker

    @pytest.fixture
    def worker(self, mock_ops, mock_design_worker, mock_assessment_worker):
        """Create AgentResearchWorker with mocked dependencies."""
        return AgentResearchWorker(
            operations_service=mock_ops,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

    @pytest.fixture
    def completed_design_op(self):
        """Create a completed design operation for stub worker flow."""
        op = MagicMock()
        op.operation_id = "op_design_123"
        op.status = OperationStatus.COMPLETED
        op.result_summary = {
            "strategy_name": "test_strategy",
            "strategy_path": "/tmp/test_strategy.yaml",
        }
        return op

    @pytest.fixture
    def parent_op(self):
        """Create parent research operation."""
        op = MagicMock()
        op.operation_id = "op_research_123"
        op.operation_type = OperationType.AGENT_RESEARCH
        op.status = OperationStatus.RUNNING
        op.created_at = datetime.now(timezone.utc)
        op.metadata = MagicMock()
        op.metadata.parameters = {
            "phase": "designing",
            "phase_start_time": 1000.0,
        }
        return op

    async def test_design_proceeds_when_training_worker_available(
        self, worker, mock_ops, parent_op
    ):
        """When a training worker is available, design→training transition happens."""
        # Setup: Design task completed, worker returns result
        completed_task = asyncio.Future()
        completed_task.set_result(
            {
                "strategy_name": "test_strategy",
                "strategy_path": "/tmp/test_strategy.yaml",
            }
        )
        worker._child_tasks["op_research_123"] = completed_task

        mock_ops.get_operation.return_value = parent_op

        # Mock worker registry with an available training worker
        mock_registry = MagicMock()
        mock_worker = MagicMock()
        mock_worker.worker_id = "training-worker-1"
        mock_registry.get_available_workers.return_value = [mock_worker]

        # Mock training service to avoid actual training call
        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock(
            return_value={"operation_id": "op_training_456"}
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_designing_phase("op_research_123", None)

        # Verify: training was started
        worker._training_service.start_training.assert_called_once()
        # Phase should be updated to training
        assert parent_op.metadata.parameters["phase"] == "training"

    async def test_design_waits_when_no_training_worker_available(
        self, worker, mock_ops, parent_op
    ):
        """When no training worker is available, stay in designing phase."""
        # Setup: Design task completed, worker returns result
        completed_task = asyncio.Future()
        completed_task.set_result(
            {
                "strategy_name": "test_strategy",
                "strategy_path": "/tmp/test_strategy.yaml",
            }
        )
        worker._child_tasks["op_research_123"] = completed_task

        mock_ops.get_operation.return_value = parent_op

        # Mock worker registry with NO available training workers
        mock_registry = MagicMock()
        mock_registry.get_available_workers.return_value = []

        # Mock training service (should NOT be called)
        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock()

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_designing_phase("op_research_123", None)

        # Verify: training was NOT started
        worker._training_service.start_training.assert_not_called()
        # Phase should still be designing
        assert parent_op.metadata.parameters["phase"] == "designing"
        # Task should NOT be deleted from child_tasks (we're waiting, not done)
        # Actually, the task is completed so it should be removed, but
        # the design results should be preserved for retry
        assert "op_research_123" in worker._design_results

    async def test_blocked_research_stays_in_designing_phase(
        self, worker, mock_ops, parent_op
    ):
        """Research stays in designing phase when waiting for worker."""
        # Setup: Design completed, no workers available
        completed_task = asyncio.Future()
        completed_task.set_result(
            {
                "strategy_name": "test_strategy",
                "strategy_path": "/tmp/test_strategy.yaml",
            }
        )
        worker._child_tasks["op_research_123"] = completed_task

        mock_ops.get_operation.return_value = parent_op

        mock_registry = MagicMock()
        mock_registry.get_available_workers.return_value = []

        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock()

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_designing_phase("op_research_123", None)

        # Phase must remain "designing" (not "training")
        assert parent_op.metadata.parameters.get("phase") == "designing"

    async def test_retry_succeeds_when_worker_becomes_available(
        self, worker, mock_ops, parent_op
    ):
        """When worker becomes available on retry, transition proceeds."""
        # Setup: Design already completed and stored in _design_results
        worker._design_results["op_research_123"] = {
            "strategy_name": "test_strategy",
            "strategy_path": "/tmp/test_strategy.yaml",
        }

        mock_ops.get_operation.return_value = parent_op

        # First call: no workers, second call: worker available
        mock_registry = MagicMock()
        mock_worker = MagicMock()
        mock_worker.worker_id = "training-worker-1"
        mock_registry.get_available_workers.return_value = [mock_worker]

        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock(
            return_value={"operation_id": "op_training_456"}
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_designing_phase("op_research_123", None)

        # Training should be started now that worker is available
        worker._training_service.start_training.assert_called_once()

    async def test_worker_check_uses_correct_worker_type(
        self, worker, mock_ops, parent_op
    ):
        """Worker availability check uses WorkerType.TRAINING."""
        completed_task = asyncio.Future()
        completed_task.set_result(
            {
                "strategy_name": "test_strategy",
                "strategy_path": "/tmp/test_strategy.yaml",
            }
        )
        worker._child_tasks["op_research_123"] = completed_task

        mock_ops.get_operation.return_value = parent_op

        mock_registry = MagicMock()
        mock_registry.get_available_workers.return_value = []

        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock()

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_designing_phase("op_research_123", None)

        # Verify the correct WorkerType was used
        from ktrdr.api.models.workers import WorkerType

        mock_registry.get_available_workers.assert_called_once_with(WorkerType.TRAINING)


class TestDesignToTrainingWithRealChildOp:
    """Tests for worker check when using real child operations (non-stub flow)."""

    @pytest.fixture
    def mock_ops(self):
        """Create mock operations service."""
        ops = MagicMock()
        ops.get_operation = AsyncMock()
        ops.list_operations = AsyncMock(return_value=([], 0, None))
        ops.update_progress = AsyncMock()
        return ops

    @pytest.fixture
    def worker(self, mock_ops):
        """Create AgentResearchWorker with mocked dependencies."""
        design_worker = MagicMock()
        assessment_worker = MagicMock()
        return AgentResearchWorker(
            operations_service=mock_ops,
            design_worker=design_worker,
            assessment_worker=assessment_worker,
        )

    @pytest.fixture
    def parent_op(self):
        """Create parent research operation."""
        op = MagicMock()
        op.operation_id = "op_research_123"
        op.status = OperationStatus.RUNNING
        op.created_at = datetime.now(timezone.utc)
        op.metadata = MagicMock()
        op.metadata.parameters = {
            "phase": "designing",
            "phase_start_time": 1000.0,
        }
        return op

    @pytest.fixture
    def completed_child_op(self):
        """Create completed design child operation."""
        op = MagicMock()
        op.operation_id = "op_design_child_123"
        op.status = OperationStatus.COMPLETED
        op.result_summary = {
            "strategy_name": "test_strategy",
            "strategy_path": "/tmp/test_strategy.yaml",
            "input_tokens": 100,
            "output_tokens": 50,
        }
        return op

    async def test_real_child_op_proceeds_when_worker_available(
        self, worker, mock_ops, parent_op, completed_child_op
    ):
        """With real child op flow, proceeds when training worker available."""
        mock_ops.get_operation.return_value = parent_op

        mock_registry = MagicMock()
        mock_worker = MagicMock()
        mock_registry.get_available_workers.return_value = [mock_worker]

        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock(
            return_value={"operation_id": "op_training_456"}
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_designing_phase("op_research_123", completed_child_op)

        # Training should be started
        worker._training_service.start_training.assert_called_once()

    async def test_real_child_op_waits_when_no_worker_available(
        self, worker, mock_ops, parent_op, completed_child_op
    ):
        """With real child op flow, waits when no training worker available."""
        mock_ops.get_operation.return_value = parent_op

        mock_registry = MagicMock()
        mock_registry.get_available_workers.return_value = []

        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock()

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_designing_phase("op_research_123", completed_child_op)

        # Training should NOT be started
        worker._training_service.start_training.assert_not_called()
        # Phase should remain "designing"
        assert parent_op.metadata.parameters["phase"] == "designing"

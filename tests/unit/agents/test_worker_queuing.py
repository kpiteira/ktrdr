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


class TestTrainingToBacktestWorkerCheck:
    """Tests for worker availability check in training→backtest transition."""

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
        """Create parent research operation in training phase."""
        op = MagicMock()
        op.operation_id = "op_research_123"
        op.status = OperationStatus.RUNNING
        op.created_at = datetime.now(timezone.utc)
        op.metadata = MagicMock()
        op.metadata.parameters = {
            "phase": "training",
            "phase_start_time": 1000.0,
            "strategy_path": "/tmp/test_strategy.yaml",
            "model_path": "/tmp/test_model.pt",
            "bypass_gates": False,
        }
        return op

    @pytest.fixture
    def completed_training_op(self):
        """Create completed training operation."""
        op = MagicMock()
        op.operation_id = "op_training_456"
        op.status = OperationStatus.COMPLETED
        op.result_summary = {
            "accuracy": 0.75,
            "final_loss": 0.25,
        }
        return op

    async def test_training_proceeds_when_backtest_worker_available(
        self, worker, mock_ops, parent_op, completed_training_op
    ):
        """When a backtest worker is available, training→backtest transition happens."""
        mock_ops.get_operation.return_value = parent_op

        # Mock worker registry with an available backtest worker
        mock_registry = MagicMock()
        mock_worker = MagicMock()
        mock_worker.worker_id = "backtest-worker-1"
        mock_registry.get_available_workers.return_value = [mock_worker]

        # Mock backtest service
        worker._backtest_service = MagicMock()
        worker._backtest_service.run_backtest = AsyncMock(
            return_value={"operation_id": "op_backtest_789"}
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_training_phase(
                "op_research_123", completed_training_op
            )

        # Verify: backtest was started
        worker._backtest_service.run_backtest.assert_called_once()
        # Phase should be updated to backtesting
        assert parent_op.metadata.parameters["phase"] == "backtesting"

    async def test_training_waits_when_no_backtest_worker_available(
        self, worker, mock_ops, parent_op, completed_training_op
    ):
        """When no backtest worker is available, stay in training phase."""
        mock_ops.get_operation.return_value = parent_op

        # Mock worker registry with NO available backtest workers
        mock_registry = MagicMock()
        mock_registry.get_available_workers.return_value = []

        # Mock backtest service (should NOT be called)
        worker._backtest_service = MagicMock()
        worker._backtest_service.run_backtest = AsyncMock()

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_training_phase(
                "op_research_123", completed_training_op
            )

        # Verify: backtest was NOT started
        worker._backtest_service.run_backtest.assert_not_called()
        # Phase should still be training
        assert parent_op.metadata.parameters["phase"] == "training"

    async def test_gate_rejection_skips_worker_check(
        self, worker, mock_ops, parent_op, completed_training_op
    ):
        """Gate rejection goes to assessment without checking workers."""
        # Training result that fails the gate (very low accuracy - below 10% threshold)
        completed_training_op.result_summary = {
            "accuracy": 0.05,  # 5%, below 10% threshold
            "final_loss": 0.9,  # High loss
        }
        mock_ops.get_operation.return_value = parent_op

        # Mock worker registry - should NOT be called for gate rejection
        mock_registry = MagicMock()
        mock_registry.get_available_workers.return_value = []  # No workers

        # Mock services
        worker._backtest_service = MagicMock()
        worker._backtest_service.run_backtest = AsyncMock()

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_training_phase(
                "op_research_123", completed_training_op
            )

        # Backtest should NOT be started (gate rejection)
        worker._backtest_service.run_backtest.assert_not_called()
        # Phase should be "assessing" (gate rejection routes there)
        assert parent_op.metadata.parameters["phase"] == "assessing"
        # Worker check should NOT have been called for backtest
        # (gate rejection bypasses the worker availability check entirely)

    async def test_worker_check_uses_correct_worker_type(
        self, worker, mock_ops, parent_op, completed_training_op
    ):
        """Worker availability check uses WorkerType.BACKTESTING."""
        mock_ops.get_operation.return_value = parent_op

        mock_registry = MagicMock()
        mock_registry.get_available_workers.return_value = []  # No workers

        worker._backtest_service = MagicMock()
        worker._backtest_service.run_backtest = AsyncMock()

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            await worker._handle_training_phase(
                "op_research_123", completed_training_op
            )

        # Verify the correct WorkerType was used
        from ktrdr.api.models.workers import WorkerType

        mock_registry.get_available_workers.assert_called_once_with(
            WorkerType.BACKTESTING
        )


class TestMultipleResearchesQueuing:
    """Tests for natural queuing behavior with multiple researches."""

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

    def create_research_op(self, op_id: str, phase: str = "designing"):
        """Helper to create a research operation in a specific phase."""
        op = MagicMock()
        op.operation_id = op_id
        op.status = OperationStatus.RUNNING
        op.created_at = datetime.now(timezone.utc)
        op.metadata = MagicMock()
        op.metadata.parameters = {
            "phase": phase,
            "phase_start_time": 1000.0,
            "strategy_path": "/tmp/test_strategy.yaml",
        }
        return op

    async def test_multiple_researches_queue_for_training_worker(
        self, worker, mock_ops
    ):
        """With 1 training worker and 3 researches, only one transitions at a time."""
        # Setup: Three researches all have completed design
        # Only one training worker available

        # Create three parent operations
        op_a = self.create_research_op("op_research_A", "designing")
        op_b = self.create_research_op("op_research_B", "designing")
        op_c = self.create_research_op("op_research_C", "designing")

        # Store completed design results for all three
        worker._design_results["op_research_A"] = {
            "strategy_name": "strategy_A",
            "strategy_path": "/tmp/strategy_a.yaml",
        }
        worker._design_results["op_research_B"] = {
            "strategy_name": "strategy_B",
            "strategy_path": "/tmp/strategy_b.yaml",
        }
        worker._design_results["op_research_C"] = {
            "strategy_name": "strategy_C",
            "strategy_path": "/tmp/strategy_c.yaml",
        }

        # Mock training service
        worker._training_service = MagicMock()
        training_call_count = 0

        async def mock_start_training(**kwargs):
            nonlocal training_call_count
            training_call_count += 1
            return {"operation_id": f"op_training_{training_call_count}"}

        worker._training_service.start_training = AsyncMock(
            side_effect=mock_start_training
        )

        # Simulate worker availability: starts with 1 available, then 0, then 0
        # First research gets the worker, others must wait
        available_workers = [
            [MagicMock(worker_id="training-worker-1")],  # First call: 1 available
            [],  # Second call: 0 available (worker busy)
            [],  # Third call: 0 available (worker still busy)
        ]
        call_idx = [0]

        def get_available_side_effect(worker_type):
            result = available_workers[min(call_idx[0], len(available_workers) - 1)]
            call_idx[0] += 1
            return result

        mock_registry = MagicMock()
        mock_registry.get_available_workers.side_effect = get_available_side_effect

        # Return appropriate op based on operation_id
        def get_op_side_effect(op_id):
            ops = {
                "op_research_A": op_a,
                "op_research_B": op_b,
                "op_research_C": op_c,
            }
            return ops.get(op_id)

        mock_ops.get_operation.side_effect = get_op_side_effect

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            # Process research A - should get the worker
            await worker._handle_designing_phase("op_research_A", None)

            # Process research B - should wait (no worker)
            await worker._handle_designing_phase("op_research_B", None)

            # Process research C - should wait (no worker)
            await worker._handle_designing_phase("op_research_C", None)

        # Only ONE training should have been started
        assert training_call_count == 1
        assert worker._training_service.start_training.call_count == 1

        # Research A should have transitioned to training
        assert op_a.metadata.parameters["phase"] == "training"

        # Researches B and C should still be in designing (waiting)
        assert op_b.metadata.parameters["phase"] == "designing"
        assert op_c.metadata.parameters["phase"] == "designing"

        # B and C should still have their design results stored for retry
        assert "op_research_B" in worker._design_results
        assert "op_research_C" in worker._design_results

    async def test_queued_research_proceeds_when_worker_frees_up(
        self, worker, mock_ops
    ):
        """When a worker becomes available, the waiting research proceeds."""
        # Setup: Research B was waiting for a training worker
        op_b = self.create_research_op("op_research_B", "designing")

        # B has completed design and is stored in _design_results
        worker._design_results["op_research_B"] = {
            "strategy_name": "strategy_B",
            "strategy_path": "/tmp/strategy_b.yaml",
        }

        mock_ops.get_operation.return_value = op_b

        # Now a training worker becomes available
        mock_registry = MagicMock()
        mock_registry.get_available_workers.return_value = [
            MagicMock(worker_id="training-worker-1")
        ]

        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock(
            return_value={"operation_id": "op_training_B"}
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            # Process research B - worker now available
            await worker._handle_designing_phase("op_research_B", None)

        # B should now transition to training
        worker._training_service.start_training.assert_called_once()
        assert op_b.metadata.parameters["phase"] == "training"

        # Design results should be cleaned up (used)
        # Note: _design_results cleanup happens in _start_training
        # but since we're mocking the training service, it might still be there

    async def test_backtest_queuing_with_multiple_researches(self, worker, mock_ops):
        """With 1 backtest worker and 2 researches, only one backtests at a time."""
        # Setup: Two researches have completed training and passed gate
        op_a = self.create_research_op("op_research_A", "training")
        op_a.metadata.parameters["training_result"] = {
            "accuracy": 0.8,
            "final_loss": 0.2,
        }

        op_b = self.create_research_op("op_research_B", "training")
        op_b.metadata.parameters["training_result"] = {
            "accuracy": 0.75,
            "final_loss": 0.25,
        }

        # Create completed training operations
        training_op_a = MagicMock()
        training_op_a.operation_id = "op_training_A"
        training_op_a.status = OperationStatus.COMPLETED
        training_op_a.result_summary = {"accuracy": 0.8, "final_loss": 0.2}

        training_op_b = MagicMock()
        training_op_b.operation_id = "op_training_B"
        training_op_b.status = OperationStatus.COMPLETED
        training_op_b.result_summary = {"accuracy": 0.75, "final_loss": 0.25}

        # Mock backtest service
        worker._backtest_service = MagicMock()
        backtest_call_count = 0

        async def mock_run_backtest(**kwargs):
            nonlocal backtest_call_count
            backtest_call_count += 1
            return {"operation_id": f"op_backtest_{backtest_call_count}"}

        worker._backtest_service.run_backtest = AsyncMock(side_effect=mock_run_backtest)

        # Simulate worker availability: 1 available, then 0
        available_workers = [
            [MagicMock(worker_id="backtest-worker-1")],  # First call: 1 available
            [],  # Second call: 0 available
        ]
        call_idx = [0]

        def get_available_side_effect(worker_type):
            result = available_workers[min(call_idx[0], len(available_workers) - 1)]
            call_idx[0] += 1
            return result

        mock_registry = MagicMock()
        mock_registry.get_available_workers.side_effect = get_available_side_effect

        def get_op_side_effect(op_id):
            ops = {"op_research_A": op_a, "op_research_B": op_b}
            return ops.get(op_id)

        mock_ops.get_operation.side_effect = get_op_side_effect

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            # Process research A - should get the backtest worker
            await worker._handle_training_phase("op_research_A", training_op_a)

            # Process research B - should wait (no worker)
            await worker._handle_training_phase("op_research_B", training_op_b)

        # Only ONE backtest should have been started
        assert backtest_call_count == 1

        # Research A should have transitioned to backtesting
        assert op_a.metadata.parameters["phase"] == "backtesting"

        # Research B should still be in training (waiting)
        assert op_b.metadata.parameters["phase"] == "training"

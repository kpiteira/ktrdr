"""Integration tests for worker queuing behavior.

Task 3.3 of M3: Verify researches naturally queue when workers are busy.

Tests the complete queuing flow where multiple researches compete for
limited workers, verifying they queue and proceed in order.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service for integration testing."""
    service = AsyncMock()

    operations: dict[str, OperationInfo] = {}
    operation_counter = 0

    async def async_create_operation(
        operation_type, metadata=None, parent_operation_id=None, is_backend_local=False
    ):
        nonlocal operation_counter
        operation_counter += 1
        op_id = f"op_{operation_type.value}_{operation_counter}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or OperationMetadata(),
            parent_operation_id=parent_operation_id,
        )
        operations[op_id] = op
        return op

    async def async_get_operation(operation_id):
        return operations.get(operation_id)

    async def async_complete_operation(operation_id, result=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.COMPLETED
            operations[operation_id].result_summary = result
            operations[operation_id].completed_at = datetime.now(timezone.utc)

    async def async_fail_operation(operation_id, error=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.FAILED
            operations[operation_id].error_message = error

    async def async_cancel_operation(operation_id, reason=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.CANCELLED
            operations[operation_id].error_message = reason

    async def async_start_operation(operation_id, task=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.RUNNING
            operations[operation_id].started_at = datetime.now(timezone.utc)

    async def async_list_operations(
        operation_type=None, status=None, limit=100, offset=0, active_only=False
    ):
        filtered = list(operations.values())

        if operation_type:
            filtered = [op for op in filtered if op.operation_type == operation_type]

        if status:
            filtered = [op for op in filtered if op.status == status]

        if active_only:
            filtered = [
                op
                for op in filtered
                if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
            ]

        filtered.sort(key=lambda op: op.created_at, reverse=True)
        total_count = len(filtered)
        active_count = len(
            [
                op
                for op in operations.values()
                if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
            ]
        )

        return filtered[offset : offset + limit], total_count, active_count

    async def async_update_progress(operation_id, progress):
        if operation_id in operations:
            operations[operation_id].progress = progress

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.complete_operation = async_complete_operation
    service.fail_operation = async_fail_operation
    service.cancel_operation = async_cancel_operation
    service.start_operation = async_start_operation
    service.list_operations = async_list_operations
    service.update_progress = async_update_progress
    service._operations = operations

    return service


class TestWorkerQueuingIntegration:
    """Integration tests for natural worker queuing behavior."""

    @pytest.fixture(autouse=True)
    def fast_polling(self, monkeypatch):
        """Use fast polling for tests."""
        monkeypatch.setenv("AGENT_POLL_INTERVAL", "0.05")

    @pytest.mark.asyncio
    async def test_natural_queuing_with_limited_training_workers(
        self, mock_operations_service
    ):
        """
        E2E: 2 training workers, 3 researches.
        A and B train in parallel, C waits, then proceeds when A finishes.
        """
        # Create mock workers
        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
        )
        worker.POLL_INTERVAL = 0.05

        # Create three research operations, all in designing phase with completed design
        op_a = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "designing",
                    "phase_start_time": 1000.0,
                    "strategy_path": "/tmp/strategy_a.yaml",
                }
            ),
        )
        await mock_operations_service.start_operation(op_a.operation_id)

        op_b = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "designing",
                    "phase_start_time": 1000.0,
                    "strategy_path": "/tmp/strategy_b.yaml",
                }
            ),
        )
        await mock_operations_service.start_operation(op_b.operation_id)

        op_c = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "designing",
                    "phase_start_time": 1000.0,
                    "strategy_path": "/tmp/strategy_c.yaml",
                }
            ),
        )
        await mock_operations_service.start_operation(op_c.operation_id)

        # Store completed design results for all three
        worker._design_results[op_a.operation_id] = {
            "strategy_name": "strategy_A",
            "strategy_path": "/tmp/strategy_a.yaml",
        }
        worker._design_results[op_b.operation_id] = {
            "strategy_name": "strategy_B",
            "strategy_path": "/tmp/strategy_b.yaml",
        }
        worker._design_results[op_c.operation_id] = {
            "strategy_name": "strategy_C",
            "strategy_path": "/tmp/strategy_c.yaml",
        }

        # Mock training service
        training_started = []

        async def mock_start_training(**kwargs):
            op_id = f"op_training_{len(training_started) + 1}"
            training_started.append(op_id)
            return {"operation_id": op_id}

        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock(
            side_effect=mock_start_training
        )

        # Simulate 2 available training workers
        # After 2 are assigned, no more available
        available_count = [2]  # Mutable to track availability

        def get_available_workers(worker_type):
            from ktrdr.api.models.workers import WorkerType

            if worker_type == WorkerType.TRAINING:
                if available_count[0] > 0:
                    workers = [
                        MagicMock(worker_id=f"training-worker-{i}")
                        for i in range(available_count[0])
                    ]
                    available_count[0] -= 1  # One worker gets assigned
                    return workers
                return []
            return []

        mock_registry = MagicMock()
        mock_registry.get_available_workers.side_effect = get_available_workers

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            # Process all three researches once (simulating one poll cycle)
            # A should get a worker
            await worker._handle_designing_phase(op_a.operation_id, None)
            # B should get a worker
            await worker._handle_designing_phase(op_b.operation_id, None)
            # C should have to wait (no workers left)
            await worker._handle_designing_phase(op_c.operation_id, None)

        # Verify: A and B started training, C is still waiting
        assert len(training_started) == 2

        # Get the updated operations
        updated_a = await mock_operations_service.get_operation(op_a.operation_id)
        updated_b = await mock_operations_service.get_operation(op_b.operation_id)
        updated_c = await mock_operations_service.get_operation(op_c.operation_id)

        # A and B should be in training phase
        assert updated_a.metadata.parameters["phase"] == "training"
        assert updated_b.metadata.parameters["phase"] == "training"

        # C should still be in designing phase (waiting for worker)
        assert updated_c.metadata.parameters["phase"] == "designing"

        # C's design results should still be stored (for retry)
        assert op_c.operation_id in worker._design_results

        # Now simulate worker A finishing and freeing up
        available_count[0] = 1  # A worker is now available

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            # C should now get a worker
            await worker._handle_designing_phase(op_c.operation_id, None)

        # Verify: C now started training
        assert len(training_started) == 3

        updated_c = await mock_operations_service.get_operation(op_c.operation_id)
        assert updated_c.metadata.parameters["phase"] == "training"

    @pytest.mark.asyncio
    async def test_queuing_preserves_order_of_completion(self, mock_operations_service):
        """Researches that complete design first should queue first."""
        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
        )
        worker.POLL_INTERVAL = 0.05

        # Create two research operations
        op_first = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "designing",
                    "phase_start_time": 1000.0,
                    "strategy_path": "/tmp/strategy_first.yaml",
                }
            ),
        )
        await mock_operations_service.start_operation(op_first.operation_id)

        op_second = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "designing",
                    "phase_start_time": 1000.0,
                    "strategy_path": "/tmp/strategy_second.yaml",
                }
            ),
        )
        await mock_operations_service.start_operation(op_second.operation_id)

        # Both have completed design
        worker._design_results[op_first.operation_id] = {
            "strategy_name": "strategy_first",
            "strategy_path": "/tmp/strategy_first.yaml",
        }
        worker._design_results[op_second.operation_id] = {
            "strategy_name": "strategy_second",
            "strategy_path": "/tmp/strategy_second.yaml",
        }

        # Track which research starts training
        training_order = []

        async def mock_start_training(**kwargs):
            training_order.append(kwargs.get("strategy_name", "unknown"))
            return {"operation_id": f"op_training_{len(training_order)}"}

        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock(
            side_effect=mock_start_training
        )

        # Only 1 worker available
        mock_registry = MagicMock()
        available = [True]  # First call returns worker, subsequent calls empty

        def get_available_workers(worker_type):
            if available[0]:
                available[0] = False
                return [MagicMock(worker_id="training-worker-1")]
            return []

        mock_registry.get_available_workers.side_effect = get_available_workers

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            # Process first, then second
            await worker._handle_designing_phase(op_first.operation_id, None)
            await worker._handle_designing_phase(op_second.operation_id, None)

        # Only first should have started (got the worker)
        assert len(training_order) == 1

        # First research transitioned, second is waiting
        updated_first = await mock_operations_service.get_operation(
            op_first.operation_id
        )
        updated_second = await mock_operations_service.get_operation(
            op_second.operation_id
        )

        assert updated_first.metadata.parameters["phase"] == "training"
        assert updated_second.metadata.parameters["phase"] == "designing"

    @pytest.mark.asyncio
    async def test_no_starvation_all_researches_eventually_proceed(
        self, mock_operations_service
    ):
        """All queued researches eventually get to train when workers free up."""
        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
        )
        worker.POLL_INTERVAL = 0.05

        # Create 3 research operations
        ops = []
        for i in range(3):
            op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_RESEARCH,
                metadata=OperationMetadata(
                    parameters={
                        "phase": "designing",
                        "phase_start_time": 1000.0,
                        "strategy_path": f"/tmp/strategy_{i}.yaml",
                    }
                ),
            )
            await mock_operations_service.start_operation(op.operation_id)
            ops.append(op)

            # Store completed design
            worker._design_results[op.operation_id] = {
                "strategy_name": f"strategy_{i}",
                "strategy_path": f"/tmp/strategy_{i}.yaml",
            }

        # Track how many times training starts
        training_call_count = [0]

        async def mock_start_training(**kwargs):
            training_call_count[0] += 1
            return {"operation_id": f"op_training_{training_call_count[0]}"}

        worker._training_service = MagicMock()
        worker._training_service.start_training = AsyncMock(
            side_effect=mock_start_training
        )

        # Simulate workers becoming available one at a time
        workers_available = [1]

        def get_available_workers(worker_type):
            if workers_available[0] > 0:
                workers_available[0] -= 1
                return [MagicMock(worker_id="training-worker-1")]
            return []

        mock_registry = MagicMock()
        mock_registry.get_available_workers.side_effect = get_available_workers

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            # Round 1: One worker available, first research gets it
            for op in ops:
                await worker._handle_designing_phase(op.operation_id, None)

            # Round 2: Free up another worker
            workers_available[0] = 1
            for op in ops:
                updated = await mock_operations_service.get_operation(op.operation_id)
                if updated.metadata.parameters["phase"] == "designing":
                    await worker._handle_designing_phase(op.operation_id, None)

            # Round 3: Free up another worker
            workers_available[0] = 1
            for op in ops:
                updated = await mock_operations_service.get_operation(op.operation_id)
                if updated.metadata.parameters["phase"] == "designing":
                    await worker._handle_designing_phase(op.operation_id, None)

        # All three should have eventually started training
        assert training_call_count[0] == 3

        # All should be in training phase now
        for op in ops:
            updated = await mock_operations_service.get_operation(op.operation_id)
            assert updated.metadata.parameters["phase"] == "training"

"""Integration tests for M6: Coordinator Restart Recovery.

Goal: Researches resume after backend restart, detecting orphaned tasks.

These tests verify restart recovery at the integration level - simulating
restart by clearing coordinator state and verifying orphan detection.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)

# ============================================================================
# Test Infrastructure
# ============================================================================


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


@pytest.fixture
def mock_design_worker():
    """Create a mock design worker."""
    worker = AsyncMock()
    worker.run = AsyncMock()
    return worker


@pytest.fixture
def mock_assessment_worker():
    """Create a mock assessment worker."""
    worker = AsyncMock()
    worker.run = AsyncMock()
    return worker


@pytest.fixture
def mock_checkpoint_service():
    """Create a mock checkpoint service."""
    service = AsyncMock()
    service.save_checkpoint = AsyncMock()
    service.delete_checkpoint = AsyncMock()
    return service


# ============================================================================
# Integration Tests
# ============================================================================


class TestRestartRecoveryIntegration:
    """Integration tests for restart recovery."""

    @pytest.mark.asyncio
    async def test_simulate_restart_orphan_detected(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """
        Simulate restart: clear _child_tasks, verify orphan detected.

        This test simulates a backend restart by:
        1. Creating a research in designing phase with RUNNING child
        2. Creating a fresh coordinator (no _child_tasks - simulates restart)
        3. Verifying the orphan is detected and phase restarted
        """
        # PHASE 1: Set up state as if backend just restarted
        #
        # Create parent research in designing phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "designing", "design_op_id": "child_design_orphan"}
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        # Create child operation that was RUNNING when backend died
        child_op = OperationInfo(
            operation_id="child_design_orphan",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_design_orphan"] = child_op

        # PHASE 2: Create a fresh coordinator (simulates post-restart state)
        # _child_tasks is empty because the coordinator is new
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Track design restarts
        design_restart_count = 0

        async def track_start_design(op_id):
            nonlocal design_restart_count
            design_restart_count += 1
            # Complete the research to exit the loop
            mock_operations_service._operations[parent_op.operation_id].status = (
                OperationStatus.COMPLETED
            )

        worker._start_design = track_start_design

        # PHASE 3: Run coordinator - should detect orphan
        await worker.run()

        # VERIFY: Orphan was detected
        assert (
            child_op.status == OperationStatus.FAILED
        ), "Orphaned child should be marked FAILED"
        assert (
            "orphaned" in child_op.error_message.lower()
        ), "Error should mention orphan"
        assert design_restart_count == 1, "Design phase should be restarted once"

    @pytest.mark.asyncio
    async def test_training_continues_after_simulated_restart(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """
        Training on worker continues after restart - NOT orphaned.

        Training runs on external workers, so a fresh coordinator should
        continue polling for training completion, not mark it as orphaned.
        """
        # Create parent research in training phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "training_op_id": "child_train_restart",
                }
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        # Create child training operation RUNNING on worker
        child_op = OperationInfo(
            operation_id="child_train_restart",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_train_restart"] = child_op

        # Create fresh coordinator (post-restart)
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0.01

        # Single advance - should NOT mark training as orphaned
        await worker._advance_research(parent_op)

        # VERIFY: Training continues (not orphaned)
        assert child_op.status == OperationStatus.RUNNING
        assert child_op.error_message is None

    @pytest.mark.asyncio
    async def test_multiple_researches_orphan_detection(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """
        Multiple researches: orphan detected only for designing phase.

        After restart:
        - Research A in designing with orphaned child → detected, restarted
        - Research B in training (on worker) → continues normally
        """
        # Research A: designing phase with orphaned child
        research_a = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "designing", "design_op_id": "child_a_design"}
            ),
        )
        research_a.status = OperationStatus.RUNNING

        child_a = OperationInfo(
            operation_id="child_a_design",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_a_design"] = child_a

        # Research B: training phase (on worker, not orphaned)
        research_b = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "training", "training_op_id": "child_b_train"}
            ),
        )
        research_b.status = OperationStatus.RUNNING

        child_b = OperationInfo(
            operation_id="child_b_train",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_b_train"] = child_b

        # Fresh coordinator (post-restart)
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Track design restarts
        design_restart_count = 0

        async def track_start_design(op_id):
            nonlocal design_restart_count
            design_restart_count += 1
            # Complete Research A
            mock_operations_service._operations[research_a.operation_id].status = (
                OperationStatus.COMPLETED
            )

        worker._start_design = track_start_design

        # Advance Research A - should detect orphan
        await worker._advance_research(research_a)
        assert child_a.status == OperationStatus.FAILED
        assert design_restart_count == 1

        # Advance Research B - should NOT detect orphan
        await worker._advance_research(research_b)
        assert child_b.status == OperationStatus.RUNNING  # Still running

"""Integration tests for M2: Error Isolation.

Goal: Verify one research failing doesn't stop others from completing.

These tests verify error isolation at the integration level - testing
the full coordinator loop with mocked workers but real error handling.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.agents.workers.research_worker import (
    AgentResearchWorker,
    GateError,
    WorkerError,
)
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
    """Create a mock operations service for integration testing.

    This mock simulates the database layer for operation tracking.
    """
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
def mock_checkpoint_service():
    """Create a mock checkpoint service for tracking saves."""
    service = AsyncMock()
    service.saved_checkpoints = []

    async def track_save(operation_id, checkpoint_type, state, artifacts=None):
        service.saved_checkpoints.append(
            {
                "operation_id": operation_id,
                "checkpoint_type": checkpoint_type,
                "state": state,
            }
        )

    service.save_checkpoint = track_save
    service.delete_checkpoint = AsyncMock()
    return service


# ============================================================================
# Integration Tests: Error Isolation
# ============================================================================


class TestErrorIsolationIntegration:
    """Integration tests for per-research error isolation.

    These tests verify that when one research fails, the coordinator
    continues processing other researches to completion.
    """

    @pytest.fixture(autouse=True)
    def fast_polling(self, monkeypatch):
        """Use fast polling for tests."""
        monkeypatch.setenv("AGENT_POLL_INTERVAL", "0.01")

    @pytest.mark.asyncio
    async def test_one_research_fails_others_continue_three_ops(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """E2E: One research fails, two others complete successfully.

        This is the primary error isolation test per M2 spec:
        - Setup: Configure one research to fail
        - Trigger three researches
        - Verify: One failed, two completed
        """
        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Create three research operations
        op_a = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle", "brief": "A"}),
        )
        await mock_operations_service.start_operation(op_a.operation_id)

        op_b = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle", "brief": "B"}),
        )
        await mock_operations_service.start_operation(op_b.operation_id)

        op_c = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle", "brief": "C"}),
        )
        await mock_operations_service.start_operation(op_c.operation_id)

        # Track processing
        call_counts = {
            op_a.operation_id: 0,
            op_b.operation_id: 0,
            op_c.operation_id: 0,
        }

        async def advance_with_b_failing(op):
            call_counts[op.operation_id] += 1

            # Research B fails on first call
            if op.operation_id == op_b.operation_id:
                raise WorkerError("Research B failed: simulated error")

            # Research A and C complete after 2 calls
            if call_counts[op.operation_id] >= 2:
                mock_operations_service._operations[op.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        with patch.object(
            worker, "_advance_research", side_effect=advance_with_b_failing
        ):
            await worker.run()

        # DB Verification: Check final statuses
        op_a_final = mock_operations_service._operations[op_a.operation_id]
        op_b_final = mock_operations_service._operations[op_b.operation_id]
        op_c_final = mock_operations_service._operations[op_c.operation_id]

        # Research B should be FAILED
        assert (
            op_b_final.status == OperationStatus.FAILED
        ), f"Expected B to be FAILED, got {op_b_final.status}"
        assert "simulated error" in op_b_final.error_message

        # Research A should be COMPLETED
        assert (
            op_a_final.status == OperationStatus.COMPLETED
        ), f"Expected A to be COMPLETED, got {op_a_final.status}"

        # Research C should be COMPLETED
        assert (
            op_c_final.status == OperationStatus.COMPLETED
        ), f"Expected C to be COMPLETED, got {op_c_final.status}"

        # Verify A and C were called multiple times (continued after B failed)
        assert call_counts[op_a.operation_id] >= 2
        assert call_counts[op_c.operation_id] >= 2

    @pytest.mark.asyncio
    async def test_checkpoint_saved_for_failed_research(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """DB verification: Checkpoint record exists after failure."""
        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        await mock_operations_service.start_operation(op.operation_id)

        async def fail_research(op_obj):
            raise WorkerError("Training timeout")

        with patch.object(worker, "_advance_research", side_effect=fail_research):
            await worker.run()

        # Verify checkpoint was saved
        assert len(mock_checkpoint_service.saved_checkpoints) == 1
        checkpoint = mock_checkpoint_service.saved_checkpoints[0]
        assert checkpoint["operation_id"] == op.operation_id
        assert checkpoint["checkpoint_type"] == "failure"

    @pytest.mark.asyncio
    async def test_gate_error_isolates_single_research(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """GateError fails one research, others continue."""
        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Create two operations
        op_fail = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        await mock_operations_service.start_operation(op_fail.operation_id)

        op_success = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        await mock_operations_service.start_operation(op_success.operation_id)

        call_counts = {op_fail.operation_id: 0, op_success.operation_id: 0}

        async def gate_error_on_first(op):
            call_counts[op.operation_id] += 1

            if op.operation_id == op_fail.operation_id:
                raise GateError(
                    "Training gate failed: accuracy=0.3 < 0.5",
                    gate="training",
                    metrics={"accuracy": 0.3},
                )

            if call_counts[op_success.operation_id] >= 2:
                mock_operations_service._operations[op_success.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        with patch.object(worker, "_advance_research", side_effect=gate_error_on_first):
            await worker.run()

        # Verify statuses
        assert (
            mock_operations_service._operations[op_fail.operation_id].status
            == OperationStatus.FAILED
        )
        assert (
            mock_operations_service._operations[op_success.operation_id].status
            == OperationStatus.COMPLETED
        )

    @pytest.mark.asyncio
    async def test_multiple_failures_dont_crash_coordinator(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Multiple researches can fail without crashing coordinator."""
        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Create three operations - all will fail
        ops = []
        for i in range(3):
            op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_RESEARCH,
                metadata=OperationMetadata(parameters={"phase": "idle", "index": i}),
            )
            await mock_operations_service.start_operation(op.operation_id)
            ops.append(op)

        async def all_fail(op):
            raise WorkerError(f"Research {op.metadata.parameters['index']} failed")

        with patch.object(worker, "_advance_research", side_effect=all_fail):
            # Should not raise - coordinator handles all errors gracefully
            await worker.run()

        # All should be FAILED
        for op in ops:
            assert (
                mock_operations_service._operations[op.operation_id].status
                == OperationStatus.FAILED
            )

        # All should have checkpoints
        assert len(mock_checkpoint_service.saved_checkpoints) == 3

    @pytest.mark.asyncio
    async def test_unexpected_error_type_isolated(
        self, mock_operations_service, mock_checkpoint_service
    ):
        """Unexpected exception types (not WorkerError/GateError) are also isolated."""
        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        op_error = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        await mock_operations_service.start_operation(op_error.operation_id)

        op_ok = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        await mock_operations_service.start_operation(op_ok.operation_id)

        call_counts = {op_error.operation_id: 0, op_ok.operation_id: 0}

        async def unexpected_error_first(op):
            call_counts[op.operation_id] += 1

            if op.operation_id == op_error.operation_id:
                # Unexpected error type
                raise RuntimeError("Unexpected database connection error")

            if call_counts[op_ok.operation_id] >= 2:
                mock_operations_service._operations[op_ok.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        with patch.object(
            worker, "_advance_research", side_effect=unexpected_error_first
        ):
            await worker.run()

        # Error op should be FAILED
        assert (
            mock_operations_service._operations[op_error.operation_id].status
            == OperationStatus.FAILED
        )

        # OK op should be COMPLETED
        assert (
            mock_operations_service._operations[op_ok.operation_id].status
            == OperationStatus.COMPLETED
        )

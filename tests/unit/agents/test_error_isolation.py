"""Tests for M2: Error Isolation in multi-research coordinator.

Goal: If one research fails, others continue unaffected.

Test categories:
- TestWorkerErrorIsolation: WorkerError in one research doesn't stop others
- TestGateErrorIsolation: GateError in one research doesn't stop others
- TestUnexpectedErrorIsolation: Unexpected exceptions don't stop others
- TestCancelledErrorIsolation: CancelledError marks one research cancelled
- TestCheckpointOnFailure: Checkpoint saved when research fails
- TestMetricsPerResearch: Each research records its own metrics
"""

import asyncio
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
    """Create a mock operations service for testing."""
    service = AsyncMock()

    # Track operations in memory
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
        """List operations with filtering."""
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
# TestWorkerErrorIsolation
# ============================================================================


class TestWorkerErrorIsolation:
    """Tests for WorkerError isolation - one failure shouldn't affect others."""

    @pytest.mark.asyncio
    async def test_worker_error_in_one_research_doesnt_stop_others(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """WorkerError marks one research failed, others continue."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Create two operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        call_count = {op1.operation_id: 0, op2.operation_id: 0}

        async def advance_with_error(op):
            call_count[op.operation_id] += 1

            # op1 raises WorkerError on first call
            if op.operation_id == op1.operation_id:
                raise WorkerError("Design failed: test error")

            # op2 completes after 2 calls
            if call_count[op2.operation_id] >= 2:
                mock_operations_service._operations[op2.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        with patch.object(worker, "_advance_research", side_effect=advance_with_error):
            await worker.run()

        # op1 should be FAILED
        assert (
            mock_operations_service._operations[op1.operation_id].status
            == OperationStatus.FAILED
        )
        # op2 should have been called multiple times (continued after op1 failed)
        assert call_count[op2.operation_id] >= 2
        # op2 should be COMPLETED
        assert (
            mock_operations_service._operations[op2.operation_id].status
            == OperationStatus.COMPLETED
        )

    @pytest.mark.asyncio
    async def test_worker_error_marks_research_failed(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """WorkerError results in FAILED status and error message stored."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        async def raise_worker_error(op_obj):
            raise WorkerError("Design failed: timeout")

        with patch.object(worker, "_advance_research", side_effect=raise_worker_error):
            await worker.run()

        # Operation should be FAILED with error message
        assert (
            mock_operations_service._operations[op.operation_id].status
            == OperationStatus.FAILED
        )
        assert (
            "timeout"
            in mock_operations_service._operations[op.operation_id].error_message
        )


# ============================================================================
# TestGateErrorIsolation
# ============================================================================


class TestGateErrorIsolation:
    """Tests for GateError isolation."""

    @pytest.mark.asyncio
    async def test_gate_error_in_one_research_doesnt_stop_others(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """GateError marks one research failed, others continue."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Create two operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )

        call_count = {op1.operation_id: 0, op2.operation_id: 0}

        async def advance_with_gate_error(op):
            call_count[op.operation_id] += 1

            # op1 raises GateError
            if op.operation_id == op1.operation_id:
                raise GateError(
                    "Training gate failed: accuracy below threshold",
                    gate="training",
                    metrics={"accuracy": 0.3},
                )

            # op2 completes
            if call_count[op2.operation_id] >= 2:
                mock_operations_service._operations[op2.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        with patch.object(
            worker, "_advance_research", side_effect=advance_with_gate_error
        ):
            await worker.run()

        # op1 should be FAILED
        assert (
            mock_operations_service._operations[op1.operation_id].status
            == OperationStatus.FAILED
        )
        # op2 should continue and complete
        assert (
            mock_operations_service._operations[op2.operation_id].status
            == OperationStatus.COMPLETED
        )


# ============================================================================
# TestUnexpectedErrorIsolation
# ============================================================================


class TestUnexpectedErrorIsolation:
    """Tests for unexpected exception isolation."""

    @pytest.mark.asyncio
    async def test_unexpected_error_in_one_research_doesnt_stop_others(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """Unexpected exception marks one research failed, others continue."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Create two operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )

        call_count = {op1.operation_id: 0, op2.operation_id: 0}

        async def advance_with_unexpected_error(op):
            call_count[op.operation_id] += 1

            # op1 raises an unexpected error (e.g., KeyError, TypeError)
            if op.operation_id == op1.operation_id:
                raise KeyError("missing_key")

            # op2 completes
            if call_count[op2.operation_id] >= 2:
                mock_operations_service._operations[op2.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        with patch.object(
            worker, "_advance_research", side_effect=advance_with_unexpected_error
        ):
            await worker.run()

        # op1 should be FAILED
        assert (
            mock_operations_service._operations[op1.operation_id].status
            == OperationStatus.FAILED
        )
        # op2 should continue and complete
        assert (
            mock_operations_service._operations[op2.operation_id].status
            == OperationStatus.COMPLETED
        )

    @pytest.mark.asyncio
    async def test_unexpected_error_is_logged(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
        caplog,
    ):
        """Unexpected errors are logged with operation ID."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        async def raise_unexpected(op_obj):
            raise RuntimeError("unexpected database error")

        with patch.object(worker, "_advance_research", side_effect=raise_unexpected):
            await worker.run()

        # Error should be logged
        assert any(
            "unexpected" in record.message.lower() or "RuntimeError" in record.message
            for record in caplog.records
        )


# ============================================================================
# TestCancelledErrorIsolation
# ============================================================================


class TestCancelledErrorIsolation:
    """Tests for CancelledError handling per-research."""

    @pytest.mark.asyncio
    async def test_cancelled_error_in_one_research_cancels_only_that_research(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """CancelledError cancels one research, others continue."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Create two operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )

        call_count = {op1.operation_id: 0, op2.operation_id: 0}

        async def advance_with_cancel(op):
            call_count[op.operation_id] += 1

            # op1 raises CancelledError (simulating cancelled child operation)
            if op.operation_id == op1.operation_id:
                raise asyncio.CancelledError("Design was cancelled")

            # op2 completes
            if call_count[op2.operation_id] >= 2:
                mock_operations_service._operations[op2.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        with patch.object(worker, "_advance_research", side_effect=advance_with_cancel):
            await worker.run()

        # op1 should be CANCELLED
        assert (
            mock_operations_service._operations[op1.operation_id].status
            == OperationStatus.CANCELLED
        )
        # op2 should continue and complete
        assert (
            mock_operations_service._operations[op2.operation_id].status
            == OperationStatus.COMPLETED
        )

    @pytest.mark.asyncio
    async def test_cancelled_research_has_checkpoint_saved(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """Cancelled research gets checkpoint saved."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )

        async def raise_cancelled(op_obj):
            raise asyncio.CancelledError("Design was cancelled")

        with patch.object(worker, "_advance_research", side_effect=raise_cancelled):
            await worker.run()

        # Checkpoint should have been saved with "cancellation" type
        mock_checkpoint_service.save_checkpoint.assert_called_once()
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["checkpoint_type"] == "cancellation"


# ============================================================================
# TestCheckpointOnFailure
# ============================================================================


class TestCheckpointOnFailure:
    """Tests for checkpoint saving on failure."""

    @pytest.mark.asyncio
    async def test_checkpoint_saved_on_worker_error(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """Checkpoint saved when research fails with WorkerError."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )

        async def raise_worker_error(op_obj):
            raise WorkerError("Training failed: timeout")

        with patch.object(worker, "_advance_research", side_effect=raise_worker_error):
            await worker.run()

        # Checkpoint should have been saved with "failure" type
        mock_checkpoint_service.save_checkpoint.assert_called_once()
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["operation_id"] == op.operation_id
        assert call_args[1]["checkpoint_type"] == "failure"

    @pytest.mark.asyncio
    async def test_checkpoint_saved_on_unexpected_error(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """Checkpoint saved when research fails with unexpected error."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "backtesting"}),
        )

        async def raise_unexpected(op_obj):
            raise ValueError("unexpected value error")

        with patch.object(worker, "_advance_research", side_effect=raise_unexpected):
            await worker.run()

        # Checkpoint should have been saved
        mock_checkpoint_service.save_checkpoint.assert_called_once()
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["checkpoint_type"] == "failure"


# ============================================================================
# TestMetricsPerResearch
# ============================================================================


class TestMetricsPerResearch:
    """Tests for per-research metrics recording."""

    @pytest.mark.asyncio
    async def test_failed_metrics_recorded_per_research(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """Each failed research records its own 'failed' metric."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Create two operations that will fail
        await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )

        async def raise_errors(op):
            raise WorkerError(f"Error in {op.operation_id}")

        with (
            patch.object(worker, "_advance_research", side_effect=raise_errors),
            patch(
                "ktrdr.agents.workers.research_worker.record_cycle_outcome"
            ) as mock_metrics,
        ):
            await worker.run()

        # Each failure should record a metric
        assert mock_metrics.call_count == 2
        for call in mock_metrics.call_args_list:
            assert call[0][0] == "failed"


# ============================================================================
# TestHandlerMethods
# ============================================================================


class TestHandlerMethods:
    """Tests for the new handler methods."""

    @pytest.mark.asyncio
    async def test_handle_research_cancelled_method_exists(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Verify _handle_research_cancelled method exists and works."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )

        # Method should exist
        assert hasattr(worker, "_handle_research_cancelled")

        # Call it
        with patch(
            "ktrdr.agents.workers.research_worker.record_cycle_outcome"
        ) as mock_metrics:
            await worker._handle_research_cancelled(op)

        # Should mark cancelled and record metrics
        assert (
            mock_operations_service._operations[op.operation_id].status
            == OperationStatus.CANCELLED
        )
        mock_metrics.assert_called_once_with("cancelled")

    @pytest.mark.asyncio
    async def test_handle_research_failed_method_exists(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Verify _handle_research_failed method exists and works."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )

        # Method should exist
        assert hasattr(worker, "_handle_research_failed")

        # Call it
        error = WorkerError("test error")
        with patch(
            "ktrdr.agents.workers.research_worker.record_cycle_outcome"
        ) as mock_metrics:
            await worker._handle_research_failed(op, error)

        # Should mark failed and record metrics
        assert (
            mock_operations_service._operations[op.operation_id].status
            == OperationStatus.FAILED
        )
        assert (
            "test error"
            in mock_operations_service._operations[op.operation_id].error_message
        )
        mock_metrics.assert_called_once_with("failed")

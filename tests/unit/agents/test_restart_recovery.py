"""Tests for M6: Coordinator Restart Recovery.

Goal: If backend restarts while researches are active, they resume automatically.
Orphaned in-process tasks (design/assessment) are detected and restarted.

Test categories:
- TestOrphanedDesignDetection: Detect orphaned design tasks
- TestOrphanedAssessmentDetection: Detect orphaned assessment tasks
- TestOrphanRestart: Orphan detection triggers phase restart
- TestTrainingNotOrphaned: Training/backtest on workers are not orphaned
- TestOldChildMarkedFailed: Orphaned child operation marked failed
"""

import asyncio
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
# TestOrphanedDesignDetection
# ============================================================================


class TestOrphanedDesignDetection:
    """Tests for detecting orphaned design tasks after restart."""

    @pytest.mark.asyncio
    async def test_orphaned_design_detected_running_child_no_task(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """Orphaned design task detected: child RUNNING but not in _child_tasks."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )

        # Create parent research operation in designing phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "designing", "design_op_id": "child_design_1"}
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        # Create a RUNNING child design operation
        child_op = OperationInfo(
            operation_id="child_design_1",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_design_1"] = child_op

        # Crucially: _child_tasks is EMPTY (simulating restart)
        assert parent_op.operation_id not in worker._child_tasks

        # Track if _start_design was called (orphan recovery)
        start_design_called = False

        async def track_start_design(op_id):
            nonlocal start_design_called
            start_design_called = True

        worker._start_design = track_start_design

        # Single call to _advance_research (not the full loop)
        await worker._advance_research(parent_op)

        # Orphaned child should be marked FAILED
        assert child_op.status == OperationStatus.FAILED
        assert "orphaned" in child_op.error_message.lower()

        # Design phase should be restarted
        assert start_design_called

    @pytest.mark.asyncio
    async def test_design_with_task_not_considered_orphan(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Design with active task is NOT orphaned."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create parent operation
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "designing", "design_op_id": "child_design_2"}
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        # Create child operation
        child_op = OperationInfo(
            operation_id="child_design_2",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_design_2"] = child_op

        # Simulate an active task exists for this operation
        async def fake_task():
            await asyncio.sleep(100)

        task = asyncio.create_task(fake_task())
        worker._child_tasks[parent_op.operation_id] = task

        try:
            # Track fail_operation calls
            fail_calls = []
            original_fail = mock_operations_service.fail_operation

            async def track_fail(op_id, error=None):
                fail_calls.append(op_id)
                await original_fail(op_id, error)

            mock_operations_service.fail_operation = track_fail

            # Single advance - should NOT detect orphan
            await worker._advance_research(parent_op)

            # Child should NOT be marked failed (not orphaned)
            assert child_op.status == OperationStatus.RUNNING
            assert "child_design_2" not in fail_calls
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected during test cleanup: fake_task was explicitly cancelled


# ============================================================================
# TestOrphanedAssessmentDetection
# ============================================================================


class TestOrphanedAssessmentDetection:
    """Tests for detecting orphaned assessment tasks after restart."""

    @pytest.mark.asyncio
    async def test_orphaned_assessment_detected(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """Orphaned assessment task detected: child RUNNING but not in _child_tasks."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )

        # Create parent research in assessing phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "assessment_op_id": "child_assess_1",
                    "training_result": {"accuracy": 0.85},
                    "backtest_result": {"sharpe_ratio": 1.5},
                }
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        # Create a RUNNING child assessment operation
        child_op = OperationInfo(
            operation_id="child_assess_1",
            operation_type=OperationType.AGENT_ASSESSMENT,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_assess_1"] = child_op

        # _child_tasks is EMPTY (simulating restart)
        assert parent_op.operation_id not in worker._child_tasks

        # Track if _start_assessment was called
        start_assessment_called = False

        async def track_start_assessment(op_id, gate_rejection_reason=None):
            nonlocal start_assessment_called
            start_assessment_called = True

        worker._start_assessment = track_start_assessment

        # Single call to _advance_research
        await worker._advance_research(parent_op)

        # Orphaned child should be marked FAILED
        assert child_op.status == OperationStatus.FAILED
        assert "orphaned" in child_op.error_message.lower()

        # Assessment phase should be restarted
        assert start_assessment_called


# ============================================================================
# TestTrainingNotOrphaned
# ============================================================================


class TestTrainingNotOrphaned:
    """Tests verifying training/backtest phases are NOT considered orphaned."""

    @pytest.mark.asyncio
    async def test_training_not_affected_by_orphan_detection(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Training on worker is NOT orphaned (runs on separate process)."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create parent research in training phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "training", "training_op_id": "child_train_1"}
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        # Create a RUNNING child training operation
        child_op = OperationInfo(
            operation_id="child_train_1",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_train_1"] = child_op

        # _child_tasks is EMPTY - but this is NORMAL for training (runs on worker)
        assert parent_op.operation_id not in worker._child_tasks

        # Track fail_operation calls
        fail_calls = []
        original_fail = mock_operations_service.fail_operation

        async def track_fail(op_id, error=None):
            fail_calls.append(op_id)
            await original_fail(op_id, error)

        mock_operations_service.fail_operation = track_fail

        # Single advance - should NOT detect orphan for training
        await worker._advance_research(parent_op)

        # Training child should NOT be marked failed
        assert child_op.status == OperationStatus.RUNNING
        assert "child_train_1" not in fail_calls

    @pytest.mark.asyncio
    async def test_backtesting_not_affected_by_orphan_detection(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Backtesting on worker is NOT orphaned (runs on separate process)."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create parent research in backtesting phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "backtesting",
                    "backtest_op_id": "child_backtest_1",
                }
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        # Create a RUNNING child backtest operation
        child_op = OperationInfo(
            operation_id="child_backtest_1",
            operation_type=OperationType.BACKTESTING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_backtest_1"] = child_op

        # _child_tasks is EMPTY - but this is NORMAL for backtest
        assert parent_op.operation_id not in worker._child_tasks

        # Track fail_operation calls
        fail_calls = []
        original_fail = mock_operations_service.fail_operation

        async def track_fail(op_id, error=None):
            fail_calls.append(op_id)
            await original_fail(op_id, error)

        mock_operations_service.fail_operation = track_fail

        # Single advance - should NOT detect orphan for backtesting
        await worker._advance_research(parent_op)

        # Backtest child should NOT be marked failed
        assert child_op.status == OperationStatus.RUNNING
        assert "child_backtest_1" not in fail_calls


# ============================================================================
# TestOldChildMarkedFailed
# ============================================================================


class TestOldChildMarkedFailed:
    """Tests verifying orphaned child operations are marked failed."""

    @pytest.mark.asyncio
    async def test_orphan_child_marked_failed_with_clear_message(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Orphaned child operation is marked FAILED with clear error message."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create parent research in designing phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "designing", "design_op_id": "orphan_child_1"}
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        # Create a RUNNING child operation (orphaned)
        child_op = OperationInfo(
            operation_id="orphan_child_1",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["orphan_child_1"] = child_op

        # No task exists (simulating restart)
        assert parent_op.operation_id not in worker._child_tasks

        # Mock _start_design to do nothing
        worker._start_design = AsyncMock()

        # Single call to _advance_research
        await worker._advance_research(parent_op)

        # Child should be FAILED
        assert child_op.status == OperationStatus.FAILED

        # Error message should mention restart/orphan
        error_msg = child_op.error_message.lower()
        assert "orphaned" in error_msg or "restart" in error_msg


class TestOrphanDetectionLogging:
    """Tests for orphan detection logging."""

    @pytest.mark.asyncio
    async def test_orphan_detection_logs_warning(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        caplog,
    ):
        """Orphan detection logs a warning message."""
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create parent research in designing phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "designing", "design_op_id": "child_log_test"}
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        # Create a RUNNING child operation (orphaned)
        child_op = OperationInfo(
            operation_id="child_log_test",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["child_log_test"] = child_op

        # No task exists
        assert parent_op.operation_id not in worker._child_tasks

        # Mock _start_design to do nothing
        worker._start_design = AsyncMock()

        # Single call to _advance_research
        await worker._advance_research(parent_op)

        # Should log warning about orphan
        assert any(
            "orphan" in record.message.lower() for record in caplog.records
        ), f"Expected 'orphan' in logs, got: {[r.message for r in caplog.records]}"


# ============================================================================
# TestStartupResume
# ============================================================================


class TestStartupResume:
    """Tests for startup hook resumption via AgentService.resume_if_needed()."""

    @pytest.fixture
    def mock_agent_service(self, mock_operations_service):
        """Create a mock agent service for testing resume_if_needed."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)
        return service

    @pytest.mark.asyncio
    async def test_resume_starts_coordinator_when_active_ops_exist(
        self,
        mock_operations_service,
        mock_agent_service,
    ):
        """resume_if_needed starts coordinator when active operations exist."""
        # Create an active research operation
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        parent_op.status = OperationStatus.RUNNING

        # Verify coordinator not running initially
        assert mock_agent_service._coordinator_task is None

        # Call resume_if_needed
        await mock_agent_service.resume_if_needed()

        # Coordinator should be started
        assert mock_agent_service._coordinator_task is not None
        assert not mock_agent_service._coordinator_task.done()

        # Cleanup - cancel the coordinator task
        mock_agent_service._coordinator_task.cancel()
        try:
            await mock_agent_service._coordinator_task
        except asyncio.CancelledError:
            pass  # Expected during cleanup: coordinator task was explicitly cancelled

    @pytest.mark.asyncio
    async def test_resume_noop_when_no_active_ops(
        self,
        mock_operations_service,
        mock_agent_service,
    ):
        """resume_if_needed does nothing when no active operations exist."""
        # No operations in system - operations dict is empty
        assert len(mock_operations_service._operations) == 0

        # Call resume_if_needed
        await mock_agent_service.resume_if_needed()

        # Coordinator should NOT be started
        assert mock_agent_service._coordinator_task is None

    @pytest.mark.asyncio
    async def test_resume_noop_when_only_completed_ops(
        self,
        mock_operations_service,
        mock_agent_service,
    ):
        """resume_if_needed does nothing when only completed operations exist."""
        # Create a completed research operation
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "complete"}),
        )
        parent_op.status = OperationStatus.COMPLETED

        # Call resume_if_needed
        await mock_agent_service.resume_if_needed()

        # Coordinator should NOT be started
        assert mock_agent_service._coordinator_task is None

    @pytest.mark.asyncio
    async def test_resume_detects_orphans_on_first_cycle(
        self,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
        mock_checkpoint_service,
    ):
        """Resumed coordinator detects orphaned tasks on first cycle.

        When coordinator resumes and finds orphaned in-process tasks,
        it should detect and handle them.
        """
        # Setup: Create research in designing phase with orphaned child
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "designing", "design_op_id": "orphan_on_resume"}
            ),
        )
        parent_op.status = OperationStatus.RUNNING

        child_op = OperationInfo(
            operation_id="orphan_on_resume",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations["orphan_on_resume"] = child_op

        # Create fresh coordinator (simulates restart - no _child_tasks)
        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
            checkpoint_service=mock_checkpoint_service,
        )
        worker.POLL_INTERVAL = 0.01

        # Track design restarts
        design_restarted = False

        async def track_restart(op_id):
            nonlocal design_restarted
            design_restarted = True
            # Complete operation to exit loop
            parent_op.status = OperationStatus.COMPLETED

        worker._start_design = track_restart

        # Run coordinator (simulates what happens after resume_if_needed)
        await worker.run()

        # Orphan should be detected and phase restarted
        assert child_op.status == OperationStatus.FAILED
        assert "orphaned" in child_op.error_message.lower()
        assert design_restarted

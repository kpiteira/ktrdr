"""Tests for multi-research coordinator functionality.

Task 1.8 of M1: Comprehensive tests for the coordinator loop that manages
multiple concurrent research operations.

Test categories:
- TestMultiResearchCoordinator: Core coordinator loop functionality
- TestCapacityCheck: Concurrency limit and capacity checking
- TestCoordinatorLifecycle: Start/stop/resume behavior
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


# ============================================================================
# TestMultiResearchCoordinator
# ============================================================================


class TestMultiResearchCoordinator:
    """Tests for multi-research coordinator loop."""

    @pytest.mark.asyncio
    async def test_get_active_research_operations_returns_running(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_get_active_research_operations() returns RUNNING operations."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create a RUNNING operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        active_ops = await worker._get_active_research_operations()

        assert len(active_ops) == 1
        assert active_ops[0].operation_id == op.operation_id

    @pytest.mark.asyncio
    async def test_get_active_research_operations_returns_pending(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_get_active_research_operations() returns PENDING operations."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create a PENDING operation
        await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        active_ops = await worker._get_active_research_operations()

        assert len(active_ops) == 1
        assert active_ops[0].status == OperationStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_active_research_operations_excludes_completed(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_get_active_research_operations() excludes COMPLETED operations."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create a COMPLETED operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "assessing"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.COMPLETED
        )

        active_ops = await worker._get_active_research_operations()

        assert len(active_ops) == 0

    @pytest.mark.asyncio
    async def test_get_active_research_operations_returns_multiple(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_get_active_research_operations() returns all active operations."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create multiple active operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        mock_operations_service._operations[op1.operation_id].status = (
            OperationStatus.RUNNING
        )

        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op2.operation_id].status = (
            OperationStatus.RUNNING
        )

        await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        # Third op stays PENDING

        active_ops = await worker._get_active_research_operations()

        assert len(active_ops) == 3

    @pytest.mark.asyncio
    async def test_advance_research_calls_correct_phase_handler_idle(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_advance_research() routes idle phase to _start_design()."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create an operation in idle phase
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Mock _start_design to verify it gets called
        with patch.object(
            worker, "_start_design", new_callable=AsyncMock
        ) as mock_start:
            await worker._advance_research(op)
            mock_start.assert_called_once_with(op.operation_id)

    @pytest.mark.asyncio
    async def test_advance_research_calls_correct_phase_handler_designing(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_advance_research() routes designing phase to _handle_designing_phase()."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create an operation in designing phase with child op
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "designing", "design_op_id": "op_design_123"}
            ),
        )

        # Mock phase handler to verify it gets called
        with patch.object(
            worker, "_handle_designing_phase", new_callable=AsyncMock
        ) as mock_handler:
            await worker._advance_research(op)
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_advance_research_calls_correct_phase_handler_training(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_advance_research() routes training phase to _handle_training_phase()."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create an operation in training phase
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "training", "training_op_id": "op_training_123"}
            ),
        )

        with patch.object(
            worker, "_handle_training_phase", new_callable=AsyncMock
        ) as mock_handler:
            await worker._advance_research(op)
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_advance_research_calls_correct_phase_handler_backtesting(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_advance_research() routes backtesting phase to _handle_backtesting_phase()."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create an operation in backtesting phase
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "backtesting", "backtest_op_id": "op_backtest_123"}
            ),
        )

        with patch.object(
            worker, "_handle_backtesting_phase", new_callable=AsyncMock
        ) as mock_handler:
            await worker._advance_research(op)
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_advance_research_calls_correct_phase_handler_assessing(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_advance_research() routes assessing phase to _handle_assessing_phase()."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create an operation in assessing phase
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "assessment_op_id": "op_assessment_123",
                }
            ),
        )

        with patch.object(
            worker, "_handle_assessing_phase", new_callable=AsyncMock
        ) as mock_handler:
            await worker._advance_research(op)
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_loop_exits_when_no_active_ops(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """Coordinator run() exits when no active operations remain."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0.01  # Fast for testing

        # No operations - should exit immediately
        await worker.run()

        # If we get here, the loop exited correctly
        assert True

    @pytest.mark.asyncio
    async def test_loop_processes_all_active_operations(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """Coordinator processes all active operations in one cycle."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
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

        # Track which operations got advanced
        advanced_ops = []

        async def track_advance(op):
            advanced_ops.append(op.operation_id)
            # Complete the operation to exit the loop
            mock_operations_service._operations[op.operation_id].status = (
                OperationStatus.COMPLETED
            )

        with patch.object(worker, "_advance_research", side_effect=track_advance):
            await worker.run()

        # Both operations should have been processed
        assert op1.operation_id in advanced_ops
        assert op2.operation_id in advanced_ops

    @pytest.mark.asyncio
    async def test_one_research_completing_doesnt_stop_loop(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """Loop continues after one research completes."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
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

        cycle_count = 0
        op1_completed = False

        async def advance_with_completion(op):
            nonlocal cycle_count, op1_completed

            if op.operation_id == op1.operation_id:
                if not op1_completed:
                    # Complete op1 on first advance
                    mock_operations_service._operations[op1.operation_id].status = (
                        OperationStatus.COMPLETED
                    )
                    op1_completed = True
            else:
                # op2 - complete on second cycle
                cycle_count += 1
                if cycle_count >= 2:
                    mock_operations_service._operations[op2.operation_id].status = (
                        OperationStatus.COMPLETED
                    )

        with patch.object(
            worker, "_advance_research", side_effect=advance_with_completion
        ):
            await worker.run()

        # Loop should have continued to process op2 after op1 completed
        assert op1_completed
        assert cycle_count >= 1

    @pytest.mark.asyncio
    async def test_get_child_op_id_returns_correct_key_for_phase(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """_get_child_op_id() returns correct child op ID for each phase."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create operation with all child op IDs
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "design_op_id": "op_design_1",
                    "training_op_id": "op_training_2",
                    "backtest_op_id": "op_backtest_3",
                    "assessment_op_id": "op_assessment_4",
                }
            ),
        )

        assert worker._get_child_op_id(op, "designing") == "op_design_1"
        assert worker._get_child_op_id(op, "training") == "op_training_2"
        assert worker._get_child_op_id(op, "backtesting") == "op_backtest_3"
        assert worker._get_child_op_id(op, "assessing") == "op_assessment_4"
        assert worker._get_child_op_id(op, "idle") is None


# ============================================================================
# TestCapacityCheck
# ============================================================================


class TestCapacityCheck:
    """Tests for concurrency limit and capacity checking."""

    @pytest.fixture(autouse=True)
    def use_stub_workers(self, monkeypatch):
        """Use stub workers to avoid real API calls."""
        monkeypatch.setenv("USE_STUB_WORKERS", "true")
        monkeypatch.setenv("STUB_WORKER_FAST", "true")

    @pytest.fixture(autouse=True)
    def mock_budget(self):
        """Mock budget tracker to allow triggers."""
        mock_tracker = MagicMock()
        mock_tracker.can_spend.return_value = (True, None)

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_tracker,
        ):
            yield mock_tracker

    @pytest.mark.asyncio
    async def test_trigger_succeeds_under_capacity(self, mock_operations_service):
        """Triggers allowed when under limit."""
        from ktrdr.api.services.agent_service import AgentService

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = [
            MagicMock(),
            MagicMock(),
        ]  # 2 workers

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)

            result = await service.trigger()

            assert result["triggered"] is True

    @pytest.mark.asyncio
    async def test_trigger_rejected_at_capacity(
        self, mock_operations_service, monkeypatch
    ):
        """Returns at_capacity when limit reached."""
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "1")

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)

            # First trigger succeeds
            result1 = await service.trigger()
            assert result1["triggered"] is True

            # Mark as running
            op_id = result1["operation_id"]
            mock_operations_service._operations[op_id].status = OperationStatus.RUNNING

            # Second trigger should fail
            result2 = await service.trigger()

            assert result2["triggered"] is False
            assert result2["reason"] == "at_capacity"
            assert result2["active_count"] == 1
            assert result2["limit"] == 1

    @pytest.mark.asyncio
    async def test_capacity_from_workers(self, mock_operations_service, monkeypatch):
        """Limit calculated from worker pool."""
        from ktrdr.api.services.agent_service import AgentService

        # Clear override to use worker calculation
        monkeypatch.delenv("AGENT_MAX_CONCURRENT_RESEARCHES", raising=False)

        mock_registry = MagicMock()
        # 2 training + 3 backtest = 5, plus buffer(1) = 6
        mock_registry.list_workers.side_effect = lambda worker_type: (
            [MagicMock()] * 2 if worker_type.value == "training" else [MagicMock()] * 3
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            limit = service._get_concurrency_limit()

            # 2 + 3 + 1 (buffer) = 6
            assert limit == 6

    @pytest.mark.asyncio
    async def test_capacity_override_env_var(
        self, mock_operations_service, monkeypatch
    ):
        """AGENT_MAX_CONCURRENT_RESEARCHES overrides calculation."""
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "10")

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = [MagicMock()]  # Would give 3 normally

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            limit = service._get_concurrency_limit()

            assert limit == 10

    @pytest.mark.asyncio
    async def test_capacity_minimum_is_one(self, mock_operations_service, monkeypatch):
        """Returns minimum 1 when no workers registered."""
        from ktrdr.api.services.agent_service import AgentService

        # Clear override
        monkeypatch.delenv("AGENT_MAX_CONCURRENT_RESEARCHES", raising=False)
        monkeypatch.setenv("AGENT_CONCURRENCY_BUFFER", "0")

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []  # No workers

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            limit = service._get_concurrency_limit()

            assert limit == 1  # Minimum of 1


# ============================================================================
# TestCoordinatorLifecycle
# ============================================================================


class TestCoordinatorLifecycle:
    """Tests for coordinator start/stop behavior."""

    @pytest.fixture(autouse=True)
    def use_stub_workers(self, monkeypatch):
        """Use stub workers to avoid real API calls."""
        monkeypatch.setenv("USE_STUB_WORKERS", "true")
        monkeypatch.setenv("STUB_WORKER_FAST", "true")

    @pytest.fixture(autouse=True)
    def mock_budget(self):
        """Mock budget tracker to allow triggers."""
        mock_tracker = MagicMock()
        mock_tracker.can_spend.return_value = (True, None)

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_tracker,
        ):
            yield mock_tracker

    @pytest.mark.asyncio
    async def test_first_trigger_starts_coordinator(self, mock_operations_service):
        """Coordinator starts on first trigger."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Initially no coordinator
        assert service._coordinator_task is None

        await service.trigger()

        # Coordinator should be started
        assert service._coordinator_task is not None

    @pytest.mark.asyncio
    async def test_second_trigger_reuses_coordinator(self, mock_operations_service):
        """No duplicate coordinators created."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # First trigger
        await service.trigger()
        first_task = service._coordinator_task

        # Second trigger
        await service.trigger()
        second_task = service._coordinator_task

        # Should be the same task
        assert first_task is second_task

    @pytest.mark.asyncio
    async def test_resume_if_needed_starts_coordinator(self, mock_operations_service):
        """Startup hook starts coordinator when ops exist."""
        from ktrdr.api.services.agent_service import AgentService

        # Create an active operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        service = AgentService(operations_service=mock_operations_service)

        # Initially no coordinator
        assert service._coordinator_task is None

        # Call resume_if_needed
        await service.resume_if_needed()

        # Coordinator should be started
        assert service._coordinator_task is not None

    @pytest.mark.asyncio
    async def test_resume_if_needed_does_nothing_when_no_ops(
        self, mock_operations_service
    ):
        """Startup hook does nothing when no active ops."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # No active operations
        await service.resume_if_needed()

        # Coordinator should NOT be started
        assert service._coordinator_task is None

    @pytest.mark.asyncio
    async def test_coordinator_task_tracked(self, mock_operations_service):
        """Coordinator task is tracked in _coordinator_task."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        await service.trigger()

        # Task should be tracked
        assert service._coordinator_task is not None
        assert isinstance(service._coordinator_task, asyncio.Task)

    @pytest.mark.asyncio
    async def test_new_coordinator_starts_when_previous_done(
        self, mock_operations_service
    ):
        """New coordinator starts if previous completed."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Simulate a completed coordinator task
        mock_task = MagicMock()
        mock_task.done.return_value = True
        service._coordinator_task = mock_task

        # Create an active operation for resume
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        # Call resume_if_needed - should start new coordinator
        await service.resume_if_needed()

        # Should have started a new coordinator
        assert service._coordinator_task is not mock_task

    @pytest.mark.asyncio
    async def test_resume_if_needed_handles_missing_tables_gracefully(self):
        """Startup hook handles missing database tables gracefully.

        On fresh install before alembic migrations, the operations table
        doesn't exist. resume_if_needed should log a warning and continue
        instead of crashing the backend startup.
        """
        from unittest.mock import AsyncMock, MagicMock

        from ktrdr.api.services.agent_service import AgentService

        # Create a mock operations service that raises "table does not exist"
        mock_ops = MagicMock()
        mock_ops.list_operations = AsyncMock(
            side_effect=Exception('relation "operations" does not exist')
        )

        service = AgentService(operations_service=mock_ops)

        # Should NOT raise - should handle gracefully
        await service.resume_if_needed()

        # Coordinator should NOT be started (we couldn't check for ops)
        assert service._coordinator_task is None


# ============================================================================
# TestOperationCompletion
# ============================================================================


class TestOperationCompletion:
    """Tests for operation completion handling inside coordinator loop."""

    @pytest.mark.asyncio
    async def test_assessment_completion_marks_operation_complete(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """Assessment completion marks operation as COMPLETED."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create parent operation in assessing phase
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "strategy_name": "test_strategy",
                    "assessment_op_id": "op_assessment_1",
                }
            ),
        )
        mock_operations_service._operations[parent_op.operation_id].status = (
            OperationStatus.RUNNING
        )

        # Create completed child assessment operation
        child_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_ASSESSMENT,
            metadata=OperationMetadata(),
            parent_operation_id=parent_op.operation_id,
        )
        mock_operations_service._operations[child_op.operation_id].status = (
            OperationStatus.COMPLETED
        )
        mock_operations_service._operations[child_op.operation_id].result_summary = {
            "verdict": "PROMISING",
            "input_tokens": 100,
            "output_tokens": 50,
        }

        # Handle assessing phase
        with (
            patch("ktrdr.agents.workers.research_worker.record_cycle_duration"),
            patch("ktrdr.agents.workers.research_worker.record_cycle_outcome"),
        ):
            await worker._handle_assessing_phase(parent_op.operation_id, child_op)

        # Parent should be COMPLETED
        assert (
            mock_operations_service._operations[parent_op.operation_id].status
            == OperationStatus.COMPLETED
        )

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_completion(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """Metrics are recorded when research completes."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create parent operation
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "strategy_name": "test_strategy",
                    "assessment_op_id": "op_assessment_1",
                }
            ),
        )
        mock_operations_service._operations[parent_op.operation_id].status = (
            OperationStatus.RUNNING
        )

        # Create completed child
        child_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_ASSESSMENT,
            metadata=OperationMetadata(),
        )
        mock_operations_service._operations[child_op.operation_id].status = (
            OperationStatus.COMPLETED
        )
        mock_operations_service._operations[child_op.operation_id].result_summary = {
            "verdict": "PROMISING"
        }

        with (
            patch(
                "ktrdr.agents.workers.research_worker.record_cycle_duration"
            ) as mock_duration,
            patch(
                "ktrdr.agents.workers.research_worker.record_cycle_outcome"
            ) as mock_outcome,
        ):
            await worker._handle_assessing_phase(parent_op.operation_id, child_op)

        # Metrics should be recorded
        mock_duration.assert_called_once()
        mock_outcome.assert_called_once_with("completed")

    @pytest.mark.asyncio
    async def test_other_researches_continue_after_one_completes(
        self, mock_operations_service, mock_design_worker, mock_assessment_worker
    ):
        """Other researches are not affected by one completing."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
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

        advance_calls = {op1.operation_id: 0, op2.operation_id: 0}

        async def track_and_complete(op):
            advance_calls[op.operation_id] += 1

            # Complete op1 immediately
            if op.operation_id == op1.operation_id:
                mock_operations_service._operations[op1.operation_id].status = (
                    OperationStatus.COMPLETED
                )
            # Complete op2 on second call
            elif advance_calls[op2.operation_id] >= 2:
                mock_operations_service._operations[op2.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        with patch.object(worker, "_advance_research", side_effect=track_and_complete):
            await worker.run()

        # op1 should only be advanced once (before completion)
        assert advance_calls[op1.operation_id] == 1
        # op2 should be advanced multiple times (continuing after op1 completes)
        assert advance_calls[op2.operation_id] >= 2

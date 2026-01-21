"""Integration tests for multi-research coordinator.

Task 1.8 of M1: Verify multiple researches can progress concurrently
and both complete successfully.

Uses stub workers for speed and reliability.
"""

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


# ============================================================================
# Integration Tests
# ============================================================================


class TestMultiResearchIntegration:
    """Integration tests for multi-research concurrent execution."""

    @pytest.fixture(autouse=True)
    def use_stub_workers(self, monkeypatch):
        """Use stub workers to avoid real API calls."""
        monkeypatch.setenv("USE_STUB_WORKERS", "true")
        monkeypatch.setenv("STUB_WORKER_FAST", "true")
        monkeypatch.setenv("AGENT_POLL_INTERVAL", "0.1")

    @pytest.fixture(autouse=True)
    def mock_budget(self):
        """Mock budget tracker to allow triggers."""
        mock_tracker = MagicMock()
        mock_tracker.can_spend.return_value = (True, None)
        mock_tracker.record_spend = MagicMock()

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_tracker,
        ):
            yield mock_tracker

    @pytest.mark.asyncio
    async def test_two_triggers_both_succeed(
        self, mock_operations_service, monkeypatch
    ):
        """Two researches can be triggered (not rejected)."""
        from ktrdr.api.services.agent_service import AgentService

        # Set high capacity
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "5")

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)

            # Trigger first research
            result1 = await service.trigger(brief="Research 1")
            assert result1["triggered"] is True
            assert "operation_id" in result1

            # Trigger second research
            result2 = await service.trigger(brief="Research 2")
            assert result2["triggered"] is True
            assert "operation_id" in result2

            # Verify different operation IDs
            assert result1["operation_id"] != result2["operation_id"]

    @pytest.mark.asyncio
    async def test_coordinator_processes_multiple_operations(
        self, mock_operations_service
    ):
        """Coordinator loop processes multiple operations."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        # Create mock workers
        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
        )
        worker.POLL_INTERVAL = 0.05

        # Create two research operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        await mock_operations_service.start_operation(op1.operation_id)

        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        await mock_operations_service.start_operation(op2.operation_id)

        # Track advance calls
        advanced_ops = set()

        async def track_and_complete(op):
            advanced_ops.add(op.operation_id)
            # Complete after one advance
            mock_operations_service._operations[op.operation_id].status = (
                OperationStatus.COMPLETED
            )

        with patch.object(worker, "_advance_research", side_effect=track_and_complete):
            await worker.run()

        # Both operations should have been advanced
        assert op1.operation_id in advanced_ops
        assert op2.operation_id in advanced_ops

    @pytest.mark.asyncio
    async def test_capacity_enforcement_at_limit(
        self, mock_operations_service, monkeypatch
    ):
        """Third trigger rejected when at capacity of 2."""
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "2")

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)

            # Trigger two (should succeed)
            result1 = await service.trigger(brief="Research 1")
            mock_operations_service._operations[result1["operation_id"]].status = (
                OperationStatus.RUNNING
            )

            result2 = await service.trigger(brief="Research 2")
            mock_operations_service._operations[result2["operation_id"]].status = (
                OperationStatus.RUNNING
            )

            assert result1["triggered"] is True
            assert result2["triggered"] is True

            # Third should be rejected
            result3 = await service.trigger(brief="Research 3")

            assert result3["triggered"] is False
            assert result3["reason"] == "at_capacity"
            assert result3["active_count"] == 2
            assert result3["limit"] == 2

    @pytest.mark.asyncio
    async def test_slot_opens_after_completion(
        self, mock_operations_service, monkeypatch
    ):
        """New trigger allowed after a research completes (slot opens)."""
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "1")

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)

            # First trigger
            result1 = await service.trigger(brief="Research 1")
            assert result1["triggered"] is True

            # Mark first as running
            mock_operations_service._operations[result1["operation_id"]].status = (
                OperationStatus.RUNNING
            )

            # Second trigger fails (at capacity)
            result2 = await service.trigger(brief="Research 2")
            assert result2["triggered"] is False
            assert result2["reason"] == "at_capacity"

            # Complete first research
            mock_operations_service._operations[result1["operation_id"]].status = (
                OperationStatus.COMPLETED
            )

            # Third trigger succeeds (slot opened)
            result3 = await service.trigger(brief="Research 3")
            assert result3["triggered"] is True

    @pytest.mark.asyncio
    async def test_coordinator_lifecycle_with_multiple_triggers(
        self, mock_operations_service, monkeypatch
    ):
        """Coordinator starts once and handles multiple triggers."""
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "5")

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)

            # Initially no coordinator
            assert service._coordinator_task is None

            # First trigger starts coordinator
            await service.trigger(brief="Research 1")
            first_coordinator = service._coordinator_task
            assert first_coordinator is not None

            # Second trigger reuses same coordinator
            await service.trigger(brief="Research 2")
            assert service._coordinator_task is first_coordinator

    @pytest.mark.asyncio
    async def test_resume_if_needed_with_multiple_active_ops(
        self, mock_operations_service
    ):
        """resume_if_needed() starts coordinator when multiple ops exist."""
        from ktrdr.api.services.agent_service import AgentService

        # Create two active operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op1.operation_id].status = (
            OperationStatus.RUNNING
        )

        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "backtesting"}),
        )
        mock_operations_service._operations[op2.operation_id].status = (
            OperationStatus.RUNNING
        )

        service = AgentService(operations_service=mock_operations_service)

        # Call resume
        await service.resume_if_needed()

        # Coordinator should be started
        assert service._coordinator_task is not None

    @pytest.mark.asyncio
    async def test_get_all_active_research_ops_returns_all_statuses(
        self, mock_operations_service
    ):
        """_get_all_active_research_ops() returns RUNNING, RESUMING, and PENDING."""
        from ktrdr.api.services.agent_service import AgentService

        # Create ops in different states
        op_running = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op_running.operation_id].status = (
            OperationStatus.RUNNING
        )

        op_pending = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        # Stays PENDING

        op_completed = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "assessing"}),
        )
        mock_operations_service._operations[op_completed.operation_id].status = (
            OperationStatus.COMPLETED
        )

        service = AgentService(operations_service=mock_operations_service)
        active_ops = await service._get_all_active_research_ops()

        # Should have RUNNING and PENDING, but not COMPLETED
        active_ids = [op.operation_id for op in active_ops]
        assert op_running.operation_id in active_ids
        assert op_pending.operation_id in active_ids
        assert op_completed.operation_id not in active_ids


class TestMultiResearchConcurrentProgress:
    """Tests for concurrent research progress through phases."""

    @pytest.fixture(autouse=True)
    def fast_polling(self, monkeypatch):
        """Use fast polling for tests."""
        monkeypatch.setenv("AGENT_POLL_INTERVAL", "0.05")

    @pytest.mark.asyncio
    async def test_researches_advance_independently(self, mock_operations_service):
        """Each research advances through phases independently."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
        )
        worker.POLL_INTERVAL = 0.05

        # Create two operations at different phases
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        await mock_operations_service.start_operation(op1.operation_id)

        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        await mock_operations_service.start_operation(op2.operation_id)

        # Track phases that get handled
        handled_phases = {op1.operation_id: [], op2.operation_id: []}

        async def track_advance(op):
            phase = op.metadata.parameters.get("phase", "unknown")
            handled_phases[op.operation_id].append(phase)
            # Complete after recording
            mock_operations_service._operations[op.operation_id].status = (
                OperationStatus.COMPLETED
            )

        with patch.object(worker, "_advance_research", side_effect=track_advance):
            await worker.run()

        # Each operation should have its phase recorded
        assert "designing" in handled_phases[op1.operation_id]
        assert "training" in handled_phases[op2.operation_id]

    @pytest.mark.asyncio
    async def test_failed_research_doesnt_stop_others(self, mock_operations_service):
        """A failed research doesn't stop the coordinator from processing others."""
        from ktrdr.agents.workers.research_worker import (
            AgentResearchWorker,
            WorkerError,
        )

        mock_design = AsyncMock()
        mock_assessment = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design,
            assessment_worker=mock_assessment,
        )
        worker.POLL_INTERVAL = 0.05

        # Create two operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        await mock_operations_service.start_operation(op1.operation_id)

        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        await mock_operations_service.start_operation(op2.operation_id)

        op2_processed = False

        async def fail_first_complete_second(op):
            nonlocal op2_processed

            if op.operation_id == op1.operation_id:
                # Fail op1
                raise WorkerError("Simulated failure")
            else:
                # Complete op2
                op2_processed = True
                mock_operations_service._operations[op2.operation_id].status = (
                    OperationStatus.COMPLETED
                )

        with (
            patch.object(
                worker, "_advance_research", side_effect=fail_first_complete_second
            ),
            patch.object(worker, "_save_checkpoint", new_callable=AsyncMock),
        ):
            await worker.run()

        # op1 should be failed
        assert (
            mock_operations_service._operations[op1.operation_id].status
            == OperationStatus.FAILED
        )

        # op2 should have been processed and completed
        assert op2_processed
        assert (
            mock_operations_service._operations[op2.operation_id].status
            == OperationStatus.COMPLETED
        )

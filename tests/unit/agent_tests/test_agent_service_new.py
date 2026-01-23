"""Tests for the new AgentService (operations-only, no sessions).

Task 1.4 of M1: Verify the service layer works with OperationsService.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service for testing."""
    service = AsyncMock()

    # Track operations in memory
    operations: dict[str, OperationInfo] = {}
    operation_counter = 0

    def create_op(operation_type, metadata=None, parent_operation_id=None):
        """Create operation helper."""
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

    async def async_create_operation(
        operation_type, metadata=None, parent_operation_id=None, is_backend_local=False
    ):
        op = create_op(operation_type, metadata, parent_operation_id)
        op.is_backend_local = is_backend_local
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

        # Sort by created_at descending
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

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.complete_operation = async_complete_operation
    service.fail_operation = async_fail_operation
    service.cancel_operation = async_cancel_operation
    service.start_operation = async_start_operation
    service.list_operations = async_list_operations
    service._operations = operations

    return service


class TestAgentServiceTrigger:
    """Test trigger() method."""

    @pytest.fixture(autouse=True)
    def use_stub_workers(self, monkeypatch):
        """Use stub workers to avoid real API calls in unit tests."""
        monkeypatch.setenv("USE_STUB_WORKERS", "true")
        monkeypatch.setenv("STUB_WORKER_FAST", "true")

    @pytest.fixture(autouse=True)
    def mock_budget(self):
        """Mock budget tracker to allow triggers in tests."""
        from unittest.mock import MagicMock, patch

        mock_tracker = MagicMock()
        mock_tracker.can_spend.return_value = (True, None)

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_tracker,
        ):
            yield mock_tracker

    @pytest.mark.asyncio
    async def test_trigger_creates_agent_research_operation(
        self, mock_operations_service
    ):
        """Trigger creates AGENT_RESEARCH operation."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        result = await service.trigger()

        assert result["triggered"] is True
        assert "operation_id" in result
        assert result["operation_id"].startswith("op_agent_research")

    @pytest.mark.asyncio
    async def test_trigger_returns_operation_id(self, mock_operations_service):
        """Trigger returns operation_id for tracking."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        result = await service.trigger()

        assert "operation_id" in result
        # Verify operation exists
        op = await mock_operations_service.get_operation(result["operation_id"])
        assert op is not None
        assert op.operation_type == OperationType.AGENT_RESEARCH

    @pytest.mark.asyncio
    async def test_trigger_rejects_when_at_capacity(
        self, mock_operations_service, monkeypatch
    ):
        """Trigger returns triggered=False with at_capacity when at limit."""
        from unittest.mock import MagicMock, patch

        from ktrdr.api.services.agent_service import AgentService

        # Set capacity limit to 1 for this test
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "1")

        # Create mock worker registry (needed for capacity check)
        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)

            # First trigger should succeed
            result1 = await service.trigger()
            assert result1["triggered"] is True

            # Mark the operation as running (simulating started worker)
            op_id = result1["operation_id"]
            mock_operations_service._operations[op_id].status = OperationStatus.RUNNING

            # Second trigger should fail (at capacity with limit=1)
            result2 = await service.trigger()

            assert result2["triggered"] is False
            assert result2["reason"] == "at_capacity"
            assert result2["active_count"] == 1
            assert result2["limit"] == 1

    @pytest.mark.asyncio
    async def test_trigger_starts_worker_in_background(self, mock_operations_service):
        """Trigger starts the worker as a background task."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        result = await service.trigger()

        assert result["triggered"] is True

        # Allow background task to start
        await asyncio.sleep(0.1)

        # Operation should transition to running
        op = await mock_operations_service.get_operation(result["operation_id"])
        assert op.status in [
            OperationStatus.RUNNING,
            OperationStatus.COMPLETED,
        ]  # May complete quickly with stubs


class TestAgentServiceGetStatus:
    """Test get_status() method."""

    @pytest.mark.asyncio
    async def test_status_returns_idle_when_no_active_cycle(
        self, mock_operations_service
    ):
        """Status returns idle when no active cycle."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        status = await service.get_status()

        assert status["status"] == "idle"

    @pytest.mark.asyncio
    async def test_status_returns_active_when_cycle_running(
        self, mock_operations_service
    ):
        """Status returns active when cycle is running."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a running operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op.operation_id].started_at = datetime.now(
            timezone.utc
        )

        status = await service.get_status()

        assert status["status"] == "active"
        # M5: operation_id is now in active_researches list
        assert len(status["active_researches"]) == 1
        assert status["active_researches"][0]["operation_id"] == op.operation_id

    @pytest.mark.asyncio
    async def test_status_returns_phase_from_metadata(self, mock_operations_service):
        """Status returns current phase from operation metadata."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a running operation with phase
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "backtesting"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op.operation_id].started_at = datetime.now(
            timezone.utc
        )

        status = await service.get_status()

        # M5: phase is now in active_researches list
        assert status["active_researches"][0]["phase"] == "backtesting"

    @pytest.mark.asyncio
    async def test_status_returns_strategy_name_when_active(
        self, mock_operations_service
    ):
        """Status returns strategy_name from metadata when cycle is active (Task 2.3)."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a running operation with strategy_name in metadata
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "strategy_name": "momentum_rsi_v2",
                }
            ),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op.operation_id].started_at = datetime.now(
            timezone.utc
        )

        status = await service.get_status()

        assert status["status"] == "active"
        # M5: strategy_name is now in active_researches list
        assert status["active_researches"][0]["strategy_name"] == "momentum_rsi_v2"

    @pytest.mark.asyncio
    async def test_status_returns_last_cycle_when_idle(self, mock_operations_service):
        """Status returns last cycle info when idle."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a completed operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "completed"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.COMPLETED
        )
        mock_operations_service._operations[op.operation_id].result_summary = {
            "strategy_name": "test_strategy_v1"
        }
        mock_operations_service._operations[op.operation_id].completed_at = (
            datetime.now(timezone.utc)
        )

        status = await service.get_status()

        assert status["status"] == "idle"
        assert status["last_cycle"] is not None
        assert status["last_cycle"]["operation_id"] == op.operation_id
        assert status["last_cycle"]["outcome"] == "completed"
        assert status["last_cycle"]["strategy_name"] == "test_strategy_v1"


class TestAgentServiceMetadataContract:
    """Test metadata contract per ARCHITECTURE.md Task 1.13.

    Status response should include child_operation_id when active.
    M5: child_operation_id is now in active_researches list items.
    """

    @pytest.mark.asyncio
    async def test_status_includes_child_operation_id_when_active(
        self, mock_operations_service
    ):
        """Status response includes child_operation_id when cycle is active."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a running operation with child op ID in metadata
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "training_op_id": "op_training_123",
                }
            ),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op.operation_id].started_at = datetime.now(
            timezone.utc
        )

        status = await service.get_status()

        assert status["status"] == "active"
        # M5: child_operation_id is now in active_researches list
        assert len(status["active_researches"]) == 1
        assert "child_operation_id" in status["active_researches"][0]
        assert status["active_researches"][0]["child_operation_id"] == "op_training_123"

    @pytest.mark.asyncio
    async def test_status_child_operation_id_matches_current_phase(
        self, mock_operations_service
    ):
        """child_operation_id matches the current phase's child operation."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create operation in backtesting phase
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "backtesting",
                    "design_op_id": "op_agent_design_1",
                    "training_op_id": "op_training_2",
                    "backtest_op_id": "op_backtesting_3",
                }
            ),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op.operation_id].started_at = datetime.now(
            timezone.utc
        )

        status = await service.get_status()

        # M5: child_operation_id is in active_researches list
        # Should return the backtest child, not design or training
        assert (
            status["active_researches"][0]["child_operation_id"] == "op_backtesting_3"
        )


class TestAgentServiceNoResearchAgentsImports:
    """Verify no imports from research_agents package."""

    def test_no_research_agents_imports(self):
        """AgentService should not import from research_agents."""
        import ast
        from pathlib import Path

        service_path = Path("ktrdr/api/services/agent_service.py")
        content = service_path.read_text()
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(
                        "research_agents"
                    ), f"Found research_agents import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(
                        "research_agents"
                    ), f"Found research_agents import: from {node.module}"


class TestAgentServiceDesignWorkerWiring:
    """Test Task 2.2: Real design worker wiring.

    Verifies that AgentService uses AgentDesignWorker (not stub) and
    that stub workers are still used for assessment.
    """

    def test_get_worker_uses_real_design_worker(self):
        """AgentService._get_worker() returns orchestrator with real AgentDesignWorker."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_ops = AsyncMock()
        service = AgentService(operations_service=mock_ops)

        worker = service._get_worker()

        # Design worker should be the real implementation
        assert isinstance(worker.design_worker, AgentDesignWorker)

    def test_get_worker_uses_services_for_training_and_backtest(self):
        """AgentService._get_worker() passes None services (lazy loaded)."""
        from ktrdr.api.services.agent_service import AgentService

        mock_ops = AsyncMock()
        service = AgentService(operations_service=mock_ops)

        worker = service._get_worker()

        # Training and backtest services are lazy-loaded (None at init)
        assert worker._training_service is None
        assert worker._backtest_service is None

    def test_get_worker_uses_real_assessment_worker(self):
        """AgentService._get_worker() uses AgentAssessmentWorker."""
        from ktrdr.agents.workers.assessment_worker import AgentAssessmentWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_ops = AsyncMock()
        service = AgentService(operations_service=mock_ops)

        worker = service._get_worker()

        assert isinstance(worker.assessment_worker, AgentAssessmentWorker)

    def test_design_worker_receives_operations_service(self):
        """AgentDesignWorker is initialized with the operations service."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_ops = AsyncMock()
        service = AgentService(operations_service=mock_ops)

        worker = service._get_worker()

        # Design worker should have the same ops service
        assert isinstance(worker.design_worker, AgentDesignWorker)
        assert worker.design_worker.ops is mock_ops


class TestAgentServiceCancelById:
    """Test cancel(operation_id) method - M4 Task 4.1.

    The cancel method now requires an operation_id parameter to cancel
    a specific research, enabling individual cancellation in multi-research
    scenarios.
    """

    @pytest.mark.asyncio
    async def test_cancel_succeeds_for_running_research(self, mock_operations_service):
        """Cancel succeeds for a running research operation."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create and start a running operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        result = await service.cancel(op.operation_id)

        assert result["success"] is True
        assert result["operation_id"] == op.operation_id
        assert result["message"] == "Research cancelled"

    @pytest.mark.asyncio
    async def test_cancel_succeeds_for_pending_research(self, mock_operations_service):
        """Cancel succeeds for a pending research operation."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a pending operation (not yet started)
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        # Status remains PENDING by default

        result = await service.cancel(op.operation_id)

        assert result["success"] is True
        assert result["operation_id"] == op.operation_id

    @pytest.mark.asyncio
    async def test_cancel_returns_not_found_for_unknown_operation(
        self, mock_operations_service
    ):
        """Cancel returns not_found for unknown operation_id."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        result = await service.cancel("op_nonexistent_12345")

        assert result["success"] is False
        assert result["reason"] == "not_found"
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_cancel_returns_not_research_for_non_research_operation(
        self, mock_operations_service
    ):
        """Cancel returns not_research for non-research operation types."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a training operation (not an AGENT_RESEARCH)
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(parameters={}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        result = await service.cancel(op.operation_id)

        assert result["success"] is False
        assert result["reason"] == "not_research"
        assert "not a research" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_cancel_returns_not_cancellable_for_completed_research(
        self, mock_operations_service
    ):
        """Cancel returns not_cancellable for already completed research."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a completed operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "completed"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.COMPLETED
        )

        result = await service.cancel(op.operation_id)

        assert result["success"] is False
        assert result["reason"] == "not_cancellable"
        assert "completed" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_cancel_returns_not_cancellable_for_failed_research(
        self, mock_operations_service
    ):
        """Cancel returns not_cancellable for already failed research."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a failed operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.FAILED
        )

        result = await service.cancel(op.operation_id)

        assert result["success"] is False
        assert result["reason"] == "not_cancellable"
        assert "failed" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_cancel_returns_child_operation_id(self, mock_operations_service):
        """Cancel returns the child operation ID that was cancelled."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create operation with a child op ID in metadata
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "training_op_id": "op_training_123",
                }
            ),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        result = await service.cancel(op.operation_id)

        assert result["success"] is True
        assert result["child_cancelled"] == "op_training_123"

    @pytest.mark.asyncio
    async def test_cancel_calls_operations_service_cancel(
        self, mock_operations_service
    ):
        """Cancel calls ops.cancel_operation() on the specified operation."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a running operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        await service.cancel(op.operation_id)

        # Check that operation was cancelled
        cancelled_op = await mock_operations_service.get_operation(op.operation_id)
        assert cancelled_op.status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_specific_research_while_others_continue(
        self, mock_operations_service
    ):
        """Cancelling one research doesn't affect other active researches."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create three running operations
        op_a = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op_a.operation_id].status = (
            OperationStatus.RUNNING
        )

        op_b = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        mock_operations_service._operations[op_b.operation_id].status = (
            OperationStatus.RUNNING
        )

        op_c = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "backtesting"}),
        )
        mock_operations_service._operations[op_c.operation_id].status = (
            OperationStatus.RUNNING
        )

        # Cancel only op_b
        result = await service.cancel(op_b.operation_id)

        assert result["success"] is True
        assert result["operation_id"] == op_b.operation_id

        # op_b should be cancelled
        assert (
            mock_operations_service._operations[op_b.operation_id].status
            == OperationStatus.CANCELLED
        )

        # op_a and op_c should still be running
        assert (
            mock_operations_service._operations[op_a.operation_id].status
            == OperationStatus.RUNNING
        )
        assert (
            mock_operations_service._operations[op_c.operation_id].status
            == OperationStatus.RUNNING
        )

    @pytest.mark.asyncio
    async def test_cancel_gets_child_id_for_each_phase(self, mock_operations_service):
        """Cancel correctly maps each phase to its child operation ID."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Test each phase mapping
        phase_to_child = {
            "designing": ("design_op_id", "op_design_1"),
            "training": ("training_op_id", "op_training_2"),
            "backtesting": ("backtest_op_id", "op_backtest_3"),
            "assessing": ("assessment_op_id", "op_assessment_4"),
        }

        for phase, (key, child_id) in phase_to_child.items():
            # Reset operations
            mock_operations_service._operations.clear()

            op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_RESEARCH,
                metadata=OperationMetadata(parameters={"phase": phase, key: child_id}),
            )
            mock_operations_service._operations[op.operation_id].status = (
                OperationStatus.RUNNING
            )

            result = await service.cancel(op.operation_id)

            assert result["child_cancelled"] == child_id, f"Failed for phase {phase}"


class TestAgentServiceBudget:
    """Test budget integration - M7 Task 7.2.

    Tests that:
    - trigger() checks budget before starting cycle
    - 429-style response when budget exhausted
    - Spend is recorded after successful completion
    """

    @pytest.fixture
    def mock_budget_tracker(self):
        """Create a mock budget tracker."""
        from unittest.mock import MagicMock

        tracker = MagicMock()
        tracker.can_spend.return_value = (True, "ok")
        tracker.record_spend = MagicMock()
        tracker.get_remaining.return_value = 5.0
        return tracker

    @pytest.mark.asyncio
    async def test_trigger_checks_budget_before_starting(
        self, mock_operations_service, mock_budget_tracker
    ):
        """Trigger checks budget before starting a cycle."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_budget_tracker,
        ):
            service = AgentService(operations_service=mock_operations_service)
            await service.trigger()

        mock_budget_tracker.can_spend.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_rejected_when_budget_exhausted(
        self, mock_operations_service, mock_budget_tracker
    ):
        """Trigger returns budget_exhausted when budget is exhausted."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        mock_budget_tracker.can_spend.return_value = (
            False,
            "budget_exhausted ($0.10 remaining, need $0.15)",
        )

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_budget_tracker,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger()

        assert result["triggered"] is False
        assert result["reason"] == "budget_exhausted"
        assert "budget" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_trigger_does_not_create_operation_when_budget_exhausted(
        self, mock_operations_service, mock_budget_tracker
    ):
        """No operation is created when budget is exhausted."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        mock_budget_tracker.can_spend.return_value = (False, "budget_exhausted")

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_budget_tracker,
        ):
            service = AgentService(operations_service=mock_operations_service)
            await service.trigger()

        # No operations should have been created
        assert len(mock_operations_service._operations) == 0

    @pytest.mark.asyncio
    async def test_budget_check_before_active_cycle_check(
        self, mock_operations_service, mock_budget_tracker
    ):
        """Budget is checked before checking for active cycle."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        # Set up an active cycle
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        # Budget exhausted
        mock_budget_tracker.can_spend.return_value = (False, "budget_exhausted")

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_budget_tracker,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger()

        # Should return budget_exhausted, not active_cycle_exists
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_service_delegates_spend_recording_to_worker(
        self, mock_operations_service, mock_budget_tracker
    ):
        """AgentService does NOT record spend - worker records per-phase."""
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        # Create a mock worker that returns immediately with token info
        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.return_value = {
            "success": True,
            "total_tokens": 5000,
            "strategy_name": "test_strategy",
        }

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_budget_tracker,
        ):
            service = AgentService(operations_service=mock_operations_service)

            # Manually call _run_coordinator to test spend recording
            await service._run_coordinator(mock_worker)

        # Service should NOT record spend - worker records per-phase
        mock_budget_tracker.record_spend.assert_not_called()

    @pytest.mark.asyncio
    async def test_spend_not_recorded_on_failure(
        self, mock_operations_service, mock_budget_tracker
    ):
        """Spend is NOT recorded when a cycle fails."""
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        # Create a mock worker that raises an exception
        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.side_effect = Exception("Worker failed")

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_budget_tracker,
        ):
            service = AgentService(operations_service=mock_operations_service)

            with pytest.raises(Exception, match="Worker failed"):
                await service._run_coordinator(mock_worker)

        # Spend should NOT have been recorded
        mock_budget_tracker.record_spend.assert_not_called()

    @pytest.mark.asyncio
    async def test_spend_not_recorded_on_cancellation(
        self, mock_operations_service, mock_budget_tracker
    ):
        """Spend is NOT recorded when a cycle is cancelled."""
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        # Create a mock worker that raises CancelledError
        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.side_effect = asyncio.CancelledError()

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_budget_tracker,
        ):
            service = AgentService(operations_service=mock_operations_service)

            with pytest.raises(asyncio.CancelledError):
                await service._run_coordinator(mock_worker)

        # Spend should NOT have been recorded
        mock_budget_tracker.record_spend.assert_not_called()

    def test_cost_estimation_opus_model(self):
        """Cost estimation uses Opus 4.5 pricing when AGENT_MODEL=opus."""
        import os
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker.__new__(AgentResearchWorker)

        # Opus 4.5: $5 input, $25 output per 1M tokens
        # 10k input + 5k output = (10000 * 5 + 5000 * 25) / 1_000_000 = $0.175
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-opus-4-5-20251101"}):
            cost = worker._estimate_cost(input_tokens=10000, output_tokens=5000)
            expected = (10000 * 5 + 5000 * 25) / 1_000_000  # $0.175
            assert abs(cost - expected) < 0.001, f"Expected {expected}, got {cost}"

    def test_cost_estimation_sonnet_model(self):
        """Cost estimation uses Sonnet 4 pricing when AGENT_MODEL=sonnet."""
        import os
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker.__new__(AgentResearchWorker)

        # Sonnet 4: $3 input, $15 output per 1M tokens
        # 10k input + 5k output = (10000 * 3 + 5000 * 15) / 1_000_000 = $0.105
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-sonnet-4-5-20250929"}):
            cost = worker._estimate_cost(input_tokens=10000, output_tokens=5000)
            expected = (10000 * 3 + 5000 * 15) / 1_000_000  # $0.105
            assert abs(cost - expected) < 0.001, f"Expected {expected}, got {cost}"

    def test_cost_estimation_haiku_model(self):
        """Cost estimation uses Haiku 4.5 pricing when AGENT_MODEL=haiku."""
        import os
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker.__new__(AgentResearchWorker)

        # Haiku 4.5: $1 input, $5 output per 1M tokens
        # 10k input + 5k output = (10000 * 1 + 5000 * 5) / 1_000_000 = $0.035
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-haiku-4-5-20251001"}):
            cost = worker._estimate_cost(input_tokens=10000, output_tokens=5000)
            expected = (10000 * 1 + 5000 * 5) / 1_000_000  # $0.035
            assert abs(cost - expected) < 0.001, f"Expected {expected}, got {cost}"

    def test_cost_estimation_default_model(self):
        """Cost estimation defaults to Opus pricing when AGENT_MODEL not set."""
        import os
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker.__new__(AgentResearchWorker)

        # Remove AGENT_MODEL if set, should default to Opus pricing
        env = {k: v for k, v in os.environ.items() if k != "AGENT_MODEL"}
        with patch.dict(os.environ, env, clear=True):
            cost = worker._estimate_cost(input_tokens=10000, output_tokens=5000)
            expected = (10000 * 5 + 5000 * 25) / 1_000_000  # Opus: $0.175
            assert abs(cost - expected) < 0.001, f"Expected {expected}, got {cost}"

    def test_cost_estimation_zero_tokens(self):
        """Cost estimation returns zero for zero tokens."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker.__new__(AgentResearchWorker)
        assert worker._estimate_cost(input_tokens=0, output_tokens=0) == 0.0

    def test_cost_estimation_typical_design_phase(self):
        """Cost estimation is accurate for typical design phase token counts."""
        import os
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker.__new__(AgentResearchWorker)

        # After M8 optimization: ~12k input tokens, ~2k output tokens
        # With Opus: (12000 * 5 + 2000 * 25) / 1_000_000 = $0.11
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-opus-4-5-20251101"}):
            cost = worker._estimate_cost(input_tokens=12000, output_tokens=2000)
            assert (
                0.05 < cost < 0.15
            ), f"Design phase cost should be ~$0.11, got ${cost}"

        # With Haiku: (12000 * 1 + 2000 * 5) / 1_000_000 = $0.022
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-haiku-4-5-20251001"}):
            cost = worker._estimate_cost(input_tokens=12000, output_tokens=2000)
            assert (
                0.01 < cost < 0.05
            ), f"Haiku design cost should be ~$0.02, got ${cost}"


class TestAgentServiceResumeIfNeeded:
    """Test resume_if_needed() method - M1 Task 1.6.

    Tests that:
    - Coordinator starts on backend startup if active researches exist
    - No coordinator started when no active researches
    - No duplicate coordinators created if already running
    """

    @pytest.fixture(autouse=True)
    def use_stub_workers(self, monkeypatch):
        """Use stub workers to avoid real API calls in unit tests."""
        monkeypatch.setenv("USE_STUB_WORKERS", "true")
        monkeypatch.setenv("STUB_WORKER_FAST", "true")

    @pytest.mark.asyncio
    async def test_resume_starts_coordinator_when_active_ops_exist(
        self, mock_operations_service
    ):
        """resume_if_needed() starts coordinator when active ops exist."""
        from ktrdr.api.services.agent_service import AgentService

        # Create an active research operation
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
        assert not service._coordinator_task.done()

    @pytest.mark.asyncio
    async def test_resume_does_nothing_when_no_active_ops(
        self, mock_operations_service
    ):
        """resume_if_needed() does nothing when no active ops exist."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # No active operations
        assert len(mock_operations_service._operations) == 0

        # Call resume_if_needed
        await service.resume_if_needed()

        # Coordinator should NOT be started
        assert service._coordinator_task is None

    @pytest.mark.asyncio
    async def test_resume_does_nothing_when_coordinator_already_running(
        self, mock_operations_service
    ):
        """resume_if_needed() does nothing if coordinator already running."""
        from unittest.mock import MagicMock

        from ktrdr.api.services.agent_service import AgentService

        # Create an active research operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        service = AgentService(operations_service=mock_operations_service)

        # Simulate already-running coordinator
        mock_task = MagicMock()
        mock_task.done.return_value = False
        service._coordinator_task = mock_task

        # Call resume_if_needed
        await service.resume_if_needed()

        # Should not have replaced the existing task
        assert service._coordinator_task is mock_task

    @pytest.mark.asyncio
    async def test_resume_starts_coordinator_when_previous_task_done(
        self, mock_operations_service
    ):
        """resume_if_needed() starts coordinator if previous task completed."""
        from unittest.mock import MagicMock

        from ktrdr.api.services.agent_service import AgentService

        # Create an active research operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        service = AgentService(operations_service=mock_operations_service)

        # Simulate completed coordinator task
        mock_task = MagicMock()
        mock_task.done.return_value = True
        service._coordinator_task = mock_task

        # Call resume_if_needed
        await service.resume_if_needed()

        # Should have started a new coordinator
        assert service._coordinator_task is not mock_task
        assert service._coordinator_task is not None


class TestAgentServiceMultiResearchStatus:
    """Test get_status() for multi-research response (M5 Task 5.1)."""

    @pytest.mark.asyncio
    async def test_status_returns_empty_active_researches_when_idle(
        self, mock_operations_service
    ):
        """Returns empty active_researches list when no active researches."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        status = await service.get_status()

        assert status["status"] == "idle"
        assert status["active_researches"] == []

    @pytest.mark.asyncio
    async def test_status_returns_all_active_researches(self, mock_operations_service):
        """Returns all active researches in active_researches list."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create multiple running operations
        op1 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "training", "strategy_name": "strat_1"}
            ),
        )
        mock_operations_service._operations[op1.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op1.operation_id].started_at = datetime.now(
            timezone.utc
        )

        op2 = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "designing", "strategy_name": "strat_2"}
            ),
        )
        mock_operations_service._operations[op2.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op2.operation_id].started_at = datetime.now(
            timezone.utc
        )

        status = await service.get_status()

        assert status["status"] == "active"
        assert len(status["active_researches"]) == 2

        # Verify each research has expected fields
        op_ids = [r["operation_id"] for r in status["active_researches"]]
        assert op1.operation_id in op_ids
        assert op2.operation_id in op_ids

        for research in status["active_researches"]:
            assert "operation_id" in research
            assert "phase" in research
            assert "strategy_name" in research
            assert "duration_seconds" in research
            assert "child_operation_id" in research

    @pytest.mark.asyncio
    async def test_status_includes_worker_utilization(self, mock_operations_service):
        """Status includes worker utilization by type."""
        from unittest.mock import MagicMock, patch

        from ktrdr.api.models.workers import WorkerStatus, WorkerType
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Mock worker registry
        mock_registry = MagicMock()

        # Create mock workers
        training_worker_1 = MagicMock()
        training_worker_1.status = WorkerStatus.BUSY
        training_worker_2 = MagicMock()
        training_worker_2.status = WorkerStatus.AVAILABLE

        backtest_worker_1 = MagicMock()
        backtest_worker_1.status = WorkerStatus.BUSY

        def mock_list_workers(worker_type=None):
            if worker_type == WorkerType.TRAINING:
                return [training_worker_1, training_worker_2]
            elif worker_type == WorkerType.BACKTESTING:
                return [backtest_worker_1]
            return []

        mock_registry.list_workers = mock_list_workers

        # Patch at the import location (inside _get_worker_status)
        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_registry,
        ):
            status = await service.get_status()

        assert "workers" in status
        assert status["workers"]["training"]["busy"] == 1
        assert status["workers"]["training"]["total"] == 2
        assert status["workers"]["backtesting"]["busy"] == 1
        assert status["workers"]["backtesting"]["total"] == 1

    @pytest.mark.asyncio
    async def test_status_includes_budget_status(self, mock_operations_service):
        """Status includes budget remaining and limit."""
        from unittest.mock import MagicMock, patch

        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Mock budget tracker
        mock_budget = MagicMock()
        mock_budget.get_remaining.return_value = 3.42
        mock_budget.daily_limit = 5.0

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_budget,
        ):
            status = await service.get_status()

        assert "budget" in status
        assert status["budget"]["remaining"] == 3.42
        assert status["budget"]["daily_limit"] == 5.0

    @pytest.mark.asyncio
    async def test_status_includes_capacity_info(self, mock_operations_service):
        """Status includes capacity active count and limit."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create 2 running operations
        for _ in range(2):
            op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_RESEARCH,
                metadata=OperationMetadata(parameters={"phase": "training"}),
            )
            mock_operations_service._operations[op.operation_id].status = (
                OperationStatus.RUNNING
            )
            mock_operations_service._operations[op.operation_id].started_at = (
                datetime.now(timezone.utc)
            )

        status = await service.get_status()

        assert "capacity" in status
        assert status["capacity"]["active"] == 2
        assert "limit" in status["capacity"]
        assert status["capacity"]["limit"] > 0  # Should have a reasonable limit

    @pytest.mark.asyncio
    async def test_status_research_duration_calculation(self, mock_operations_service):
        """Duration is calculated correctly from started_at."""
        from datetime import timedelta

        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a running operation started 2 minutes ago
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op.operation_id].started_at = datetime.now(
            timezone.utc
        ) - timedelta(minutes=2, seconds=30)

        status = await service.get_status()

        assert len(status["active_researches"]) == 1
        research = status["active_researches"][0]
        # Should be around 150 seconds (2m 30s), allow 5s tolerance
        assert 145 <= research["duration_seconds"] <= 155

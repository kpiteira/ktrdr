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
        operation_type, metadata=None, parent_operation_id=None
    ):
        return create_op(operation_type, metadata, parent_operation_id)

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

    async def async_start_operation(operation_id, task):
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
    async def test_trigger_rejects_when_cycle_active(self, mock_operations_service):
        """Trigger returns triggered=False if cycle already active."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # First trigger should succeed
        result1 = await service.trigger()
        assert result1["triggered"] is True

        # Mark the operation as running (simulating started worker)
        op_id = result1["operation_id"]
        mock_operations_service._operations[op_id].status = OperationStatus.RUNNING

        # Second trigger should fail
        result2 = await service.trigger()

        assert result2["triggered"] is False
        assert result2["reason"] == "active_cycle_exists"
        assert result2["operation_id"] == op_id

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

        status = await service.get_status()

        assert status["status"] == "active"
        assert status["operation_id"] == op.operation_id

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

        status = await service.get_status()

        assert status["phase"] == "backtesting"

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

        status = await service.get_status()

        assert status["status"] == "active"
        assert status["strategy_name"] == "momentum_rsi_v2"

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

        status = await service.get_status()

        assert status["status"] == "active"
        assert "child_operation_id" in status
        assert status["child_operation_id"] == "op_training_123"

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

        status = await service.get_status()

        # Should return the backtest child, not design or training
        assert status["child_operation_id"] == "op_backtesting_3"


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


class TestAgentServiceCancel:
    """Test cancel() method - Task 6.1."""

    @pytest.mark.asyncio
    async def test_cancel_returns_success_when_cycle_active(
        self, mock_operations_service
    ):
        """Cancel returns success=True when an active cycle exists."""
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

        result = await service.cancel()

        assert result["success"] is True
        assert result["operation_id"] == op.operation_id
        assert result["message"] == "Research cycle cancelled"

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

        result = await service.cancel()

        assert result["success"] is True
        assert result["child_cancelled"] == "op_training_123"

    @pytest.mark.asyncio
    async def test_cancel_returns_none_child_when_no_child_op(
        self, mock_operations_service
    ):
        """Cancel returns None for child_cancelled when no child op exists."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create operation without child op
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )

        result = await service.cancel()

        assert result["success"] is True
        assert result["child_cancelled"] is None

    @pytest.mark.asyncio
    async def test_cancel_returns_failure_when_no_active_cycle(
        self, mock_operations_service
    ):
        """Cancel returns success=False with reason when no active cycle."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        result = await service.cancel()

        assert result["success"] is False
        assert result["reason"] == "no_active_cycle"
        assert result["message"] == "No active research cycle to cancel"

    @pytest.mark.asyncio
    async def test_cancel_calls_operations_service_cancel(
        self, mock_operations_service
    ):
        """Cancel calls ops.cancel_operation() on the active operation."""
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

        await service.cancel()

        # Check that operation was cancelled
        cancelled_op = await mock_operations_service.get_operation(op.operation_id)
        assert cancelled_op.status == OperationStatus.CANCELLED

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

            result = await service.cancel()

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
    async def test_spend_recorded_after_successful_completion(
        self, mock_operations_service, mock_budget_tracker
    ):
        """Spend is recorded after a cycle completes successfully."""
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

            # Manually call _run_worker to test spend recording
            op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_RESEARCH,
                metadata=OperationMetadata(parameters={"phase": "idle"}),
            )

            await service._run_worker(op.operation_id, mock_worker)

        # Spend should have been recorded
        mock_budget_tracker.record_spend.assert_called_once()
        call_args = mock_budget_tracker.record_spend.call_args
        assert call_args[0][1] == op.operation_id  # operation_id

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

            op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_RESEARCH,
                metadata=OperationMetadata(parameters={"phase": "idle"}),
            )

            with pytest.raises(Exception, match="Worker failed"):
                await service._run_worker(op.operation_id, mock_worker)

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

            op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_RESEARCH,
                metadata=OperationMetadata(parameters={"phase": "idle"}),
            )

            with pytest.raises(asyncio.CancelledError):
                await service._run_worker(op.operation_id, mock_worker)

        # Spend should NOT have been recorded
        mock_budget_tracker.record_spend.assert_not_called()

    @pytest.mark.asyncio
    async def test_cost_estimation_from_tokens(
        self, mock_operations_service, mock_budget_tracker
    ):
        """Cost is estimated from token count."""
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker
        from ktrdr.api.services.agent_service import AgentService

        mock_worker = AsyncMock(spec=AgentResearchWorker)
        mock_worker.run.return_value = {
            "success": True,
            "total_tokens": 10000,  # 10k tokens
        }

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_budget_tracker,
        ):
            service = AgentService(operations_service=mock_operations_service)

            op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_RESEARCH,
                metadata=OperationMetadata(parameters={"phase": "idle"}),
            )

            await service._run_worker(op.operation_id, mock_worker)

        # Check that some cost was recorded (not zero)
        call_args = mock_budget_tracker.record_spend.call_args
        estimated_cost = call_args[0][0]
        assert estimated_cost > 0
        # With 10k tokens at ~$0.039/1k, should be around $0.39
        assert 0.1 < estimated_cost < 1.0

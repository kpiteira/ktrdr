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

"""Tests for multi-research coordinator functionality.

Task 1.1: Tests for _get_all_active_research_ops() method.
"""

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

    def create_op(
        operation_type,
        metadata=None,
        parent_operation_id=None,
        status=OperationStatus.PENDING,
    ):
        """Create operation helper."""
        nonlocal operation_counter
        operation_counter += 1
        op_id = f"op_{operation_type.value}_{operation_counter}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=status,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or OperationMetadata(),
            parent_operation_id=parent_operation_id,
        )
        operations[op_id] = op
        return op

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

    service.list_operations = async_list_operations
    service._operations = operations
    service._create_op = create_op

    return service


class TestGetAllActiveResearchOps:
    """Tests for _get_all_active_research_ops() method - Task 1.1."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_active_researches(
        self, mock_operations_service
    ):
        """Returns empty list when no active researches exist."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        result = await service._get_all_active_research_ops()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_single_operation_when_one_active(
        self, mock_operations_service
    ):
        """Returns list with single operation when one active research exists."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create one running research
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op.operation_id

    @pytest.mark.asyncio
    async def test_returns_multiple_operations_when_several_active(
        self, mock_operations_service
    ):
        """Returns list with all active operations when multiple researches active."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create three running researches
        op1 = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        op2 = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        op3 = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 3
        result_ids = {op.operation_id for op in result}
        assert result_ids == {op1.operation_id, op2.operation_id, op3.operation_id}

    @pytest.mark.asyncio
    async def test_includes_running_status(self, mock_operations_service):
        """Includes operations with RUNNING status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].status == OperationStatus.RUNNING

    @pytest.mark.asyncio
    async def test_includes_resuming_status(self, mock_operations_service):
        """Includes operations with RESUMING status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RESUMING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].status == OperationStatus.RESUMING

    @pytest.mark.asyncio
    async def test_includes_pending_status(self, mock_operations_service):
        """Includes operations with PENDING status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.PENDING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].status == OperationStatus.PENDING

    @pytest.mark.asyncio
    async def test_includes_all_active_statuses(self, mock_operations_service):
        """Includes operations with RUNNING, RESUMING, and PENDING statuses."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create one of each status
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RESUMING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.PENDING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 3
        statuses = {op.status for op in result}
        assert statuses == {
            OperationStatus.RUNNING,
            OperationStatus.RESUMING,
            OperationStatus.PENDING,
        }

    @pytest.mark.asyncio
    async def test_excludes_completed_operations(self, mock_operations_service):
        """Excludes operations with COMPLETED status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create completed operation
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.COMPLETED,
        )
        # Create running operation
        op_active = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op_active.operation_id

    @pytest.mark.asyncio
    async def test_excludes_failed_operations(self, mock_operations_service):
        """Excludes operations with FAILED status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create failed operation
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.FAILED,
        )
        # Create running operation
        op_active = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op_active.operation_id

    @pytest.mark.asyncio
    async def test_excludes_cancelled_operations(self, mock_operations_service):
        """Excludes operations with CANCELLED status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create cancelled operation
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.CANCELLED,
        )
        # Create running operation
        op_active = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op_active.operation_id

    @pytest.mark.asyncio
    async def test_only_returns_agent_research_operations(
        self, mock_operations_service
    ):
        """Only returns AGENT_RESEARCH operations, not other types."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create operations of different types
        mock_operations_service._create_op(
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.BACKTESTING,
            status=OperationStatus.RUNNING,
        )
        op_research = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op_research.operation_id
        assert result[0].operation_type == OperationType.AGENT_RESEARCH


class TestGetActiveResearchOpBackwardCompatibility:
    """Test that existing _get_active_research_op() still works after adding new method."""

    @pytest.mark.asyncio
    async def test_get_active_research_op_still_returns_single_operation(
        self, mock_operations_service
    ):
        """Existing method should still return a single operation."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a running research
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_active_research_op()

        assert result is not None
        assert result.operation_id == op.operation_id

    @pytest.mark.asyncio
    async def test_get_active_research_op_still_returns_none_when_no_active(
        self, mock_operations_service
    ):
        """Existing method should still return None when no active operations."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        result = await service._get_active_research_op()

        assert result is None

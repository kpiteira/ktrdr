"""
Integration tests for Agent Parent-Child Operations (Task 1.15).

Tests the end-to-end flow of parent-child operations in the agent service:
- Parent operation created when session starts
- Child operation linked to parent
- Cancellation cascade
- Session lifecycle
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import OperationsService


@pytest.fixture
def operations_service():
    """Create a fresh OperationsService for each test."""
    return OperationsService()


@pytest.fixture
def mock_trigger_config():
    """Mock TriggerConfig that's enabled."""
    config = MagicMock()
    config.enabled = True
    return config


@pytest.fixture
def mock_db():
    """Mock agent database."""
    db = AsyncMock()
    db.get_active_session.return_value = None  # No active session by default
    return db


class TestAgentParentChildIntegration:
    """Integration tests for agent parent-child operation lifecycle."""

    @pytest.mark.asyncio
    async def test_trigger_creates_parent_and_child_operations(
        self, operations_service, mock_trigger_config, mock_db
    ):
        """Test that trigger creates both parent (AGENT_SESSION) and child (AGENT_DESIGN) operations."""
        # Create agent service with our operations service
        agent_service = AgentService(operations_service=operations_service)
        agent_service._config = mock_trigger_config
        agent_service._db = mock_db

        # Mock the actual agent work (we don't want to call Anthropic)
        with patch.object(
            agent_service, "_run_agent_with_tracking", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = None

            # Trigger a research cycle
            result = await agent_service.trigger()

            # Verify trigger succeeded
            assert result["success"] is True
            assert result["triggered"] is True
            assert "operation_id" in result
            assert "design_operation_id" in result

            session_op_id = result["operation_id"]
            design_op_id = result["design_operation_id"]

            # Verify parent operation exists and is AGENT_SESSION
            parent_op = await operations_service.get_operation(session_op_id)
            assert parent_op is not None
            assert parent_op.operation_type == OperationType.AGENT_SESSION
            assert parent_op.status == OperationStatus.RUNNING

            # Verify child operation exists and is linked to parent
            child_op = await operations_service.get_operation(design_op_id)
            assert child_op is not None
            assert child_op.operation_type == OperationType.AGENT_DESIGN
            assert child_op.parent_operation_id == session_op_id

    @pytest.mark.asyncio
    async def test_get_children_returns_design_operation(
        self, operations_service, mock_trigger_config, mock_db
    ):
        """Test that get_children returns the design operation."""
        agent_service = AgentService(operations_service=operations_service)
        agent_service._config = mock_trigger_config
        agent_service._db = mock_db

        with patch.object(
            agent_service, "_run_agent_with_tracking", new_callable=AsyncMock
        ):
            result = await agent_service.trigger()

            session_op_id = result["operation_id"]
            design_op_id = result["design_operation_id"]

            # Get children of parent
            children = await operations_service.get_children(session_op_id)

            assert len(children) == 1
            assert children[0].operation_id == design_op_id
            assert children[0].operation_type == OperationType.AGENT_DESIGN

    @pytest.mark.asyncio
    async def test_cancel_parent_cancels_child(
        self, operations_service, mock_trigger_config, mock_db
    ):
        """Test that cancelling the parent session also cancels child operations."""
        agent_service = AgentService(operations_service=operations_service)
        agent_service._config = mock_trigger_config
        agent_service._db = mock_db

        with patch.object(
            agent_service, "_run_agent_with_tracking", new_callable=AsyncMock
        ):
            result = await agent_service.trigger()

            session_op_id = result["operation_id"]
            design_op_id = result["design_operation_id"]

            # Cancel the parent session
            cancel_result = await operations_service.cancel_operation(
                session_op_id, reason="User cancelled session"
            )

            assert cancel_result["success"] is True

            # Verify parent is cancelled
            parent_op = await operations_service.get_operation(session_op_id)
            assert parent_op.status == OperationStatus.CANCELLED

            # Verify child is also cancelled (cascade)
            child_op = await operations_service.get_operation(design_op_id)
            assert child_op.status == OperationStatus.CANCELLED
            assert "Parent operation cancelled" in child_op.error_message

    @pytest.mark.asyncio
    async def test_parent_stays_running_after_child_completes(
        self, operations_service, mock_trigger_config, mock_db
    ):
        """Test that parent session stays RUNNING even after design completes (waiting for training)."""
        agent_service = AgentService(operations_service=operations_service)
        agent_service._config = mock_trigger_config
        agent_service._db = mock_db

        with patch.object(
            agent_service, "_run_agent_with_tracking", new_callable=AsyncMock
        ):
            result = await agent_service.trigger()

            session_op_id = result["operation_id"]
            design_op_id = result["design_operation_id"]

            # Complete the design child operation
            await operations_service.complete_operation(
                design_op_id,
                result_summary={"strategy_name": "test_strategy"},
            )

            # Verify child is completed
            child_op = await operations_service.get_operation(design_op_id)
            assert child_op.status == OperationStatus.COMPLETED

            # Verify parent is still RUNNING (waiting for training/backtest)
            parent_op = await operations_service.get_operation(session_op_id)
            assert parent_op.status == OperationStatus.RUNNING

    @pytest.mark.asyncio
    async def test_aggregated_progress_shows_design_phase(
        self, operations_service, mock_trigger_config, mock_db
    ):
        """Test that aggregated progress shows current phase."""
        agent_service = AgentService(operations_service=operations_service)
        agent_service._config = mock_trigger_config
        agent_service._db = mock_db

        with patch.object(
            agent_service, "_run_agent_with_tracking", new_callable=AsyncMock
        ):
            result = await agent_service.trigger()

            session_op_id = result["operation_id"]
            design_op_id = result["design_operation_id"]

            # Update design progress to 50%
            from ktrdr.api.models.operations import OperationProgress

            await operations_service.update_progress(
                design_op_id,
                OperationProgress(
                    percentage=50.0,
                    current_step="Designing strategy",
                ),
            )

            # Get aggregated progress
            progress = await operations_service.get_aggregated_progress(session_op_id)

            # Design at 50% should map to ~2.5% (design range is 0-5%)
            assert progress.percentage == pytest.approx(2.5, abs=0.5)
            assert "Design" in progress.current_step

    @pytest.mark.asyncio
    async def test_can_trigger_after_cancel(
        self, operations_service, mock_trigger_config, mock_db
    ):
        """Test that a new session can be triggered after cancelling the previous one."""
        agent_service = AgentService(operations_service=operations_service)
        agent_service._config = mock_trigger_config
        agent_service._db = mock_db

        with patch.object(
            agent_service, "_run_agent_with_tracking", new_callable=AsyncMock
        ):
            # First trigger
            result1 = await agent_service.trigger()
            session_op_id1 = result1["operation_id"]

            # Cancel first session
            await operations_service.cancel_operation(session_op_id1)

            # Second trigger should work (mock db still returns no active session)
            result2 = await agent_service.trigger()

            assert result2["success"] is True
            assert result2["triggered"] is True
            assert result2["operation_id"] != session_op_id1  # New operation


class TestOperationTypeAgentSession:
    """Additional tests for AGENT_SESSION operation type."""

    @pytest.mark.asyncio
    async def test_agent_session_operation_id_format(self, operations_service):
        """Test that AGENT_SESSION operations have correct ID format."""
        operation = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
        )

        # ID should contain "agent_session"
        assert "agent_session" in operation.operation_id

    @pytest.mark.asyncio
    async def test_list_operations_filters_by_agent_session(self, operations_service):
        """Test that listing operations can filter by AGENT_SESSION type."""
        # Create different operation types
        await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
        )
        await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
        )
        await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
        )

        # Filter by AGENT_SESSION
        ops, total, active = await operations_service.list_operations(
            operation_type=OperationType.AGENT_SESSION
        )

        assert len(ops) == 1
        assert ops[0].operation_type == OperationType.AGENT_SESSION

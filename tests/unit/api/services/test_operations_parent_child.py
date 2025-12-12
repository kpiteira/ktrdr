"""
Unit tests for Parent-Child Operation Lifecycle (Task 1.15).

Tests the parent-child relationship between agent session operations
and their phase operations (design, training, backtest).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import OperationsService


@pytest.fixture
def operations_service():
    """Create an OperationsService instance for testing."""
    return OperationsService()


@pytest.fixture
def agent_session_metadata():
    """Create sample metadata for agent session operation."""
    return OperationMetadata(
        symbol="N/A",
        timeframe="N/A",
        mode="agent_session",
        parameters={"trigger_reason": "start_new_cycle"},
    )


@pytest.fixture
def agent_design_metadata():
    """Create sample metadata for agent design phase operation."""
    return OperationMetadata(
        symbol="N/A",
        timeframe="N/A",
        mode="strategy_design",
        parameters={"session_id": 123},
    )


class TestOperationTypeAgentSession:
    """Test AGENT_SESSION operation type exists and works."""

    def test_agent_session_type_exists(self):
        """Test that AGENT_SESSION is a valid OperationType."""
        # This test will FAIL until we add AGENT_SESSION to OperationType enum
        assert hasattr(OperationType, "AGENT_SESSION")
        assert OperationType.AGENT_SESSION.value == "agent_session"

    @pytest.mark.asyncio
    async def test_create_agent_session_operation(
        self, operations_service, agent_session_metadata
    ):
        """Test creating an AGENT_SESSION type operation."""
        # This test will FAIL until AGENT_SESSION type is added
        operation = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )

        assert operation is not None
        assert operation.operation_id.startswith("op_agent_session_")
        assert operation.operation_type == OperationType.AGENT_SESSION
        assert operation.status == OperationStatus.PENDING


class TestParentOperationIdField:
    """Test parent_operation_id field on OperationInfo model."""

    def test_operation_info_has_parent_field(self):
        """Test that OperationInfo has parent_operation_id field."""
        # This test will FAIL until we add parent_operation_id to OperationInfo
        operation = OperationInfo(
            operation_id="test_op",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
        )

        # Should have parent_operation_id field (default None)
        assert hasattr(operation, "parent_operation_id")
        assert operation.parent_operation_id is None

    def test_operation_info_with_parent_set(self):
        """Test creating OperationInfo with parent_operation_id set."""
        parent_id = "op_agent_session_20251211_123456"

        # This will FAIL until parent_operation_id field is added
        operation = OperationInfo(
            operation_id="test_child_op",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
            parent_operation_id=parent_id,
        )

        assert operation.parent_operation_id == parent_id


class TestCreateChildOperation:
    """Test creating child operations linked to a parent."""

    @pytest.mark.asyncio
    async def test_create_operation_with_parent_id(
        self, operations_service, agent_session_metadata, agent_design_metadata
    ):
        """Test creating a child operation linked to parent."""
        # First create parent
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )

        # Create child with parent_operation_id
        # This will FAIL until create_operation accepts parent_operation_id
        child = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=agent_design_metadata,
            parent_operation_id=parent.operation_id,
        )

        assert child is not None
        assert child.parent_operation_id == parent.operation_id
        assert child.operation_type == OperationType.AGENT_DESIGN


class TestGetChildrenOperations:
    """Test getting child operations for a parent."""

    @pytest.mark.asyncio
    async def test_get_children_returns_child_operations(
        self, operations_service, agent_session_metadata, agent_design_metadata
    ):
        """Test that get_children returns all child operations."""
        # Create parent
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )

        # Create child
        child = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=agent_design_metadata,
            parent_operation_id=parent.operation_id,
        )

        # Get children - this will FAIL until get_children method is added
        children = await operations_service.get_children(parent.operation_id)

        assert len(children) == 1
        assert children[0].operation_id == child.operation_id
        assert children[0].parent_operation_id == parent.operation_id

    @pytest.mark.asyncio
    async def test_get_children_returns_empty_for_no_children(
        self, operations_service, agent_session_metadata
    ):
        """Test get_children returns empty list when no children."""
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )

        children = await operations_service.get_children(parent.operation_id)
        assert children == []

    @pytest.mark.asyncio
    async def test_get_children_returns_multiple_children_in_order(
        self, operations_service, agent_session_metadata
    ):
        """Test get_children returns multiple children in creation order."""
        # Create parent
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )

        # Create multiple children (simulating design → training → backtest)
        child1 = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A", mode="design"),
            parent_operation_id=parent.operation_id,
        )
        child2 = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h", mode="train"),
            parent_operation_id=parent.operation_id,
        )
        child3 = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol="EURUSD", timeframe="1h", mode="backtest"
            ),
            parent_operation_id=parent.operation_id,
        )

        children = await operations_service.get_children(parent.operation_id)

        assert len(children) == 3
        assert children[0].operation_id == child1.operation_id
        assert children[1].operation_id == child2.operation_id
        assert children[2].operation_id == child3.operation_id


class TestCancellationCascade:
    """Test that cancelling parent cascades to children."""

    @pytest.mark.asyncio
    async def test_cancel_parent_cancels_running_children(
        self, operations_service, agent_session_metadata, agent_design_metadata
    ):
        """Test that cancelling parent cancels any running children."""
        # Create parent and start it
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )
        parent_task = MagicMock()
        parent_task.done.return_value = False
        parent_task.cancel = MagicMock()
        await operations_service.start_operation(parent.operation_id, parent_task)

        # Create child and start it
        child = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=agent_design_metadata,
            parent_operation_id=parent.operation_id,
        )
        child_task = MagicMock()
        child_task.done.return_value = False
        child_task.cancel = MagicMock()
        await operations_service.start_operation(child.operation_id, child_task)

        # Cancel parent
        await operations_service.cancel_operation(
            parent.operation_id, reason="User cancelled session"
        )

        # Verify parent cancelled
        parent_op = await operations_service.get_operation(parent.operation_id)
        assert parent_op.status == OperationStatus.CANCELLED

        # Verify child also cancelled (cascade)
        child_op = await operations_service.get_operation(child.operation_id)
        assert child_op.status == OperationStatus.CANCELLED
        child_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_parent_skips_completed_children(
        self, operations_service, agent_session_metadata, agent_design_metadata
    ):
        """Test that completed children are not affected by parent cancellation."""
        # Create parent and start it
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )
        parent_task = MagicMock()
        parent_task.done.return_value = False
        parent_task.cancel = MagicMock()
        await operations_service.start_operation(parent.operation_id, parent_task)

        # Create child, start it, and complete it
        child = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=agent_design_metadata,
            parent_operation_id=parent.operation_id,
        )
        child_task = MagicMock()
        child_task.done.return_value = False
        await operations_service.start_operation(child.operation_id, child_task)
        await operations_service.complete_operation(
            child.operation_id, {"strategy_name": "test_strategy"}
        )

        # Cancel parent
        await operations_service.cancel_operation(
            parent.operation_id, reason="User cancelled"
        )

        # Child should remain COMPLETED (not changed to CANCELLED)
        child_op = await operations_service.get_operation(child.operation_id)
        assert child_op.status == OperationStatus.COMPLETED


class TestPhaseProgressWeights:
    """Test phase-based progress aggregation constants."""

    def test_phase_weights_exist_and_sum_correctly(self):
        """Test that phase weight constants exist and are sensible."""
        # This will FAIL until we define the constants
        from ktrdr.api.services.operations_service import (
            PHASE_WEIGHT_BACKTEST_END,
            PHASE_WEIGHT_BACKTEST_START,
            PHASE_WEIGHT_DESIGN_END,
            PHASE_WEIGHT_DESIGN_START,
            PHASE_WEIGHT_TRAINING_END,
            PHASE_WEIGHT_TRAINING_START,
        )

        # Design: 0-5%
        assert PHASE_WEIGHT_DESIGN_START == 0.0
        assert PHASE_WEIGHT_DESIGN_END == 5.0

        # Training: 5-80%
        assert PHASE_WEIGHT_TRAINING_START == 5.0
        assert PHASE_WEIGHT_TRAINING_END == 80.0

        # Backtest: 80-100%
        assert PHASE_WEIGHT_BACKTEST_START == 80.0
        assert PHASE_WEIGHT_BACKTEST_END == 100.0


class TestParentProgressAggregation:
    """Test progress aggregation from children to parent."""

    @pytest.mark.asyncio
    async def test_get_aggregated_progress_design_phase(
        self, operations_service, agent_session_metadata
    ):
        """Test aggregated progress during design phase."""
        # Create parent
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )
        parent_task = MagicMock()
        parent_task.done.return_value = False
        await operations_service.start_operation(parent.operation_id, parent_task)

        # Create design child at 50% progress
        child = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
            parent_operation_id=parent.operation_id,
        )
        child_task = MagicMock()
        child_task.done.return_value = False
        await operations_service.start_operation(child.operation_id, child_task)
        await operations_service.update_progress(
            child.operation_id,
            OperationProgress(percentage=50.0, current_step="Designing strategy"),
        )

        # Get aggregated progress - will FAIL until method is added
        progress = await operations_service.get_aggregated_progress(parent.operation_id)

        # Design at 50% maps to: 0 + (5-0) * 0.5 = 2.5%
        assert progress.percentage == pytest.approx(2.5, abs=0.1)
        assert "Design" in progress.current_step

    @pytest.mark.asyncio
    async def test_get_aggregated_progress_training_phase(
        self, operations_service, agent_session_metadata
    ):
        """Test aggregated progress during training phase."""
        # Create parent
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )
        parent_task = MagicMock()
        parent_task.done.return_value = False
        await operations_service.start_operation(parent.operation_id, parent_task)

        # Create completed design child
        design_child = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
            parent_operation_id=parent.operation_id,
        )
        await operations_service.complete_operation(
            design_child.operation_id, {"strategy": "test"}
        )

        # Create training child at 40% progress
        train_child = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
            parent_operation_id=parent.operation_id,
        )
        train_task = MagicMock()
        train_task.done.return_value = False
        await operations_service.start_operation(train_child.operation_id, train_task)
        await operations_service.update_progress(
            train_child.operation_id,
            OperationProgress(percentage=40.0, current_step="Epoch 40/100"),
        )

        # Get aggregated progress
        progress = await operations_service.get_aggregated_progress(parent.operation_id)

        # Training at 40% maps to: 5 + (80-5) * 0.4 = 5 + 30 = 35%
        assert progress.percentage == pytest.approx(35.0, abs=0.1)
        assert "Training" in progress.current_step

    @pytest.mark.asyncio
    async def test_get_aggregated_progress_backtest_phase(
        self, operations_service, agent_session_metadata
    ):
        """Test aggregated progress during backtest phase."""
        # Create parent
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )
        parent_task = MagicMock()
        parent_task.done.return_value = False
        await operations_service.start_operation(parent.operation_id, parent_task)

        # Create completed design and training children
        design_child = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
            parent_operation_id=parent.operation_id,
        )
        await operations_service.complete_operation(design_child.operation_id, {})

        train_child = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
            parent_operation_id=parent.operation_id,
        )
        await operations_service.complete_operation(train_child.operation_id, {})

        # Create backtest child at 60% progress
        backtest_child = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
            parent_operation_id=parent.operation_id,
        )
        backtest_task = MagicMock()
        backtest_task.done.return_value = False
        await operations_service.start_operation(
            backtest_child.operation_id, backtest_task
        )
        await operations_service.update_progress(
            backtest_child.operation_id,
            OperationProgress(percentage=60.0, current_step="Running backtest"),
        )

        # Get aggregated progress
        progress = await operations_service.get_aggregated_progress(parent.operation_id)

        # Backtest at 60% maps to: 80 + (100-80) * 0.6 = 80 + 12 = 92%
        assert progress.percentage == pytest.approx(92.0, abs=0.1)
        assert "Backtest" in progress.current_step


class TestParentLifecycle:
    """Test parent operation lifecycle management."""

    @pytest.mark.asyncio
    async def test_parent_stays_running_after_child_completes(
        self, operations_service, agent_session_metadata
    ):
        """Test that parent stays RUNNING after design child completes."""
        # Create and start parent
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )
        parent_task = MagicMock()
        parent_task.done.return_value = False
        await operations_service.start_operation(parent.operation_id, parent_task)

        # Create and complete design child
        child = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
            parent_operation_id=parent.operation_id,
        )
        child_task = MagicMock()
        child_task.done.return_value = False
        await operations_service.start_operation(child.operation_id, child_task)
        await operations_service.complete_operation(child.operation_id, {})

        # Parent should still be RUNNING (waiting for next phase)
        parent_op = await operations_service.get_operation(parent.operation_id)
        assert parent_op.status == OperationStatus.RUNNING

    @pytest.mark.asyncio
    async def test_complete_parent_when_all_children_complete(
        self, operations_service, agent_session_metadata
    ):
        """Test completing parent marks it as completed."""
        # Create parent
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )
        parent_task = MagicMock()
        parent_task.done.return_value = False
        await operations_service.start_operation(parent.operation_id, parent_task)

        # Create all three phase children and complete them
        design = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
            parent_operation_id=parent.operation_id,
        )
        await operations_service.complete_operation(design.operation_id, {})

        training = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
            parent_operation_id=parent.operation_id,
        )
        await operations_service.complete_operation(training.operation_id, {})

        backtest = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
            parent_operation_id=parent.operation_id,
        )
        await operations_service.complete_operation(backtest.operation_id, {})

        # Complete parent (caller does this when session is done)
        await operations_service.complete_operation(
            parent.operation_id, {"final_status": "success"}
        )

        # Parent should be COMPLETED
        parent_op = await operations_service.get_operation(parent.operation_id)
        assert parent_op.status == OperationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_fail_parent_when_child_fails(
        self, operations_service, agent_session_metadata
    ):
        """Test that failing a child can optionally fail the parent."""
        # Create parent
        parent = await operations_service.create_operation(
            operation_type=OperationType.AGENT_SESSION,
            metadata=agent_session_metadata,
        )
        parent_task = MagicMock()
        parent_task.done.return_value = False
        await operations_service.start_operation(parent.operation_id, parent_task)

        # Create and fail design child
        child = await operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
            parent_operation_id=parent.operation_id,
        )
        child_task = MagicMock()
        child_task.done.return_value = False
        await operations_service.start_operation(child.operation_id, child_task)

        # Fail child and cascade to parent - will FAIL until fail_with_cascade is added
        await operations_service.fail_operation(
            child.operation_id, "Design failed", fail_parent=True
        )

        # Parent should be FAILED
        parent_op = await operations_service.get_operation(parent.operation_id)
        assert parent_op.status == OperationStatus.FAILED
        assert "Design failed" in parent_op.error_message

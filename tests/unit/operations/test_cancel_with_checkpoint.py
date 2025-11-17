"""
Unit tests for cancel_operation with checkpoint creation.

Tests verify:
- Checkpoint created before operation cancellation when policy enabled
- No checkpoint created when policy disabled
- Checkpoint metadata includes cancellation reason
- Checkpoint creation doesn't block cancellation on failure
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import OperationInfo, OperationStatus, OperationType, OperationProgress
from ktrdr.checkpoint.types import CheckpointType
from ktrdr.checkpoint.policy import CheckpointPolicy


class TestCancelOperationWithCheckpoint:
    """Test cancel_operation with checkpoint creation."""

    @pytest.fixture
    def operations_service(self):
        """Create OperationsService instance for testing."""
        return OperationsService()

    @pytest.fixture
    def sample_operation(self):
        """Create sample operation for testing."""
        return OperationInfo(
            operation_id="op_test_001",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            progress=OperationProgress(
                percentage=50.0,
                current_step="Training epoch 5/10",
                steps_completed=5,
                steps_total=10
            ),
            description="Test training operation",
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def policy_enabled(self):
        """Policy with checkpoint_on_cancellation enabled."""
        return CheckpointPolicy(
            checkpoint_interval_seconds=300,
            force_checkpoint_every_n=50,
            delete_on_completion=True,
            checkpoint_on_failure=True,
            checkpoint_on_cancellation=True,
        )

    @pytest.fixture
    def policy_disabled(self):
        """Policy with checkpoint_on_cancellation disabled."""
        return CheckpointPolicy(
            checkpoint_interval_seconds=300,
            force_checkpoint_every_n=50,
            delete_on_completion=True,
            checkpoint_on_failure=True,
            checkpoint_on_cancellation=False,
        )

    @pytest.mark.asyncio
    async def test_cancel_creates_checkpoint_when_enabled(self, operations_service, sample_operation, policy_enabled):
        """Test that checkpoint is created when checkpoint_on_cancellation is enabled."""
        # Add operation to service
        operations_service._operations[sample_operation.operation_id] = sample_operation

        with patch.object(operations_service, 'create_checkpoint', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = True
            with patch('ktrdr.checkpoint.policy.load_checkpoint_policies', return_value={"training": policy_enabled}):
                result = await operations_service.cancel_operation(
                    sample_operation.operation_id,
                    reason="User requested cancellation"
                )

        # Verify checkpoint was created
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[1]["operation_id"] == sample_operation.operation_id
        assert call_args[1]["checkpoint_type"] == CheckpointType.CANCELLATION
        assert "cancellation_reason" in call_args[1]["metadata"]
        assert call_args[1]["metadata"]["cancellation_reason"] == "User requested cancellation"

        # Verify operation was cancelled
        assert result["success"] is True
        assert operations_service._operations[sample_operation.operation_id].status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_skips_checkpoint_when_disabled(self, operations_service, sample_operation, policy_disabled):
        """Test that no checkpoint is created when checkpoint_on_cancellation is disabled."""
        # Add operation to service
        operations_service._operations[sample_operation.operation_id] = sample_operation

        with patch.object(operations_service, 'create_checkpoint', new_callable=AsyncMock) as mock_create:
            with patch('ktrdr.checkpoint.policy.load_checkpoint_policies', return_value={"training": policy_disabled}):
                result = await operations_service.cancel_operation(
                    sample_operation.operation_id,
                    reason="User requested cancellation"
                )

        # Verify checkpoint was NOT created
        mock_create.assert_not_called()

        # Verify operation was still cancelled
        assert result["success"] is True
        assert operations_service._operations[sample_operation.operation_id].status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_continues_if_checkpoint_fails(self, operations_service, sample_operation, policy_enabled):
        """Test that cancellation continues even if checkpoint creation fails."""
        # Add operation to service
        operations_service._operations[sample_operation.operation_id] = sample_operation

        with patch.object(operations_service, 'create_checkpoint', new_callable=AsyncMock) as mock_create:
            # Simulate checkpoint failure
            mock_create.return_value = False
            with patch('ktrdr.checkpoint.policy.load_checkpoint_policies', return_value={"training": policy_enabled}):
                result = await operations_service.cancel_operation(
                    sample_operation.operation_id,
                    reason="User requested cancellation"
                )

        # Verify checkpoint was attempted
        mock_create.assert_called_once()

        # Verify operation was still cancelled despite checkpoint failure
        assert result["success"] is True
        assert operations_service._operations[sample_operation.operation_id].status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_includes_cancellation_metadata(self, operations_service, sample_operation, policy_enabled):
        """Test that cancellation checkpoint includes proper metadata."""
        operations_service._operations[sample_operation.operation_id] = sample_operation

        with patch.object(operations_service, 'create_checkpoint', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = True
            with patch('ktrdr.checkpoint.policy.load_checkpoint_policies', return_value={"training": policy_enabled}):
                await operations_service.cancel_operation(
                    sample_operation.operation_id,
                    reason="Training timeout exceeded"
                )

        # Verify metadata
        call_args = mock_create.call_args
        metadata = call_args[1]["metadata"]
        assert metadata["cancellation_reason"] == "Training timeout exceeded"
        assert "checkpoint_at_cancellation" in metadata

    @pytest.mark.asyncio
    async def test_cancel_no_checkpoint_for_completed_operation(self, operations_service, sample_operation, policy_enabled):
        """Test that no checkpoint is created for already completed operations."""
        # Set operation as completed
        sample_operation.status = OperationStatus.COMPLETED
        operations_service._operations[sample_operation.operation_id] = sample_operation

        with patch.object(operations_service, 'create_checkpoint', new_callable=AsyncMock) as mock_create:
            with patch('ktrdr.checkpoint.policy.load_checkpoint_policies', return_value={"training": policy_enabled}):
                result = await operations_service.cancel_operation(
                    sample_operation.operation_id,
                    reason="User requested cancellation"
                )

        # Verify checkpoint was NOT created (operation already finished)
        mock_create.assert_not_called()

        # Verify cancellation failed
        assert result["success"] is False
        assert "already finished" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_cancel_handles_missing_policy_gracefully(self, operations_service, sample_operation):
        """Test that cancellation works even if policy loading fails."""
        operations_service._operations[sample_operation.operation_id] = sample_operation

        with patch.object(operations_service, 'create_checkpoint', new_callable=AsyncMock) as mock_create:
            # Simulate policy loading failure
            with patch('ktrdr.checkpoint.policy.load_checkpoint_policies', side_effect=Exception("Config error")):
                result = await operations_service.cancel_operation(
                    sample_operation.operation_id,
                    reason="User requested cancellation"
                )

        # Should not create checkpoint due to policy loading error, but should still cancel
        mock_create.assert_not_called()

        # Operation should still be cancelled
        assert result["success"] is True
        assert operations_service._operations[sample_operation.operation_id].status == OperationStatus.CANCELLED

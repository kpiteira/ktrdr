"""
Unit tests for OperationsService.create_checkpoint() method.

Tests verify:
- Checkpoint creation with different checkpoint types
- State retrieval from workers/services
- Error handling when state unavailable
- Integration with CheckpointService
- Logging of checkpoint events
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.services.operations_service import OperationsService
from ktrdr.checkpoint.types import CheckpointType


class TestCreateCheckpoint:
    """Test OperationsService.create_checkpoint() method."""

    @pytest.fixture
    def operations_service(self):
        """Create OperationsService instance for testing."""
        return OperationsService()

    @pytest.fixture
    def mock_checkpoint_service(self):
        """Mock CheckpointService."""
        mock_service = MagicMock()
        mock_service.save_checkpoint = AsyncMock(return_value="checkpoint_123")
        return mock_service

    @pytest.mark.asyncio
    async def test_create_checkpoint_timer_type(
        self, operations_service, mock_checkpoint_service
    ):
        """Test creating TIMER checkpoint."""
        operation_id = "op_test_001"
        current_state = {"epoch": 10, "loss": 0.5}

        with patch.object(
            operations_service,
            "_get_checkpoint_service",
            return_value=mock_checkpoint_service,
        ):
            with patch.object(
                operations_service,
                "_get_operation_state",
                new_callable=AsyncMock,
                return_value=current_state,
            ):
                result = await operations_service.create_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type=CheckpointType.TIMER,
                    metadata={"interval": 300},
                )

        assert result is True
        mock_checkpoint_service.save_checkpoint.assert_called_once()
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["operation_id"] == operation_id
        assert call_args[1]["checkpoint_type"] == "TIMER"
        assert call_args[1]["state"] == current_state
        assert call_args[1]["metadata"]["interval"] == 300

    @pytest.mark.asyncio
    async def test_create_checkpoint_cancellation_type(
        self, operations_service, mock_checkpoint_service
    ):
        """Test creating CANCELLATION checkpoint."""
        operation_id = "op_test_002"
        current_state = {"epoch": 25, "loss": 0.3}

        with patch.object(
            operations_service,
            "_get_checkpoint_service",
            return_value=mock_checkpoint_service,
        ):
            with patch.object(
                operations_service,
                "_get_operation_state",
                new_callable=AsyncMock,
                return_value=current_state,
            ):
                result = await operations_service.create_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type=CheckpointType.CANCELLATION,
                    metadata={"cancellation_reason": "user_cancelled"},
                )

        assert result is True
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["checkpoint_type"] == "CANCELLATION"
        assert call_args[1]["metadata"]["cancellation_reason"] == "user_cancelled"

    @pytest.mark.asyncio
    async def test_create_checkpoint_shutdown_type(
        self, operations_service, mock_checkpoint_service
    ):
        """Test creating SHUTDOWN checkpoint."""
        operation_id = "op_test_003"
        current_state = {"bar_index": 5000, "position": "LONG"}

        with patch.object(
            operations_service,
            "_get_checkpoint_service",
            return_value=mock_checkpoint_service,
        ):
            with patch.object(
                operations_service,
                "_get_operation_state",
                new_callable=AsyncMock,
                return_value=current_state,
            ):
                result = await operations_service.create_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type=CheckpointType.SHUTDOWN,
                    metadata={"shutdown_signal": 15},  # SIGTERM
                )

        assert result is True
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args[1]["checkpoint_type"] == "SHUTDOWN"
        assert call_args[1]["metadata"]["shutdown_signal"] == 15

    @pytest.mark.asyncio
    async def test_create_checkpoint_no_state_available(
        self, operations_service, mock_checkpoint_service
    ):
        """Test checkpoint creation fails gracefully when no state available."""
        operation_id = "op_test_004"

        with patch.object(
            operations_service,
            "_get_checkpoint_service",
            return_value=mock_checkpoint_service,
        ):
            with patch.object(
                operations_service,
                "_get_operation_state",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await operations_service.create_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type=CheckpointType.CANCELLATION,
                    metadata={},
                )

        assert result is False
        mock_checkpoint_service.save_checkpoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_checkpoint_service_error(
        self, operations_service, mock_checkpoint_service
    ):
        """Test checkpoint creation handles CheckpointService errors gracefully."""
        operation_id = "op_test_005"
        current_state = {"epoch": 15}

        # Make save_checkpoint raise exception
        mock_checkpoint_service.save_checkpoint.side_effect = Exception("Disk full")

        with patch.object(
            operations_service,
            "_get_checkpoint_service",
            return_value=mock_checkpoint_service,
        ):
            with patch.object(
                operations_service,
                "_get_operation_state",
                new_callable=AsyncMock,
                return_value=current_state,
            ):
                result = await operations_service.create_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type=CheckpointType.TIMER,
                    metadata={},
                )

        # Should return False but not crash
        assert result is False

    @pytest.mark.asyncio
    async def test_create_checkpoint_with_empty_metadata(
        self, operations_service, mock_checkpoint_service
    ):
        """Test checkpoint creation with None metadata adds default fields."""
        operation_id = "op_test_006"
        current_state = {"epoch": 5}

        with patch.object(
            operations_service,
            "_get_checkpoint_service",
            return_value=mock_checkpoint_service,
        ):
            with patch.object(
                operations_service,
                "_get_operation_state",
                new_callable=AsyncMock,
                return_value=current_state,
            ):
                result = await operations_service.create_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type=CheckpointType.FORCE,
                    metadata=None,  # None should be handled
                )

        assert result is True
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        # Should have default fields even when None metadata provided
        assert "checkpoint_type" in call_args[1]["metadata"]
        assert "created_at" in call_args[1]["metadata"]
        assert call_args[1]["metadata"]["checkpoint_type"] == "FORCE"

    @pytest.mark.asyncio
    async def test_create_checkpoint_logs_success(
        self, operations_service, mock_checkpoint_service
    ):
        """Test checkpoint creation logs success message."""
        operation_id = "op_test_007"
        current_state = {"epoch": 20}

        with patch.object(
            operations_service,
            "_get_checkpoint_service",
            return_value=mock_checkpoint_service,
        ):
            with patch.object(
                operations_service,
                "_get_operation_state",
                new_callable=AsyncMock,
                return_value=current_state,
            ):
                with patch(
                    "ktrdr.api.services.operations_service.logger"
                ) as mock_logger:
                    result = await operations_service.create_checkpoint(
                        operation_id=operation_id,
                        checkpoint_type=CheckpointType.CANCELLATION,
                        metadata={},
                    )

        assert result is True
        # Should log success
        mock_logger.info.assert_called()
        log_call = mock_logger.info.call_args[0][0]
        assert "CANCELLATION" in log_call
        assert operation_id in log_call

    @pytest.mark.asyncio
    async def test_create_checkpoint_logs_failure(
        self, operations_service, mock_checkpoint_service
    ):
        """Test checkpoint creation logs failure when state unavailable."""
        operation_id = "op_test_008"

        with patch.object(
            operations_service,
            "_get_checkpoint_service",
            return_value=mock_checkpoint_service,
        ):
            with patch.object(
                operations_service,
                "_get_operation_state",
                new_callable=AsyncMock,
                return_value=None,
            ):
                with patch(
                    "ktrdr.api.services.operations_service.logger"
                ) as mock_logger:
                    result = await operations_service.create_checkpoint(
                        operation_id=operation_id,
                        checkpoint_type=CheckpointType.TIMER,
                        metadata={},
                    )

        assert result is False
        # Should log warning
        mock_logger.warning.assert_called()
        log_call = mock_logger.warning.call_args[0][0]
        assert operation_id in log_call
        assert "no state available" in log_call.lower()

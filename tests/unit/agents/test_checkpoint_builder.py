"""Unit tests for agent checkpoint builder."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestBuildAgentCheckpointState:
    """Tests for build_agent_checkpoint_state function."""

    @pytest.fixture
    def mock_operation(self):
        """Create a mock operation with typical agent state."""
        op = MagicMock()
        op.operation_id = "op_agent_research_123"
        op.metadata = MagicMock()
        op.metadata.parameters = {
            "phase": "training",
            "strategy_name": "momentum_v1",
            "strategy_path": "/strategies/momentum_v1.yaml",
            "training_op_id": "op_training_456",
            "trigger_reason": "start_new_cycle",
        }
        return op

    @pytest.fixture
    def mock_checkpoint_service(self):
        """Create a mock checkpoint service."""
        service = MagicMock()
        # Mock load_checkpoint to return a checkpoint with epoch info
        service.load_checkpoint.return_value = MagicMock(state={"epoch": 25})
        return service

    def test_extracts_phase(self, mock_operation):
        """Should extract current phase from operation metadata."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        state = build_agent_checkpoint_state(mock_operation)

        assert state.phase == "training"

    def test_extracts_strategy_info(self, mock_operation):
        """Should extract strategy name and path."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        state = build_agent_checkpoint_state(mock_operation)

        assert state.strategy_name == "momentum_v1"
        assert state.strategy_path == "/strategies/momentum_v1.yaml"

    def test_extracts_training_operation_id(self, mock_operation):
        """Should extract training operation ID if in training phase."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        state = build_agent_checkpoint_state(mock_operation)

        assert state.training_operation_id == "op_training_456"

    def test_extracts_backtest_operation_id(self, mock_operation):
        """Should extract backtest operation ID if in backtesting phase."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        mock_operation.metadata.parameters["phase"] = "backtesting"
        mock_operation.metadata.parameters["backtest_op_id"] = "op_backtest_789"

        state = build_agent_checkpoint_state(mock_operation)

        assert state.backtest_operation_id == "op_backtest_789"

    def test_extracts_original_request(self, mock_operation):
        """Should include trigger reason in original request."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        state = build_agent_checkpoint_state(mock_operation)

        assert state.original_request["trigger_reason"] == "start_new_cycle"

    def test_handles_idle_phase(self, mock_operation):
        """Should handle idle phase (no strategy yet)."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        mock_operation.metadata.parameters = {
            "phase": "idle",
            "trigger_reason": "start_new_cycle",
        }

        state = build_agent_checkpoint_state(mock_operation)

        assert state.phase == "idle"
        assert state.strategy_name is None
        assert state.strategy_path is None

    def test_handles_designing_phase(self, mock_operation):
        """Should handle designing phase (strategy in progress)."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        mock_operation.metadata.parameters = {
            "phase": "designing",
            "design_op_id": "op_design_001",
            "trigger_reason": "start_new_cycle",
        }

        state = build_agent_checkpoint_state(mock_operation)

        assert state.phase == "designing"
        assert state.training_operation_id is None

    def test_handles_assessing_phase(self, mock_operation):
        """Should handle assessing phase (after backtest)."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        mock_operation.metadata.parameters = {
            "phase": "assessing",
            "strategy_name": "trend_follower",
            "strategy_path": "/strategies/trend_follower.yaml",
            "training_op_id": "op_train_done",
            "backtest_op_id": "op_backtest_done",
            "assessment_op_id": "op_assess_001",
            "trigger_reason": "continue_cycle",
        }

        state = build_agent_checkpoint_state(mock_operation)

        assert state.phase == "assessing"
        assert state.strategy_name == "trend_follower"
        assert state.training_operation_id == "op_train_done"
        assert state.backtest_operation_id == "op_backtest_done"

    def test_returns_correct_operation_type(self, mock_operation):
        """Should always set operation_type to 'agent'."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        state = build_agent_checkpoint_state(mock_operation)

        assert state.operation_type == "agent"

    def test_state_is_json_serializable(self, mock_operation):
        """State should convert to dict for JSON storage."""
        import json

        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        state = build_agent_checkpoint_state(mock_operation)
        state_dict = state.to_dict()

        # Should be JSON serializable without error
        json_str = json.dumps(state_dict)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_includes_token_counts_if_available(self, mock_operation):
        """Should include token counts if tracked in operation."""
        from ktrdr.agents.checkpoint_builder import build_agent_checkpoint_state

        mock_operation.metadata.parameters["token_counts"] = {
            "input_tokens": 15000,
            "output_tokens": 5000,
        }

        state = build_agent_checkpoint_state(mock_operation)

        assert state.token_counts["input_tokens"] == 15000
        assert state.token_counts["output_tokens"] == 5000


@pytest.mark.asyncio
class TestBuildAgentCheckpointStateWithTrainingCheckpoint:
    """Tests for extracting training checkpoint epoch."""

    @pytest.fixture
    def mock_operation_in_training(self):
        """Create a mock operation in training phase."""
        op = MagicMock()
        op.operation_id = "op_agent_research_123"
        op.metadata = MagicMock()
        op.metadata.parameters = {
            "phase": "training",
            "strategy_name": "momentum_v1",
            "strategy_path": "/strategies/momentum_v1.yaml",
            "training_op_id": "op_training_456",
            "trigger_reason": "start_new_cycle",
        }
        return op

    @pytest.fixture
    def mock_checkpoint_service(self):
        """Create a mock checkpoint service with AsyncMock."""
        service = MagicMock()
        service.load_checkpoint = AsyncMock()
        return service

    async def test_extracts_training_checkpoint_epoch(
        self, mock_operation_in_training, mock_checkpoint_service
    ):
        """Should extract training checkpoint epoch if available."""
        from ktrdr.agents.checkpoint_builder import (
            build_agent_checkpoint_state_with_training,
        )

        # Mock checkpoint service to return epoch 25
        mock_checkpoint_service.load_checkpoint.return_value = MagicMock(
            state={"epoch": 25}
        )

        state = await build_agent_checkpoint_state_with_training(
            mock_operation_in_training,
            mock_checkpoint_service,
        )

        assert state.training_checkpoint_epoch == 25

    async def test_handles_no_training_checkpoint(
        self, mock_operation_in_training, mock_checkpoint_service
    ):
        """Should handle case where training has no checkpoint yet."""
        from ktrdr.agents.checkpoint_builder import (
            build_agent_checkpoint_state_with_training,
        )

        # Mock checkpoint service to return None
        mock_checkpoint_service.load_checkpoint.return_value = None

        state = await build_agent_checkpoint_state_with_training(
            mock_operation_in_training,
            mock_checkpoint_service,
        )

        assert state.training_checkpoint_epoch is None

    async def test_handles_non_training_phase(
        self, mock_operation_in_training, mock_checkpoint_service
    ):
        """Should not lookup checkpoint if not in training phase."""
        from ktrdr.agents.checkpoint_builder import (
            build_agent_checkpoint_state_with_training,
        )

        mock_operation_in_training.metadata.parameters["phase"] = "designing"

        state = await build_agent_checkpoint_state_with_training(
            mock_operation_in_training,
            mock_checkpoint_service,
        )

        # Should not have called checkpoint service for non-training phase
        mock_checkpoint_service.load_checkpoint.assert_not_called()
        assert state.training_checkpoint_epoch is None

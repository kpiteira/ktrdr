"""
Unit tests for TriggerService full state machine (Task 2.5).

Tests cover:
- State transitions through all phases
- Training gate evaluation
- Backtest gate evaluation
- Operation status checking
- Outcome recording
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_agents.database.schema import (
    AgentSession,
    SessionOutcome,
    SessionPhase,
)
from research_agents.services.trigger import TriggerConfig, TriggerService


class TestTriggerServiceStateMachine:
    """Tests for TriggerService full state machine."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def mock_invoker(self):
        """Create a mock modern invoker with run() method."""
        invoker = MagicMock()
        invoker.run = AsyncMock()
        return invoker

    @pytest.fixture
    def mock_context_provider(self):
        """Create a mock context provider."""
        provider = MagicMock()
        provider.get_available_indicators = AsyncMock(return_value=[])
        provider.get_available_symbols = AsyncMock(return_value=[])
        return provider

    @pytest.fixture
    def mock_tool_executor(self):
        """Create a mock tool executor."""
        return AsyncMock()

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return TriggerConfig(interval_seconds=1, enabled=True)

    @pytest.fixture
    def service(
        self, config, mock_db, mock_invoker, mock_context_provider, mock_tool_executor
    ):
        """Create a TriggerService instance."""
        return TriggerService(
            config=config,
            db=mock_db,
            invoker=mock_invoker,
            context_provider=mock_context_provider,
            tool_executor=mock_tool_executor,
        )

    # =========================================================================
    # DESIGNED → TRAINING transition tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_designed_session_starts_training(
        self, service, mock_db, mock_tool_executor
    ):
        """Test that a DESIGNED session triggers training start."""
        # Session is in DESIGNED phase, waiting for training
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.DESIGNED,
            created_at=MagicMock(),
            strategy_name="test_strategy",
        )
        mock_db.get_active_session.return_value = mock_session

        # Mock start_training_via_api at the import location
        with patch(
            "ktrdr.agents.executor.start_training_via_api",
            new_callable=AsyncMock,
        ) as mock_training:
            mock_training.return_value = {
                "success": True,
                "operation_id": "op_training_123",
            }

            result = await service.check_and_trigger()

        # Should not trigger new design (active session exists)
        assert result["triggered"] is False
        # Should be handled as active session
        assert result.get("reason") == "handled_designed_session"
        # Session should be updated to TRAINING phase
        mock_db.update_session.assert_called()
        # Should have the operation_id set
        update_calls = mock_db.update_session.call_args_list
        training_update = [
            c for c in update_calls if c.kwargs.get("phase") == SessionPhase.TRAINING
        ]
        assert len(training_update) >= 1

    @pytest.mark.asyncio
    async def test_designed_session_training_start_failure(
        self, service, mock_db, mock_tool_executor
    ):
        """Test handling when training fails to start."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.DESIGNED,
            created_at=MagicMock(),
            strategy_name="test_strategy",
        )
        mock_db.get_active_session.return_value = mock_session

        # Mock start_training_via_api to return failure
        with patch(
            "ktrdr.agents.executor.start_training_via_api",
            new_callable=AsyncMock,
        ) as mock_training:
            mock_training.return_value = {
                "success": False,
                "error": "Training service unavailable",
            }

            await service.check_and_trigger()

        # Session should be marked as failed
        mock_db.complete_session.assert_called()
        complete_call = mock_db.complete_session.call_args
        assert complete_call.kwargs.get("outcome") == SessionOutcome.FAILED_TRAINING

    # =========================================================================
    # TRAINING → gate → BACKTESTING transition tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_training_completed_gate_passes(
        self, service, mock_db, mock_tool_executor
    ):
        """Test that completed training with passing gate starts backtest."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.TRAINING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
            operation_id="op_training_123",
        )
        mock_db.get_active_session.return_value = mock_session

        # Mock operation status - completed with good results
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_ops:
            mock_ops = MagicMock()
            mock_ops.get_operation = AsyncMock(
                return_value=MagicMock(
                    status="COMPLETED",
                    result_summary={
                        "accuracy": 0.65,
                        "final_loss": 0.3,
                        "initial_loss": 1.0,
                        "model_path": "/models/test.pt",
                    },
                )
            )
            mock_get_ops.return_value = mock_ops

            # Mock backtest start
            with patch(
                "ktrdr.agents.executor.start_backtest_via_api",
                new_callable=AsyncMock,
            ) as mock_backtest:
                mock_backtest.return_value = {
                    "success": True,
                    "operation_id": "op_backtest_456",
                }

                await service.check_and_trigger()

        # Session should transition to BACKTESTING
        update_calls = mock_db.update_session.call_args_list
        backtest_update = [
            c for c in update_calls if c.kwargs.get("phase") == SessionPhase.BACKTESTING
        ]
        assert len(backtest_update) >= 1

    @pytest.mark.asyncio
    async def test_training_completed_gate_fails_accuracy(
        self, service, mock_db, mock_tool_executor
    ):
        """Test that completed training with failing accuracy gate ends session."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.TRAINING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
            operation_id="op_training_123",
        )
        mock_db.get_active_session.return_value = mock_session

        # Mock operation status - completed with bad accuracy
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_ops:
            mock_ops = MagicMock()
            mock_ops.get_operation = AsyncMock(
                return_value=MagicMock(
                    status="COMPLETED",
                    result_summary={
                        "accuracy": 0.30,  # Below 0.45 threshold
                        "final_loss": 0.3,
                        "initial_loss": 1.0,
                    },
                )
            )
            mock_get_ops.return_value = mock_ops

            await service.check_and_trigger()

        # Session should be completed with FAILED_TRAINING_GATE
        mock_db.complete_session.assert_called()
        complete_call = mock_db.complete_session.call_args
        assert (
            complete_call.kwargs.get("outcome") == SessionOutcome.FAILED_TRAINING_GATE
        )

    @pytest.mark.asyncio
    async def test_training_operation_still_running(
        self, service, mock_db, mock_tool_executor
    ):
        """Test that running training operation is left alone."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.TRAINING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
            operation_id="op_training_123",
        )
        mock_db.get_active_session.return_value = mock_session

        # Mock operation status - still running
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_ops:
            mock_ops = MagicMock()
            mock_ops.get_operation = AsyncMock(return_value=MagicMock(status="RUNNING"))
            mock_get_ops.return_value = mock_ops

            result = await service.check_and_trigger()

        # Should not transition - operation still running
        assert result.get("reason") == "operation_in_progress"
        mock_db.complete_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_training_operation_failed(
        self, service, mock_db, mock_tool_executor
    ):
        """Test that failed training operation ends session."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.TRAINING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
            operation_id="op_training_123",
        )
        mock_db.get_active_session.return_value = mock_session

        # Mock operation status - failed
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_ops:
            mock_ops = MagicMock()
            mock_ops.get_operation = AsyncMock(
                return_value=MagicMock(status="FAILED", error_message="GPU OOM")
            )
            mock_get_ops.return_value = mock_ops

            await service.check_and_trigger()

        # Session should be completed with FAILED_TRAINING
        mock_db.complete_session.assert_called()
        complete_call = mock_db.complete_session.call_args
        assert complete_call.kwargs.get("outcome") == SessionOutcome.FAILED_TRAINING

    # =========================================================================
    # BACKTESTING → gate → ASSESSING transition tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_backtest_completed_gate_passes(self, service, mock_db, mock_invoker):
        """Test that completed backtest with passing gate invokes assessment."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.BACKTESTING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
            operation_id="op_backtest_456",
        )
        mock_db.get_active_session.return_value = mock_session
        mock_db.get_recent_completed_sessions.return_value = []

        # Mock operation status - completed with good results
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_ops:
            mock_ops = MagicMock()
            mock_ops.get_operation = AsyncMock(
                return_value=MagicMock(
                    status="COMPLETED",
                    result_summary={
                        "win_rate": 0.55,
                        "max_drawdown": 0.25,
                        "sharpe_ratio": 1.2,
                    },
                )
            )
            mock_get_ops.return_value = mock_ops

            # Agent invocation succeeds
            mock_invoker.run.return_value = MagicMock(
                success=True, input_tokens=100, output_tokens=200
            )

            await service.check_and_trigger()

        # Session should transition to ASSESSING
        update_calls = mock_db.update_session.call_args_list
        assessing_update = [
            c for c in update_calls if c.kwargs.get("phase") == SessionPhase.ASSESSING
        ]
        assert len(assessing_update) >= 1

    @pytest.mark.asyncio
    async def test_backtest_completed_gate_fails_win_rate(
        self, service, mock_db, mock_invoker
    ):
        """Test that completed backtest with failing win rate ends session."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.BACKTESTING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
            operation_id="op_backtest_456",
        )
        mock_db.get_active_session.return_value = mock_session

        # Mock operation status - completed with bad win rate
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_ops:
            mock_ops = MagicMock()
            mock_ops.get_operation = AsyncMock(
                return_value=MagicMock(
                    status="COMPLETED",
                    result_summary={
                        "win_rate": 0.30,  # Below 0.45 threshold
                        "max_drawdown": 0.25,
                        "sharpe_ratio": 1.2,
                    },
                )
            )
            mock_get_ops.return_value = mock_ops

            await service.check_and_trigger()

        # Session should be completed with FAILED_BACKTEST_GATE
        mock_db.complete_session.assert_called()
        complete_call = mock_db.complete_session.call_args
        assert (
            complete_call.kwargs.get("outcome") == SessionOutcome.FAILED_BACKTEST_GATE
        )

    @pytest.mark.asyncio
    async def test_backtest_operation_failed(self, service, mock_db, mock_invoker):
        """Test that failed backtest operation ends session."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.BACKTESTING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
            operation_id="op_backtest_456",
        )
        mock_db.get_active_session.return_value = mock_session

        # Mock operation status - failed
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_ops:
            mock_ops = MagicMock()
            mock_ops.get_operation = AsyncMock(
                return_value=MagicMock(status="FAILED", error_message="Data not found")
            )
            mock_get_ops.return_value = mock_ops

            await service.check_and_trigger()

        # Session should be completed with FAILED_BACKTEST
        mock_db.complete_session.assert_called()
        complete_call = mock_db.complete_session.call_args
        assert complete_call.kwargs.get("outcome") == SessionOutcome.FAILED_BACKTEST

    # =========================================================================
    # ASSESSING → COMPLETE transition tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_assessing_completes_successfully(
        self, service, mock_db, mock_invoker
    ):
        """Test that assessment completion marks session as success."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.ASSESSING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
        )
        mock_db.get_active_session.return_value = mock_session
        mock_db.get_recent_completed_sessions.return_value = []

        # Agent assessment succeeds
        mock_invoker.run.return_value = MagicMock(
            success=True,
            output="Strategy shows promising results...",
            input_tokens=150,
            output_tokens=300,
        )

        await service.check_and_trigger()

        # Session should be completed with SUCCESS
        mock_db.complete_session.assert_called()
        complete_call = mock_db.complete_session.call_args
        assert complete_call.kwargs.get("outcome") == SessionOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_assessing_fails_on_agent_error(self, service, mock_db, mock_invoker):
        """Test that assessment failure ends session appropriately."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.ASSESSING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
        )
        mock_db.get_active_session.return_value = mock_session
        mock_db.get_recent_completed_sessions.return_value = []

        # Agent assessment fails
        mock_invoker.run.return_value = MagicMock(
            success=False, error="API rate limit exceeded"
        )

        await service.check_and_trigger()

        # Session should be completed with FAILED_ASSESSMENT
        mock_db.complete_session.assert_called()
        complete_call = mock_db.complete_session.call_args
        assert complete_call.kwargs.get("outcome") == SessionOutcome.FAILED_ASSESSMENT

    # =========================================================================
    # Gate configuration tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_training_gate_uses_config(
        self, service, mock_db, mock_tool_executor
    ):
        """Test that training gate uses configured thresholds."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.TRAINING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
            operation_id="op_training_123",
        )
        mock_db.get_active_session.return_value = mock_session

        # Result that would pass default config but fail stricter config
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_ops:
            mock_ops = MagicMock()
            mock_ops.get_operation = AsyncMock(
                return_value=MagicMock(
                    status="COMPLETED",
                    result_summary={
                        "accuracy": 0.50,  # Passes default 0.45
                        "final_loss": 0.6,
                        "initial_loss": 1.0,
                    },
                )
            )
            mock_get_ops.return_value = mock_ops

            # With stricter environment config
            with patch.dict(
                "os.environ",
                {"TRAINING_GATE_MIN_ACCURACY": "0.6"},
            ):
                await service.check_and_trigger()

        # With stricter threshold (0.6), accuracy 0.50 fails
        # Should be completed with FAILED_TRAINING_GATE
        mock_db.complete_session.assert_called()
        complete_call = mock_db.complete_session.call_args
        assert (
            complete_call.kwargs.get("outcome") == SessionOutcome.FAILED_TRAINING_GATE
        )

    # =========================================================================
    # Edge case tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_training_session_without_operation_id(
        self, service, mock_db, mock_tool_executor
    ):
        """Test handling of training session without operation ID (error state)."""
        mock_session = AgentSession(
            id=1,
            phase=SessionPhase.TRAINING,
            created_at=MagicMock(),
            strategy_name="test_strategy",
            operation_id=None,  # Missing operation ID
        )
        mock_db.get_active_session.return_value = mock_session

        await service.check_and_trigger()

        # Should handle gracefully - mark as failed
        mock_db.complete_session.assert_called()
        complete_call = mock_db.complete_session.call_args
        assert complete_call.kwargs.get("outcome") == SessionOutcome.FAILED_TRAINING

"""
Unit tests for agent state management functions.

Tests cover:
- create_agent_session: Creates new session, returns session_id
- get_agent_state: Gets current session state by ID
- update_agent_state: Updates session phase and fields
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_agents.database.schema import SessionPhase


class TestCreateAgentSession:
    """Tests for create_agent_session function."""

    @pytest.mark.asyncio
    async def test_create_agent_session_returns_session_id(self):
        """Test that create_agent_session returns a session_id."""
        from research_agents.services.agent_state import create_agent_session

        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.create_session.return_value = MagicMock(
                id=42,
                phase=SessionPhase.IDLE,
                created_at=datetime.now(timezone.utc),
            )
            mock_get_db.return_value = mock_db

            result = await create_agent_session()

            assert result["success"] is True
            assert result["session_id"] == 42
            assert result["phase"] == "idle"
            mock_db.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_session_logs_action(self):
        """Test that creating a session logs the action."""
        from research_agents.services.agent_state import create_agent_session

        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_session = MagicMock(
                id=1,
                phase=SessionPhase.IDLE,
                created_at=datetime.now(timezone.utc),
            )
            mock_db.create_session.return_value = mock_session
            mock_get_db.return_value = mock_db

            await create_agent_session()

            # Should log the action
            mock_db.log_action.assert_called_once()
            call_args = mock_db.log_action.call_args
            assert call_args.kwargs["session_id"] == 1
            assert call_args.kwargs["tool_name"] == "create_agent_session"

    @pytest.mark.asyncio
    async def test_create_agent_session_handles_error(self):
        """Test that create_agent_session handles database errors."""
        from research_agents.services.agent_state import create_agent_session

        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.create_session.side_effect = Exception("Database error")
            mock_get_db.return_value = mock_db

            result = await create_agent_session()

            assert result["success"] is False
            assert "error" in result
            assert "Database error" in result["error"]


class TestGetAgentState:
    """Tests for get_agent_state function."""

    @pytest.mark.asyncio
    async def test_get_agent_state_returns_session_data(self):
        """Test that get_agent_state returns session data."""
        from research_agents.services.agent_state import get_agent_state

        now = datetime.now(timezone.utc)
        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_session.return_value = MagicMock(
                id=42,
                phase=SessionPhase.TRAINING,
                created_at=now,
                updated_at=now,
                strategy_name="test_strategy",
                operation_id="op_training_123",
                outcome=None,
            )
            mock_get_db.return_value = mock_db

            result = await get_agent_state(session_id=42)

            assert result["success"] is True
            assert result["session"]["id"] == 42
            assert result["session"]["phase"] == "training"
            assert result["session"]["strategy_name"] == "test_strategy"
            assert result["session"]["operation_id"] == "op_training_123"
            mock_db.get_session.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_get_agent_state_not_found(self):
        """Test that get_agent_state handles missing session."""
        from research_agents.services.agent_state import get_agent_state

        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_session.return_value = None
            mock_get_db.return_value = mock_db

            result = await get_agent_state(session_id=999)

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_agent_state_handles_error(self):
        """Test that get_agent_state handles database errors."""
        from research_agents.services.agent_state import get_agent_state

        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_session.side_effect = Exception("Connection failed")
            mock_get_db.return_value = mock_db

            result = await get_agent_state(session_id=1)

            assert result["success"] is False
            assert "error" in result


class TestUpdateAgentState:
    """Tests for update_agent_state function."""

    @pytest.mark.asyncio
    async def test_update_agent_state_updates_phase(self):
        """Test that update_agent_state updates the phase."""
        from research_agents.services.agent_state import update_agent_state

        now = datetime.now(timezone.utc)
        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.update_session.return_value = MagicMock(
                id=1,
                phase=SessionPhase.DESIGNING,
                created_at=now,
                updated_at=now,
                strategy_name=None,
                operation_id=None,
                outcome=None,
            )
            mock_get_db.return_value = mock_db

            result = await update_agent_state(session_id=1, phase="designing")

            assert result["success"] is True
            assert result["session"]["phase"] == "designing"
            mock_db.update_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_agent_state_updates_all_fields(self):
        """Test that update_agent_state can update all fields."""
        from research_agents.services.agent_state import update_agent_state

        now = datetime.now(timezone.utc)
        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.update_session.return_value = MagicMock(
                id=1,
                phase=SessionPhase.TRAINING,
                created_at=now,
                updated_at=now,
                strategy_name="my_strategy",
                operation_id="op_456",
                outcome=None,
            )
            mock_get_db.return_value = mock_db

            result = await update_agent_state(
                session_id=1,
                phase="training",
                strategy_name="my_strategy",
                operation_id="op_456",
            )

            assert result["success"] is True
            assert result["session"]["phase"] == "training"
            assert result["session"]["strategy_name"] == "my_strategy"
            assert result["session"]["operation_id"] == "op_456"

    @pytest.mark.asyncio
    async def test_update_agent_state_logs_action(self):
        """Test that updating state logs the action."""
        from research_agents.services.agent_state import update_agent_state

        now = datetime.now(timezone.utc)
        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.update_session.return_value = MagicMock(
                id=1,
                phase=SessionPhase.DESIGNING,
                created_at=now,
                updated_at=now,
                strategy_name=None,
                operation_id=None,
                outcome=None,
            )
            mock_get_db.return_value = mock_db

            await update_agent_state(session_id=1, phase="designing")

            mock_db.log_action.assert_called_once()
            call_args = mock_db.log_action.call_args
            assert call_args.kwargs["session_id"] == 1
            assert call_args.kwargs["tool_name"] == "update_agent_state"

    @pytest.mark.asyncio
    async def test_update_agent_state_invalid_phase(self):
        """Test that update_agent_state rejects invalid phase."""
        from research_agents.services.agent_state import update_agent_state

        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            result = await update_agent_state(session_id=1, phase="invalid_phase")

            assert result["success"] is False
            assert "invalid" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_update_agent_state_session_not_found(self):
        """Test that update_agent_state handles missing session."""
        from research_agents.services.agent_state import update_agent_state

        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.update_session.side_effect = ValueError("Session 999 not found")
            mock_get_db.return_value = mock_db

            result = await update_agent_state(session_id=999, phase="designing")

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_update_agent_state_handles_error(self):
        """Test that update_agent_state handles database errors."""
        from research_agents.services.agent_state import update_agent_state

        with patch("research_agents.services.agent_state.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.update_session.side_effect = Exception("Connection lost")
            mock_get_db.return_value = mock_db

            result = await update_agent_state(session_id=1, phase="designing")

            assert result["success"] is False
            assert "error" in result

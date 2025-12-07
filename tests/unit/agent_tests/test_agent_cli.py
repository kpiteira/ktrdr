"""
Unit tests for agent CLI commands.

Tests cover:
- Status command: Show current agent state
- Trigger command: Manually trigger agent cycle

These tests mock the database layer to avoid requiring PostgreSQL.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from ktrdr.cli.agent_commands import agent_app
from research_agents.database.schema import AgentSession, SessionPhase

runner = CliRunner()


class TestAgentStatusCommand:
    """Tests for ktrdr agent status command."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = AsyncMock()
        return db

    def test_status_no_sessions(self):
        """Test status command when no sessions exist."""
        with patch("ktrdr.cli.agent_commands.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_active_session.return_value = None
            mock_get_db.return_value = mock_db

            result = runner.invoke(agent_app, ["status"])

            assert result.exit_code == 0
            assert "No active session" in result.output

    def test_status_active_session_exists(self):
        """Test status command when an active session exists."""
        with patch("ktrdr.cli.agent_commands.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_session = AgentSession(
                id=1,
                phase=SessionPhase.TRAINING,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                strategy_name="test_strategy",
                operation_id="op_123",
                outcome=None,
            )
            mock_db.get_active_session.return_value = mock_session
            mock_get_db.return_value = mock_db

            result = runner.invoke(agent_app, ["status"])

            assert result.exit_code == 0
            # Check for session identifier in various formats
            assert "1" in result.output and "Session" in result.output
            assert "training" in result.output.lower()
            assert "test_strategy" in result.output

    def test_status_completed_session(self):
        """Test status command shows completed sessions correctly."""
        with patch("ktrdr.cli.agent_commands.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            # A completed session is not active, so get_active_session returns None
            mock_db.get_active_session.return_value = None
            mock_get_db.return_value = mock_db

            result = runner.invoke(agent_app, ["status"])

            assert result.exit_code == 0
            # Should indicate no active session
            assert "No active session" in result.output

    def test_status_verbose_mode(self):
        """Test status command with verbose flag shows more detail."""
        with patch("ktrdr.cli.agent_commands.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_session = AgentSession(
                id=3,
                phase=SessionPhase.DESIGNING,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                strategy_name=None,
                operation_id=None,
                outcome=None,
            )
            mock_db.get_active_session.return_value = mock_session
            mock_db.get_session_actions.return_value = []
            mock_get_db.return_value = mock_db

            result = runner.invoke(agent_app, ["status", "--verbose"])

            assert result.exit_code == 0
            assert "designing" in result.output.lower()


class TestAgentTriggerCommand:
    """Tests for ktrdr agent trigger command."""

    def test_trigger_no_active_session(self):
        """Test trigger command invokes agent when no active session."""
        with (
            patch("ktrdr.cli.agent_commands.get_agent_db") as mock_get_db,
            patch("ktrdr.cli.agent_commands.TriggerService") as mock_trigger_cls,
        ):
            mock_db = AsyncMock()
            mock_db.get_active_session.return_value = None
            mock_get_db.return_value = mock_db

            mock_trigger = MagicMock()
            mock_trigger.check_and_trigger = AsyncMock(
                return_value={
                    "triggered": True,
                    "reason": "no_active_session",
                    "session_id": 1,
                }
            )
            mock_trigger_cls.return_value = mock_trigger

            result = runner.invoke(agent_app, ["trigger"])

            assert result.exit_code == 0
            assert (
                "triggered" in result.output.lower()
                or "started" in result.output.lower()
            )

    def test_trigger_active_session_exists(self):
        """Test trigger command reports when active session exists."""
        with patch("ktrdr.cli.agent_commands.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_session = AgentSession(
                id=1,
                phase=SessionPhase.TRAINING,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                strategy_name="active_strategy",
                operation_id="op_456",
                outcome=None,
            )
            mock_db.get_active_session.return_value = mock_session
            mock_get_db.return_value = mock_db

            result = runner.invoke(agent_app, ["trigger"])

            assert result.exit_code == 0
            # Should indicate that there's already an active session
            assert (
                "active" in result.output.lower() or "already" in result.output.lower()
            )

    def test_trigger_disabled(self):
        """Test trigger command respects disabled state."""
        with (
            patch("ktrdr.cli.agent_commands.get_agent_db") as mock_get_db,
            patch("ktrdr.cli.agent_commands.TriggerService") as mock_trigger_cls,
        ):
            mock_db = AsyncMock()
            mock_db.get_active_session.return_value = None
            mock_get_db.return_value = mock_db

            mock_trigger = MagicMock()
            mock_trigger.check_and_trigger = AsyncMock(
                return_value={
                    "triggered": False,
                    "reason": "disabled",
                }
            )
            mock_trigger_cls.return_value = mock_trigger

            result = runner.invoke(agent_app, ["trigger"])

            assert result.exit_code == 0
            assert (
                "disabled" in result.output.lower()
                or "not triggered" in result.output.lower()
            )

    def test_trigger_dry_run(self):
        """Test trigger command with dry-run flag."""
        with patch("ktrdr.cli.agent_commands.get_agent_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_active_session.return_value = None
            mock_get_db.return_value = mock_db

            result = runner.invoke(agent_app, ["trigger", "--dry-run"])

            assert result.exit_code == 0
            # Dry run should not actually trigger
            assert "dry" in result.output.lower() or "would" in result.output.lower()


class TestAgentCommandsHelp:
    """Tests for CLI help output."""

    def test_agent_help(self):
        """Test that agent --help shows available commands."""
        result = runner.invoke(agent_app, ["--help"])

        assert result.exit_code == 0
        assert "status" in result.output
        assert "trigger" in result.output

    def test_status_help(self):
        """Test that agent status --help shows options."""
        result = runner.invoke(agent_app, ["status", "--help"])

        assert result.exit_code == 0
        assert "verbose" in result.output.lower() or "-v" in result.output

    def test_trigger_help(self):
        """Test that agent trigger --help shows options."""
        result = runner.invoke(agent_app, ["trigger", "--help"])

        assert result.exit_code == 0

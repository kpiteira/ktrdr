"""
Unit tests for research agent trigger service.

Tests cover:
- Configuration loading from environment
- Active session detection
- Agent invocation logic (mocked)
- Service start/stop lifecycle
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_agents.services.trigger import (
    TriggerConfig,
    TriggerService,
)


class TestTriggerConfig:
    """Tests for TriggerConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TriggerConfig()
        assert config.interval_seconds == 300  # 5 minutes
        assert config.enabled is True

    def test_config_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "AGENT_TRIGGER_INTERVAL_SECONDS": "60",
                "AGENT_ENABLED": "false",
            },
        ):
            config = TriggerConfig.from_env()
            assert config.interval_seconds == 60
            assert config.enabled is False

    def test_config_from_env_defaults(self):
        """Test that missing env vars use defaults."""
        with patch.dict("os.environ", {}, clear=True):
            config = TriggerConfig.from_env()
            assert config.interval_seconds == 300
            assert config.enabled is True


class TestTriggerService:
    """Tests for TriggerService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def mock_invoker(self):
        """Create a mock agent invoker."""
        invoker = AsyncMock()
        invoker.invoke.return_value = {"success": True, "session_id": 1}
        return invoker

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return TriggerConfig(interval_seconds=1, enabled=True)

    @pytest.mark.asyncio
    async def test_check_and_trigger_no_active_session(
        self, mock_db, mock_invoker, config
    ):
        """Test that agent is invoked when no active session."""
        mock_db.get_active_session.return_value = None

        service = TriggerService(config=config, db=mock_db, invoker=mock_invoker)
        result = await service.check_and_trigger()

        assert result["triggered"] is True
        mock_db.get_active_session.assert_called_once()
        mock_invoker.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_and_trigger_active_session_exists(
        self, mock_db, mock_invoker, config
    ):
        """Test that agent is NOT invoked when active session exists."""
        # Mock an active session
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.phase = "training"
        mock_db.get_active_session.return_value = mock_session

        service = TriggerService(config=config, db=mock_db, invoker=mock_invoker)
        result = await service.check_and_trigger()

        assert result["triggered"] is False
        assert result["reason"] == "active_session_exists"
        mock_db.get_active_session.assert_called_once()
        mock_invoker.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_and_trigger_disabled(self, mock_db, mock_invoker):
        """Test that agent is NOT invoked when service is disabled."""
        config = TriggerConfig(interval_seconds=1, enabled=False)

        service = TriggerService(config=config, db=mock_db, invoker=mock_invoker)
        result = await service.check_and_trigger()

        assert result["triggered"] is False
        assert result["reason"] == "disabled"
        mock_db.get_active_session.assert_not_called()
        mock_invoker.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_service_run_loop(self, mock_db, mock_invoker):
        """Test that service runs the check loop."""
        config = TriggerConfig(interval_seconds=0.1, enabled=True)
        mock_db.get_active_session.return_value = None

        service = TriggerService(config=config, db=mock_db, invoker=mock_invoker)

        # Run service for a short time
        run_task = asyncio.create_task(service.start())
        await asyncio.sleep(0.25)  # Allow ~2 iterations
        service.stop()
        await run_task

        # Should have been called at least once
        assert mock_db.get_active_session.call_count >= 1

    @pytest.mark.asyncio
    async def test_service_stop(self, mock_db, mock_invoker):
        """Test that service stops cleanly."""
        # Use very short interval to avoid test hanging
        config = TriggerConfig(interval_seconds=0.01, enabled=True)
        service = TriggerService(config=config, db=mock_db, invoker=mock_invoker)

        # Start and immediately stop
        run_task = asyncio.create_task(service.start())
        await asyncio.sleep(0.01)  # Give the service a moment to start
        service.stop()
        await run_task

        assert service._running is False

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

from research_agents.services.invoker import InvocationResult
from research_agents.services.trigger import TriggerConfig, TriggerService


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
        invoker.invoke.return_value = InvocationResult(
            success=True,
            exit_code=0,
            output={"session_id": 1},
            raw_output="",
            error=None,
        )
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


class TestTriggerServiceDesignPhase:
    """Tests for Phase 1 design phase behavior.

    These tests verify the trigger service correctly implements the
    "session first" pattern where session is created BEFORE invoking Claude.
    """

    @pytest.fixture
    def mock_db(self):
        """Create a mock database with full interface."""
        db = AsyncMock()
        # Mock session creation
        mock_session = MagicMock()
        mock_session.id = 42
        mock_session.phase = "designing"
        db.create_session.return_value = mock_session
        db.update_session.return_value = mock_session
        db.get_active_session.return_value = None
        db.get_recent_completed_sessions.return_value = []
        return db

    @pytest.fixture
    def mock_invoker(self):
        """Create a mock agent invoker."""
        invoker = AsyncMock()
        invoker.invoke.return_value = InvocationResult(
            success=True,
            exit_code=0,
            output={"status": "designed"},
            raw_output="",
            error=None,
        )
        return invoker

    @pytest.fixture
    def mock_context_provider(self):
        """Create a mock context provider for indicators/symbols."""
        provider = AsyncMock()
        provider.get_available_indicators.return_value = [
            {"id": "RSI", "name": "RSI", "type": "momentum"}
        ]
        provider.get_available_symbols.return_value = [
            {"symbol": "EURUSD", "available_timeframes": ["1h", "1d"]}
        ]
        return provider

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return TriggerConfig(interval_seconds=1, enabled=True)

    @pytest.mark.asyncio
    async def test_session_created_before_invocation(
        self, mock_db, mock_invoker, mock_context_provider, config
    ):
        """Test that session is created BEFORE agent is invoked.

        This is the key Phase 1 behavior change: create session first,
        then invoke agent with session_id in context.
        """
        service = TriggerService(
            config=config,
            db=mock_db,
            invoker=mock_invoker,
            context_provider=mock_context_provider,
        )

        await service.check_and_trigger()

        # Session should be created
        mock_db.create_session.assert_called_once()

        # Invoker should be called with session_id in context
        mock_invoker.invoke.assert_called_once()
        call_kwargs = mock_invoker.invoke.call_args

        # The prompt should contain the session ID
        assert "42" in call_kwargs.kwargs.get("prompt", "") or "42" in str(
            call_kwargs.args
        )

    @pytest.mark.asyncio
    async def test_session_phase_set_to_designing(
        self, mock_db, mock_invoker, mock_context_provider, config
    ):
        """Test that session phase is set to DESIGNING before invocation."""
        from research_agents.database.schema import SessionPhase

        service = TriggerService(
            config=config,
            db=mock_db,
            invoker=mock_invoker,
            context_provider=mock_context_provider,
        )

        await service.check_and_trigger()

        # Session should be updated to DESIGNING phase
        mock_db.update_session.assert_called()
        update_call = mock_db.update_session.call_args
        assert update_call.kwargs.get("phase") == SessionPhase.DESIGNING

    @pytest.mark.asyncio
    async def test_uses_strategy_designer_prompt(
        self, mock_db, mock_invoker, mock_context_provider, config
    ):
        """Test that strategy designer prompt is used (not phase0)."""
        service = TriggerService(
            config=config,
            db=mock_db,
            invoker=mock_invoker,
            context_provider=mock_context_provider,
        )

        await service.check_and_trigger()

        # Check that invoke was called with strategy designer prompt content
        call_kwargs = mock_invoker.invoke.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt", "")

        # Strategy designer prompt should contain these key elements
        assert "Strategy Designer" in system_prompt or "neuro-fuzzy" in system_prompt

    @pytest.mark.asyncio
    async def test_fetches_context_data(
        self, mock_db, mock_invoker, mock_context_provider, config
    ):
        """Test that indicators/symbols/recent strategies are fetched."""
        service = TriggerService(
            config=config,
            db=mock_db,
            invoker=mock_invoker,
            context_provider=mock_context_provider,
        )

        await service.check_and_trigger()

        # Context provider should be called to fetch data
        mock_context_provider.get_available_indicators.assert_called_once()
        mock_context_provider.get_available_symbols.assert_called_once()
        mock_db.get_recent_completed_sessions.assert_called()

    @pytest.mark.asyncio
    async def test_result_includes_session_id(
        self, mock_db, mock_invoker, mock_context_provider, config
    ):
        """Test that the trigger result includes the created session ID."""
        service = TriggerService(
            config=config,
            db=mock_db,
            invoker=mock_invoker,
            context_provider=mock_context_provider,
        )

        result = await service.check_and_trigger()

        assert result["triggered"] is True
        assert result["session_id"] == 42

    @pytest.mark.asyncio
    async def test_invocation_failure_marks_session_failed(
        self, mock_db, mock_context_provider, config
    ):
        """Test that invocation failure marks the session as failed."""
        from research_agents.database.schema import SessionOutcome

        mock_invoker = AsyncMock()
        mock_invoker.invoke.side_effect = Exception("Claude API error")

        service = TriggerService(
            config=config,
            db=mock_db,
            invoker=mock_invoker,
            context_provider=mock_context_provider,
        )

        await service.check_and_trigger()

        # Should complete session with failed outcome
        mock_db.complete_session.assert_called_once()
        complete_call = mock_db.complete_session.call_args
        assert complete_call.kwargs.get("outcome") == SessionOutcome.FAILED_DESIGN

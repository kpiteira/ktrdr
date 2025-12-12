"""
Tests for the background trigger loop (Task 1.10).

These tests verify:
1. Background loop starts when AGENT_ENABLED=true
2. Loop triggers at configured interval
3. Graceful shutdown on backend stop
4. TriggerService works with AnthropicAgentInvoker
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Test fixtures


@dataclass
class MockAgentResult:
    """Mock result from AnthropicAgentInvoker."""

    success: bool = True
    output: str = "Strategy designed successfully"
    input_tokens: int = 100
    output_tokens: int = 50
    error: str | None = None


class MockAnthropicInvoker:
    """Mock AnthropicAgentInvoker for testing."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.run_called = False
        self.run_count = 0
        self.last_prompt = None
        self.last_tools = None
        self.last_system_prompt = None

    async def run(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str,
        tool_executor: Any = None,
    ) -> MockAgentResult:
        """Mock the run method."""
        self.run_called = True
        self.run_count += 1
        self.last_prompt = prompt
        self.last_tools = tools
        self.last_system_prompt = system_prompt

        if self.should_fail:
            return MockAgentResult(success=False, error="Mock failure")
        return MockAgentResult()


class MockToolExecutor:
    """Mock tool executor for testing."""

    async def execute(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Mock tool execution."""
        return {"success": True}


class MockSession:
    """Mock session for database tests."""

    def __init__(self, session_id: int = 1, phase: str = "designing"):
        self.id = session_id
        self.phase = MagicMock(value=phase)
        self.strategy_name = None
        self.operation_id = None


class MockDatabase:
    """Mock database for testing."""

    def __init__(self):
        self.active_session = None
        self.created_sessions = []
        self.updated_sessions = []
        self.completed_sessions = []
        self._session_counter = 0

    async def get_active_session(self) -> MockSession | None:
        return self.active_session

    async def create_session(self) -> MockSession:
        self._session_counter += 1
        session = MockSession(session_id=self._session_counter)
        self.created_sessions.append(session)
        self.active_session = session
        return session

    async def update_session(
        self,
        session_id: int,
        phase: Any = None,
        strategy_name: str | None = None,
        operation_id: str | None = None,
    ) -> None:
        self.updated_sessions.append(
            {
                "session_id": session_id,
                "phase": phase,
                "strategy_name": strategy_name,
                "operation_id": operation_id,
            }
        )

    async def complete_session(self, session_id: int, outcome: Any) -> None:
        self.completed_sessions.append(
            {
                "session_id": session_id,
                "outcome": outcome,
            }
        )

    async def get_recent_completed_sessions(self, n: int = 5) -> list[dict[str, Any]]:
        return []


class MockContextProvider:
    """Mock context provider for testing."""

    async def get_available_indicators(self) -> list[dict[str, Any]]:
        return [{"name": "rsi", "description": "RSI indicator"}]

    async def get_available_symbols(self) -> list[dict[str, Any]]:
        return [{"symbol": "EURUSD", "timeframes": ["1h", "4h"]}]


# Tests for TriggerService with AnthropicAgentInvoker


class TestTriggerServiceWithAnthropicInvoker:
    """Test TriggerService works with the new AnthropicAgentInvoker pattern."""

    @pytest.mark.asyncio
    async def test_trigger_service_accepts_anthropic_invoker(self):
        """TriggerService should accept AnthropicAgentInvoker as invoker."""
        from research_agents.services.trigger import TriggerConfig, TriggerService

        config = TriggerConfig(interval_seconds=1, enabled=True)
        db = MockDatabase()
        invoker = MockAnthropicInvoker()
        context_provider = MockContextProvider()

        # Should not raise - TriggerService accepts the new invoker type
        service = TriggerService(
            config=config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
        )
        assert service is not None

    @pytest.mark.asyncio
    async def test_trigger_service_accepts_tool_executor(self):
        """TriggerService should accept optional tool_executor."""
        from research_agents.services.trigger import TriggerConfig, TriggerService

        config = TriggerConfig(interval_seconds=1, enabled=True)
        db = MockDatabase()
        invoker = MockAnthropicInvoker()
        context_provider = MockContextProvider()
        tool_executor = MockToolExecutor()

        # Should not raise - TriggerService accepts tool_executor
        service = TriggerService(
            config=config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
            tool_executor=tool_executor,
        )
        assert service is not None
        assert service.tool_executor == tool_executor

    @pytest.mark.asyncio
    async def test_trigger_service_passes_tools_to_invoker(self):
        """TriggerService should pass tool definitions to the invoker."""
        from research_agents.services.trigger import TriggerConfig, TriggerService

        config = TriggerConfig(interval_seconds=1, enabled=True)
        db = MockDatabase()
        invoker = MockAnthropicInvoker()
        context_provider = MockContextProvider()

        service = TriggerService(
            config=config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
        )

        # Trigger a cycle
        await service.check_and_trigger()

        # Invoker should have been called with tools
        assert invoker.run_called
        assert invoker.last_tools is not None
        assert len(invoker.last_tools) > 0

    @pytest.mark.asyncio
    async def test_trigger_service_uses_new_invoker_signature(self):
        """TriggerService should use run() method with correct signature."""
        from research_agents.services.trigger import TriggerConfig, TriggerService

        config = TriggerConfig(interval_seconds=1, enabled=True)
        db = MockDatabase()
        invoker = MockAnthropicInvoker()
        context_provider = MockContextProvider()
        tool_executor = MockToolExecutor()

        service = TriggerService(
            config=config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
            tool_executor=tool_executor,
        )

        await service.check_and_trigger()

        # Verify invoker was called with all expected parameters
        assert invoker.run_called
        assert invoker.last_prompt is not None
        assert invoker.last_system_prompt is not None
        assert invoker.last_tools is not None


# Tests for background loop in startup


class TestBackgroundTriggerLoop:
    """Test background trigger loop integration with API startup."""

    @pytest.mark.asyncio
    async def test_background_loop_starts_when_enabled(self):
        """Background loop should start when AGENT_ENABLED=true.

        Note: TriggerService.start() waits for interval FIRST before triggering,
        so we need to wait longer than the interval for a trigger to occur.
        """
        from research_agents.services.trigger import TriggerConfig, TriggerService

        # Use a short interval so the test completes quickly
        config = TriggerConfig(interval_seconds=0.1, enabled=True)
        db = MockDatabase()
        invoker = MockAnthropicInvoker()
        context_provider = MockContextProvider()

        service = TriggerService(
            config=config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
        )

        # Start in a task
        task = asyncio.create_task(service.start())

        # Wait longer than the interval for at least one trigger
        # (interval is 0.1s, so 0.3s should allow for at least one trigger)
        await asyncio.sleep(0.3)

        # Stop the service
        service.stop()
        await asyncio.sleep(0.1)

        # Should have triggered at least once
        assert invoker.run_count >= 1

        # Wait for task to complete
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()

    @pytest.mark.asyncio
    async def test_background_loop_does_not_start_when_disabled(self):
        """Background loop should not invoke agent when AGENT_ENABLED=false."""
        from research_agents.services.trigger import TriggerConfig, TriggerService

        config = TriggerConfig(interval_seconds=1, enabled=False)
        db = MockDatabase()
        invoker = MockAnthropicInvoker()
        context_provider = MockContextProvider()

        service = TriggerService(
            config=config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
        )

        # Run a single check (not the loop)
        result = await service.check_and_trigger()

        # Should not have invoked the agent
        assert result["triggered"] is False
        assert result["reason"] == "disabled"
        assert invoker.run_count == 0

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """Service should stop gracefully when stop() is called."""
        from research_agents.services.trigger import TriggerConfig, TriggerService

        config = TriggerConfig(interval_seconds=60, enabled=True)
        db = MockDatabase()
        invoker = MockAnthropicInvoker()
        context_provider = MockContextProvider()

        service = TriggerService(
            config=config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
        )

        # Start the service
        task = asyncio.create_task(service.start())

        # Give it time to start
        await asyncio.sleep(0.1)

        # Stop should complete quickly
        service.stop()

        # Should complete within a second, not waiting for the full 60s interval
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("Service did not stop within timeout")

    @pytest.mark.asyncio
    async def test_loop_respects_interval(self):
        """Service should check for triggers at configured interval.

        Note: After first successful invocation, session becomes active
        and subsequent triggers skip (this is correct behavior). This test
        verifies the trigger CHECK happens at interval, not that invocations
        happen at interval.
        """
        from research_agents.services.trigger import TriggerConfig, TriggerService

        # Short interval for testing
        config = TriggerConfig(interval_seconds=1, enabled=True)
        db = MockDatabase()
        invoker = MockAnthropicInvoker()
        context_provider = MockContextProvider()

        # Track trigger checks
        trigger_check_count = 0
        original_check = TriggerService.check_and_trigger

        async def counting_check(self):
            nonlocal trigger_check_count
            trigger_check_count += 1
            return await original_check(self)

        service = TriggerService(
            config=config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
        )

        # Patch the check_and_trigger method to count calls
        service.check_and_trigger = lambda: counting_check(service)

        # Start and let it run for multiple intervals
        task = asyncio.create_task(service.start())

        # Wait for approximately 2.5 intervals (should be 3 checks)
        await asyncio.sleep(2.5)

        # Stop the service
        service.stop()
        await asyncio.wait_for(task, timeout=1.0)

        # Should have checked 2-3 times (timing can vary)
        assert (
            trigger_check_count >= 2
        ), f"Expected at least 2 checks, got {trigger_check_count}"
        # Invoker should have been called once (first check)
        assert invoker.run_count == 1, f"Expected 1 invocation, got {invoker.run_count}"


# Tests for startup.py integration


class TestStartupIntegration:
    """Test that startup.py correctly integrates the trigger loop."""

    def test_startup_has_agent_trigger_support(self):
        """startup.py should have agent trigger loop support."""
        from ktrdr.api import startup

        # Check that start_agent_trigger_loop function exists
        assert hasattr(startup, "start_agent_trigger_loop")

    @pytest.mark.asyncio
    async def test_start_agent_trigger_loop_function(self):
        """start_agent_trigger_loop should create and start the trigger service."""
        from ktrdr.api.startup import start_agent_trigger_loop

        # Mock the dependencies at import locations (lazy imports in the function)
        with patch.dict("os.environ", {"AGENT_ENABLED": "true"}):
            # Create mocks
            mock_invoker = AsyncMock()
            mock_db = AsyncMock()
            mock_context = MagicMock()
            mock_service = AsyncMock()
            mock_service.start = AsyncMock()

            # Patch all the imports used inside start_agent_trigger_loop
            with patch(
                "ktrdr.agents.invoker.AnthropicAgentInvoker",
                return_value=mock_invoker,
            ):
                with patch(
                    "research_agents.database.queries.get_agent_db",
                    return_value=mock_db,
                ):
                    with patch(
                        "ktrdr.api.services.agent_context.AgentMCPContextProvider",
                        return_value=mock_context,
                    ):
                        with patch(
                            "research_agents.services.trigger.TriggerService",
                        ) as mock_trigger_service:
                            mock_trigger_service.return_value = mock_service

                            # Create a task but cancel it immediately
                            task = asyncio.create_task(start_agent_trigger_loop())

                            # Give it a moment to start
                            await asyncio.sleep(0.1)

                            # Cancel the task
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass

                            # Verify TriggerService was created
                            mock_trigger_service.assert_called_once()


class TestAgentServiceWithAnthropicInvoker:
    """Test AgentService uses AnthropicAgentInvoker for manual triggers."""

    @pytest.mark.asyncio
    async def test_agent_service_uses_anthropic_invoker(self):
        """AgentService should use AnthropicAgentInvoker, not ClaudeCodeInvoker."""
        # This test verifies the code change - check imports in agent_service.py
        import inspect

        from ktrdr.api.services.agent_service import AgentService

        # Get the source code of the _run_agent_with_tracking method
        # (Agent execution is now in background task, invoker created there)
        source = inspect.getsource(AgentService._run_agent_with_tracking)

        # Should use AnthropicAgentInvoker, not ClaudeCodeInvoker
        assert "AnthropicAgentInvoker" in source or "anthropic" in source.lower()
        # Should NOT use ClaudeCodeInvoker
        assert "ClaudeCodeInvoker" not in source

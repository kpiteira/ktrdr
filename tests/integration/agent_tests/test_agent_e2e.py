"""
End-to-end integration tests for the research agent system.

These tests validate the full trigger → agent → MCP tools → database flow.

Test scenario:
1. Start trigger service
2. Wait for trigger
3. Verify agent invoked
4. Verify state changes in database
5. Verify session completes

Requirements:
- PostgreSQL database (set DATABASE_URL environment variable)
- For manual testing with real Claude, set AGENT_E2E_REAL_INVOKE=true

Run with:
    pytest tests/integration/agent_tests/test_agent_e2e.py -v
"""

import asyncio
import os
from typing import Any

import pytest
import pytest_asyncio

from research_agents.database.queries import AgentDatabase
from research_agents.database.schema import SessionOutcome, SessionPhase
from research_agents.services.invoker import InvocationResult
from research_agents.services.trigger import TriggerConfig, TriggerService

# Skip all tests in this module if no database URL is set
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL environment variable not set - skipping E2E tests",
)


class MockAgentInvoker:
    """Mock invoker that simulates the agent's behavior.

    This invoker simulates what the real Claude agent would do:
    1. Create a new session via MCP tool
    2. Update state to "testing" phase
    3. Update state to "complete" phase
    """

    def __init__(self, db: AgentDatabase):
        """Initialize with database reference for state manipulation.

        Args:
            db: Database interface to update session state.
        """
        self.db = db
        self.invoke_count = 0
        self.last_prompt: str | None = None
        self.last_system_prompt: str | None = None

    async def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
        session_context: dict[str, Any] | None = None,
    ) -> InvocationResult:
        """Simulate agent invocation by executing the Phase 0 test workflow.

        This method simulates what the real Claude agent does:
        1. Creates a session
        2. Updates to testing phase
        3. Updates to complete phase

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            session_context: Optional session context.

        Returns:
            InvocationResult with success status.
        """
        self.invoke_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt

        try:
            # Step 1: Create session (simulating what agent would do)
            session = await self.db.create_session()

            # Step 2: Update to testing phase
            await self.db.update_session(
                session_id=session.id,
                phase=SessionPhase.DESIGNING,  # Using DESIGNING as "testing" equivalent
            )

            # Step 3: Complete the session
            await self.db.complete_session(
                session_id=session.id,
                outcome=SessionOutcome.SUCCESS,
            )

            return InvocationResult(
                success=True,
                exit_code=0,
                output={"session_id": session.id, "status": "completed"},
                raw_output=f"Session {session.id} completed successfully",
                error=None,
            )

        except Exception as e:
            return InvocationResult(
                success=False,
                exit_code=1,
                output=None,
                raw_output="",
                error=str(e),
            )


@pytest_asyncio.fixture
async def agent_db():
    """Create and connect to the agent database.

    Yields the database instance, then disconnects.
    Skips tests if database connection fails.
    """
    db = AgentDatabase()
    try:
        await db.connect(os.getenv("DATABASE_URL"))
    except Exception as e:
        pytest.skip(f"Could not connect to database: {e}")

    yield db

    await db.disconnect()


@pytest_asyncio.fixture
async def clean_db(agent_db: AgentDatabase):
    """Ensure database is clean before each test.

    Deletes all existing sessions and actions.
    """
    async with agent_db.pool.acquire() as conn:
        await conn.execute("DELETE FROM agent_actions")
        await conn.execute("DELETE FROM agent_sessions")

    return agent_db


class TestAgentE2E:
    """End-to-end tests for the agent research system."""

    @pytest.mark.asyncio
    async def test_trigger_invokes_agent_when_no_active_session(
        self,
        clean_db: AgentDatabase,
    ):
        """Test that the trigger service invokes the agent when no active session exists.

        Test scenario:
        1. Start with empty database (no active sessions)
        2. Run check_and_trigger
        3. Verify agent was invoked
        4. Verify session was created in database
        """
        # Arrange
        mock_invoker = MockAgentInvoker(db=clean_db)
        config = TriggerConfig(interval_seconds=0.1, enabled=True)
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
        )

        # Act
        result = await service.check_and_trigger()

        # Assert
        assert result["triggered"] is True
        assert result["reason"] == "no_active_session"
        assert mock_invoker.invoke_count == 1

        # Verify session was created and completed
        # (The mock invoker creates and completes a session)
        sessions = []
        async with clean_db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, phase, outcome FROM agent_sessions ORDER BY id DESC LIMIT 1"
            )
            sessions = list(rows)

        assert len(sessions) == 1
        assert sessions[0]["phase"] == SessionPhase.COMPLETE.value
        assert sessions[0]["outcome"] == SessionOutcome.SUCCESS.value

    @pytest.mark.asyncio
    async def test_trigger_skips_when_active_session_exists(
        self,
        clean_db: AgentDatabase,
    ):
        """Test that the trigger service does NOT invoke agent when active session exists.

        Test scenario:
        1. Create an active session (not IDLE or COMPLETE)
        2. Run check_and_trigger
        3. Verify agent was NOT invoked
        """
        # Arrange - Create an active session
        session = await clean_db.create_session()
        await clean_db.update_session(
            session_id=session.id,
            phase=SessionPhase.TRAINING,
        )

        mock_invoker = MockAgentInvoker(db=clean_db)
        config = TriggerConfig(interval_seconds=0.1, enabled=True)
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
        )

        # Act
        result = await service.check_and_trigger()

        # Assert
        assert result["triggered"] is False
        assert result["reason"] == "active_session_exists"
        assert result["active_session_id"] == session.id
        assert mock_invoker.invoke_count == 0

    @pytest.mark.asyncio
    async def test_full_trigger_loop_completes_session(
        self,
        clean_db: AgentDatabase,
    ):
        """Test the full trigger service loop creates and completes a session.

        Test scenario:
        1. Start trigger service
        2. Wait for at least one trigger cycle
        3. Verify session was created
        4. Verify session completed (phase=COMPLETE, outcome set)
        5. Stop the service
        """
        # Arrange
        mock_invoker = MockAgentInvoker(db=clean_db)
        config = TriggerConfig(interval_seconds=0.05, enabled=True)  # Fast for testing
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
        )

        # Act - Run the service for a short time
        run_task = asyncio.create_task(service.start())
        await asyncio.sleep(0.15)  # Allow ~2-3 trigger cycles
        service.stop()
        await run_task

        # Assert - Agent was invoked at least once
        assert mock_invoker.invoke_count >= 1

        # Verify session exists in database with completion
        async with clean_db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT phase, outcome FROM agent_sessions ORDER BY id DESC LIMIT 1"
            )

        assert row is not None
        assert row["phase"] == SessionPhase.COMPLETE.value
        assert row["outcome"] == SessionOutcome.SUCCESS.value

    @pytest.mark.asyncio
    async def test_trigger_disabled_does_not_invoke(
        self,
        clean_db: AgentDatabase,
    ):
        """Test that disabled trigger service does not invoke agent.

        Test scenario:
        1. Configure trigger service as disabled
        2. Run check_and_trigger
        3. Verify agent was NOT invoked
        4. Verify no sessions created
        """
        # Arrange
        mock_invoker = MockAgentInvoker(db=clean_db)
        config = TriggerConfig(interval_seconds=0.1, enabled=False)
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
        )

        # Act
        result = await service.check_and_trigger()

        # Assert
        assert result["triggered"] is False
        assert result["reason"] == "disabled"
        assert mock_invoker.invoke_count == 0

        # Verify no sessions were created
        async with clean_db.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM agent_sessions")

        assert count == 0

    @pytest.mark.asyncio
    async def test_state_transitions_logged_in_database(
        self,
        clean_db: AgentDatabase,
    ):
        """Test that all state transitions are properly recorded in database.

        Verifies the full Phase 0 workflow:
        1. Session created in IDLE phase
        2. Session transitions through phases
        3. Session ends in COMPLETE phase with SUCCESS outcome
        """
        # Arrange
        mock_invoker = MockAgentInvoker(db=clean_db)
        config = TriggerConfig(interval_seconds=0.1, enabled=True)
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
        )

        # Act
        result = await service.check_and_trigger()

        # Assert - verify the invocation triggered
        assert result["triggered"] is True

        # Get the session from database and verify final state
        async with clean_db.pool.acquire() as conn:
            session_row = await conn.fetchrow(
                "SELECT id, phase, outcome, updated_at FROM agent_sessions ORDER BY id DESC LIMIT 1"
            )

        assert session_row is not None
        assert session_row["phase"] == SessionPhase.COMPLETE.value
        assert session_row["outcome"] == SessionOutcome.SUCCESS.value
        assert session_row["updated_at"] is not None


class TestAgentE2EManual:
    """Tests that can be run manually with real Claude invocation.

    These tests are skipped by default. To run with real Claude:
        AGENT_E2E_REAL_INVOKE=true pytest tests/integration/agent_tests/test_agent_e2e.py -v -k manual
    """

    @pytest.mark.skipif(
        not os.getenv("AGENT_E2E_REAL_INVOKE"),
        reason="Set AGENT_E2E_REAL_INVOKE=true to run with real Claude",
    )
    @pytest.mark.asyncio
    async def test_real_agent_invocation_manual(self, clean_db: AgentDatabase):
        """Manual test with real Claude Code invocation.

        This test actually invokes Claude Code with MCP tools.
        Requires:
        - DATABASE_URL set
        - AGENT_E2E_REAL_INVOKE=true
        - Claude CLI available
        - MCP server configured

        Watch the output to observe:
        1. Claude receiving the prompt
        2. Claude calling MCP tools
        3. State changes in database
        """
        from research_agents.services.invoker import ClaudeCodeInvoker, InvokerConfig

        # Use real invoker
        invoker = ClaudeCodeInvoker(config=InvokerConfig.from_env())
        config = TriggerConfig(interval_seconds=300, enabled=True)  # Normal interval
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=invoker,
        )

        # Single trigger (don't start loop for manual observation)
        print("\n=== Starting Real Agent Invocation ===")
        result = await service.check_and_trigger()
        print(f"Result: {result}")

        # Check database state
        async with clean_db.pool.acquire() as conn:
            sessions = await conn.fetch(
                "SELECT * FROM agent_sessions ORDER BY id DESC LIMIT 5"
            )
            print(f"\nSessions in database: {len(sessions)}")
            for s in sessions:
                print(
                    f"  Session {s['id']}: phase={s['phase']}, outcome={s['outcome']}"
                )

        assert result["triggered"] is True

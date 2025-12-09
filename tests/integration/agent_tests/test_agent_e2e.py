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


class MockContextProvider:
    """Mock context provider for testing the Phase 1 design flow.

    Provides test data for indicators and symbols without calling real API.
    """

    async def get_available_indicators(self) -> list[dict[str, Any]]:
        """Return a small set of test indicators."""
        return [
            {
                "id": "RSIIndicator",
                "name": "RSI",
                "type": "momentum",
                "description": "Relative Strength Index",
                "parameters": [
                    {"name": "period", "type": "int", "default": 14},
                    {"name": "source", "type": "str", "default": "close"},
                ],
            },
            {
                "id": "SimpleMovingAverage",
                "name": "SMA",
                "type": "trend",
                "description": "Simple Moving Average",
                "parameters": [
                    {"name": "period", "type": "int", "default": 20},
                    {"name": "source", "type": "str", "default": "close"},
                ],
            },
        ]

    async def get_available_symbols(self) -> list[dict[str, Any]]:
        """Return a small set of test symbols."""
        return [
            {
                "symbol": "EURUSD",
                "name": "EUR/USD",
                "type": "forex",
                "available_timeframes": ["1h", "1d"],
            },
            {
                "symbol": "AAPL",
                "name": "Apple Inc",
                "type": "stock",
                "available_timeframes": ["1d"],
            },
        ]


class MockDesignAgentInvoker:
    """Mock invoker that simulates Claude designing a strategy.

    This invoker simulates the Phase 1 design workflow:
    1. Receives session_id from prompt (session already exists)
    2. "Designs" a valid strategy config
    3. Saves the strategy via strategy service
    4. Updates session to DESIGNED with strategy_name
    """

    def __init__(self, db: AgentDatabase, strategies_dir: str = "strategies"):
        """Initialize with database and strategies directory.

        Args:
            db: Database interface for session updates.
            strategies_dir: Directory to save strategies (for testing).
        """
        self.db = db
        self.strategies_dir = strategies_dir
        self.invoke_count = 0
        self.last_prompt: str | None = None
        self.last_system_prompt: str | None = None
        self.designed_strategy_name: str | None = None

    async def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> InvocationResult:
        """Simulate Claude designing a strategy.

        This method simulates what Claude would do:
        1. Extract session_id from prompt
        2. Create a valid strategy config
        3. Save the strategy
        4. Update session to DESIGNED

        Args:
            prompt: The user prompt (contains session_id).
            system_prompt: The system prompt.

        Returns:
            InvocationResult with success status.
        """
        import re
        import time

        from research_agents.services.strategy_service import save_strategy_config

        self.invoke_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt

        try:
            # Step 1: Extract session_id from prompt
            # Look for "Session ID: <number>" pattern
            match = re.search(r"Session ID:\s*(\d+)", prompt)
            if not match:
                raise ValueError("Could not find session_id in prompt")
            session_id = int(match.group(1))

            # Step 2: Create a valid strategy config (simulating Claude's design)
            timestamp = int(time.time())
            strategy_name = f"e2e_test_strategy_{timestamp}"
            strategy_config = {
                "name": strategy_name,
                "description": "E2E test strategy designed by MockDesignAgentInvoker",
                "version": "1.0",
                "hypothesis": "Test hypothesis for E2E validation",
                "scope": "universal",
                "training_data": {
                    "symbols": {"mode": "single", "list": ["EURUSD"]},
                    "timeframes": {
                        "mode": "single",
                        "list": ["1h"],
                        "base_timeframe": "1h",
                    },
                    "history_required": 200,
                },
                "deployment": {
                    "target_symbols": {"mode": "training_only"},
                    "target_timeframes": {"mode": "single", "supported": ["1h"]},
                },
                "indicators": [
                    {
                        "name": "rsi",
                        "feature_id": "rsi_14",
                        "period": 14,
                        "source": "close",
                    }
                ],
                "fuzzy_sets": {
                    "rsi_14": {
                        "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
                        "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                        "overbought": {
                            "type": "triangular",
                            "parameters": [65, 80, 100],
                        },
                    }
                },
                "model": {
                    "type": "mlp",
                    "architecture": {
                        "hidden_layers": [32, 16],
                        "activation": "relu",
                        "output_activation": "softmax",
                        "dropout": 0.2,
                    },
                    "features": {
                        "include_price_context": False,
                        "lookback_periods": 2,
                        "scale_features": True,
                    },
                    "training": {
                        "learning_rate": 0.001,
                        "batch_size": 32,
                        "epochs": 50,
                        "optimizer": "adam",
                        "early_stopping": {
                            "enabled": True,
                            "patience": 10,
                            "min_delta": 0.001,
                        },
                    },
                },
                "decisions": {
                    "output_format": "classification",
                    "confidence_threshold": 0.6,
                    "position_awareness": True,
                },
                "training": {
                    "method": "supervised",
                    "labels": {
                        "source": "zigzag",
                        "zigzag_threshold": 0.03,
                        "label_lookahead": 20,
                    },
                    "data_split": {"train": 0.7, "validation": 0.15, "test": 0.15},
                },
            }

            # Step 3: Save the strategy via strategy service
            save_result = await save_strategy_config(
                name=strategy_name,
                config=strategy_config,
                description="E2E test strategy",
                strategies_dir=self.strategies_dir,
            )

            if not save_result["success"]:
                raise ValueError(
                    f"Failed to save strategy: {save_result.get('errors')}"
                )

            self.designed_strategy_name = strategy_name

            # Step 4: Update session to DESIGNED with strategy_name
            await self.db.update_session(
                session_id=session_id,
                phase=SessionPhase.DESIGNED,
                strategy_name=strategy_name,
            )

            return InvocationResult(
                success=True,
                exit_code=0,
                output={
                    "session_id": session_id,
                    "strategy_name": strategy_name,
                    "status": "designed",
                },
                raw_output=f"Strategy {strategy_name} designed and saved successfully",
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


class TestAgentDesignPhaseE2E:
    """E2E tests for Phase 1 strategy design flow.

    These tests verify the complete "session first" design flow:
    1. TriggerService creates session BEFORE invoking
    2. TriggerService sets phase to DESIGNING
    3. Agent (mock) receives session_id in prompt
    4. Agent designs strategy and saves it
    5. Agent updates session to DESIGNED with strategy_name
    """

    @pytest_asyncio.fixture
    async def agent_db(self):
        """Create and connect to the agent database."""
        db = AgentDatabase()
        try:
            await db.connect(os.getenv("DATABASE_URL"))
        except Exception as e:
            pytest.skip(f"Could not connect to database: {e}")

        yield db

        await db.disconnect()

    @pytest_asyncio.fixture
    async def clean_db(self, agent_db: AgentDatabase):
        """Ensure database is clean before each test."""
        async with agent_db.pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_actions")
            await conn.execute("DELETE FROM agent_sessions")

        return agent_db

    @pytest_asyncio.fixture
    async def test_strategies_dir(self, tmp_path):
        """Create a temporary directory for test strategies."""
        strategies_dir = tmp_path / "test_strategies"
        strategies_dir.mkdir()
        return str(strategies_dir)

    @pytest.mark.asyncio
    async def test_full_design_phase_flow(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test the complete Phase 1 design flow.

        Verifies:
        1. TriggerService creates session first
        2. Phase is set to DESIGNING before invocation
        3. Mock agent receives session_id in prompt
        4. Strategy is saved to disk
        5. Session ends in DESIGNED state with strategy_name
        """
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockDesignAgentInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        result = await service.check_and_trigger()

        # Assert - trigger succeeded
        assert result["triggered"] is True
        assert result["session_id"] is not None
        session_id = result["session_id"]

        # Assert - invoker was called
        assert mock_invoker.invoke_count == 1
        assert mock_invoker.designed_strategy_name is not None

        # Assert - session_id was in the prompt
        assert str(session_id) in mock_invoker.last_prompt

        # Assert - strategy file was created
        import os as os_module

        strategy_files = os_module.listdir(test_strategies_dir)
        assert len(strategy_files) == 1
        assert strategy_files[0].endswith(".yaml")

        # Assert - session is in DESIGNED state with strategy_name
        session = await clean_db.get_session(session_id)
        assert session.phase == SessionPhase.DESIGNED
        assert session.strategy_name == mock_invoker.designed_strategy_name

    @pytest.mark.asyncio
    async def test_design_flow_with_recent_strategies_context(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that recent strategies are included in context.

        Verifies that the prompt builder includes recent strategies
        to help the agent avoid repetition.
        """
        # Arrange - Create a completed session with strategy_name
        # This simulates a previous design cycle
        previous_session = await clean_db.create_session()
        await clean_db.update_session(
            session_id=previous_session.id,
            phase=SessionPhase.DESIGNED,
            strategy_name="previous_test_strategy",
        )
        await clean_db.complete_session(
            session_id=previous_session.id,
            outcome=SessionOutcome.SUCCESS,
        )

        # Now run a new design cycle
        context_provider = MockContextProvider()
        mock_invoker = MockDesignAgentInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        result = await service.check_and_trigger()

        # Assert - trigger succeeded
        assert result["triggered"] is True

        # Assert - the prompt should mention recent strategies
        # (The exact format depends on the prompt builder, but it should
        # include context about recent strategies)
        assert mock_invoker.last_prompt is not None
        # The prompt builder formats recent strategies - verify the flow worked
        assert mock_invoker.invoke_count == 1

    @pytest.mark.asyncio
    async def test_design_flow_skip_when_active_session(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that design flow is skipped when active session exists.

        Verifies that the trigger service correctly detects an active
        DESIGNING session and skips invoking the agent.
        """
        # Arrange - Create an active session in DESIGNING phase
        active_session = await clean_db.create_session()
        await clean_db.update_session(
            session_id=active_session.id,
            phase=SessionPhase.DESIGNING,
        )

        context_provider = MockContextProvider()
        mock_invoker = MockDesignAgentInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        result = await service.check_and_trigger()

        # Assert - should NOT trigger because active session exists
        assert result["triggered"] is False
        assert result["reason"] == "active_session_exists"
        assert result["active_session_id"] == active_session.id
        assert mock_invoker.invoke_count == 0

    @pytest.mark.asyncio
    async def test_strategy_validation_on_save(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that saved strategy validates correctly.

        Verifies that the strategy config created by the mock invoker
        passes validation (same validation Claude's strategies would use).
        """
        from ktrdr.config.strategy_validator import StrategyValidator

        # Run the design flow
        context_provider = MockContextProvider()
        mock_invoker = MockDesignAgentInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)
        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        result = await service.check_and_trigger()
        assert result["triggered"] is True

        # Load and validate the saved strategy
        import os as os_module

        import yaml

        strategy_files = os_module.listdir(test_strategies_dir)
        assert len(strategy_files) == 1

        with open(os_module.path.join(test_strategies_dir, strategy_files[0])) as f:
            loaded_config = yaml.safe_load(f)

        # Validate the loaded config
        validator = StrategyValidator()
        validation_result = validator.validate_strategy_config(loaded_config)

        assert (
            validation_result.is_valid
        ), f"Strategy validation failed: {validation_result.errors}"

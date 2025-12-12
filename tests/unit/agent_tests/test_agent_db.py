"""
Unit tests for research agents database layer.

Tests cover:
- Schema dataclass definitions
- Query helper functions (with mocked database)
- State transitions and validations
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_agents.database.queries import AgentDatabase
from research_agents.database.schema import (
    AgentAction,
    AgentSession,
    SessionOutcome,
    SessionPhase,
)


class TestSessionPhase:
    """Tests for SessionPhase enum."""

    def test_phase_values_exist(self):
        """Verify all required phases exist."""
        assert SessionPhase.IDLE.value == "idle"
        assert SessionPhase.DESIGNING.value == "designing"
        assert SessionPhase.TRAINING.value == "training"
        assert SessionPhase.BACKTESTING.value == "backtesting"
        assert SessionPhase.ASSESSING.value == "assessing"
        assert SessionPhase.COMPLETE.value == "complete"

    def test_phase_from_string(self):
        """Test creating phase from string."""
        assert SessionPhase("idle") == SessionPhase.IDLE
        assert SessionPhase("designing") == SessionPhase.DESIGNING


class TestSessionOutcome:
    """Tests for SessionOutcome enum."""

    def test_outcome_values_exist(self):
        """Verify all required outcomes exist."""
        assert SessionOutcome.SUCCESS.value == "success"
        assert SessionOutcome.FAILED_DESIGN.value == "failed_design"
        assert SessionOutcome.FAILED_TRAINING.value == "failed_training"
        assert SessionOutcome.FAILED_TRAINING_GATE.value == "failed_training_gate"
        assert SessionOutcome.FAILED_BACKTEST.value == "failed_backtest"
        assert SessionOutcome.FAILED_BACKTEST_GATE.value == "failed_backtest_gate"
        assert SessionOutcome.FAILED_ASSESSMENT.value == "failed_assessment"


class TestAgentSession:
    """Tests for AgentSession dataclass."""

    def test_create_session(self):
        """Test creating a session with required fields."""
        session = AgentSession(
            id=1,
            phase=SessionPhase.IDLE,
            created_at=datetime.now(timezone.utc),
        )
        assert session.id == 1
        assert session.phase == SessionPhase.IDLE
        assert session.strategy_name is None
        assert session.operation_id is None
        assert session.outcome is None

    def test_session_with_all_fields(self):
        """Test session with all fields populated."""
        now = datetime.now(timezone.utc)
        session = AgentSession(
            id=1,
            phase=SessionPhase.TRAINING,
            created_at=now,
            updated_at=now,
            strategy_name="neuro_mean_reversion",
            operation_id="op_training_123",
            outcome=None,
        )
        assert session.strategy_name == "neuro_mean_reversion"
        assert session.operation_id == "op_training_123"

    def test_session_assessment_fields_default_to_none(self):
        """Test that assessment fields default to None (Task 2.7)."""
        session = AgentSession(
            id=1,
            phase=SessionPhase.IDLE,
            created_at=datetime.now(timezone.utc),
        )
        assert session.assessment_text is None
        assert session.assessment_metrics is None

    def test_session_with_assessment_text(self):
        """Test session with assessment text populated (Task 2.7)."""
        now = datetime.now(timezone.utc)
        assessment = """
        ## Strategy Assessment

        This strategy showed promise with stable training convergence.
        The model achieved 52% accuracy which exceeds threshold.

        ### What Worked
        - RSI indicator provided good mean reversion signals
        - Gaussian fuzzy sets captured gradual transitions well

        ### What Didn't Work
        - Sharpe ratio was below expectations

        ### Suggestions
        - Try adding volume as secondary indicator
        - Consider longer training period
        """
        session = AgentSession(
            id=1,
            phase=SessionPhase.COMPLETE,
            created_at=now,
            updated_at=now,
            strategy_name="test_strategy",
            outcome=SessionOutcome.SUCCESS,
            assessment_text=assessment,
        )
        assert session.assessment_text == assessment
        assert "RSI indicator" in session.assessment_text

    def test_session_with_assessment_metrics(self):
        """Test session with assessment metrics populated (Task 2.7)."""
        now = datetime.now(timezone.utc)
        metrics = {
            "training": {
                "accuracy": 0.52,
                "final_loss": 0.65,
                "initial_loss": 0.95,
                "loss_reduction": 0.316,
            },
            "backtest": {
                "win_rate": 0.48,
                "sharpe_ratio": 0.12,
                "max_drawdown": 0.18,
                "total_return": 0.05,
            },
            "gate_results": {
                "training_gate_passed": True,
                "backtest_gate_passed": True,
            },
        }
        session = AgentSession(
            id=1,
            phase=SessionPhase.COMPLETE,
            created_at=now,
            updated_at=now,
            strategy_name="test_strategy",
            outcome=SessionOutcome.SUCCESS,
            assessment_metrics=metrics,
        )
        assert session.assessment_metrics == metrics
        assert session.assessment_metrics["training"]["accuracy"] == 0.52
        assert session.assessment_metrics["backtest"]["win_rate"] == 0.48

    def test_session_is_active(self):
        """Test is_active property."""
        active_session = AgentSession(
            id=1,
            phase=SessionPhase.TRAINING,
            created_at=datetime.now(timezone.utc),
        )
        assert active_session.is_active is True

        idle_session = AgentSession(
            id=2,
            phase=SessionPhase.IDLE,
            created_at=datetime.now(timezone.utc),
        )
        assert idle_session.is_active is False

        complete_session = AgentSession(
            id=3,
            phase=SessionPhase.COMPLETE,
            created_at=datetime.now(timezone.utc),
        )
        assert complete_session.is_active is False


class TestAgentAction:
    """Tests for AgentAction dataclass."""

    def test_create_action(self):
        """Test creating an action log entry."""
        action = AgentAction(
            id=1,
            session_id=10,
            tool_name="update_agent_state",
            tool_args={"phase": "training"},
            result={"success": True},
            created_at=datetime.now(timezone.utc),
        )
        assert action.id == 1
        assert action.session_id == 10
        assert action.tool_name == "update_agent_state"
        assert action.tool_args == {"phase": "training"}
        assert action.result == {"success": True}

    def test_action_with_token_counts(self):
        """Test action with token tracking."""
        action = AgentAction(
            id=1,
            session_id=10,
            tool_name="create_agent_session",
            tool_args={},
            result={"session_id": 1},
            created_at=datetime.now(timezone.utc),
            input_tokens=100,
            output_tokens=50,
        )
        assert action.input_tokens == 100
        assert action.output_tokens == 50


class TestAgentDatabase:
    """Tests for AgentDatabase query helpers."""

    @pytest.fixture
    def mock_pool(self):
        """Create a mock connection pool with proper async context manager support."""
        pool = MagicMock()
        conn = AsyncMock()

        # Create an async context manager mock for pool.acquire()
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = acquire_cm

        return pool, conn

    @pytest.mark.asyncio
    async def test_create_session(self, mock_pool):
        """Test creating a new session."""
        pool, conn = mock_pool
        conn.fetchrow.return_value = {
            "id": 1,
            "phase": "idle",
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "strategy_name": None,
            "operation_id": None,
            "outcome": None,
        }

        db = AgentDatabase(pool)
        session = await db.create_session()

        assert session.id == 1
        assert session.phase == SessionPhase.IDLE
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session(self, mock_pool):
        """Test getting a session by ID."""
        pool, conn = mock_pool
        now = datetime.now(timezone.utc)
        conn.fetchrow.return_value = {
            "id": 1,
            "phase": "training",
            "created_at": now,
            "updated_at": now,
            "strategy_name": "test_strategy",
            "operation_id": "op_123",
            "outcome": None,
        }

        db = AgentDatabase(pool)
        session = await db.get_session(1)

        assert session is not None
        assert session.id == 1
        assert session.phase == SessionPhase.TRAINING
        assert session.strategy_name == "test_strategy"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, mock_pool):
        """Test getting a non-existent session."""
        pool, conn = mock_pool
        conn.fetchrow.return_value = None

        db = AgentDatabase(pool)
        session = await db.get_session(999)

        assert session is None

    @pytest.mark.asyncio
    async def test_get_active_session(self, mock_pool):
        """Test getting the active session."""
        pool, conn = mock_pool
        now = datetime.now(timezone.utc)
        conn.fetchrow.return_value = {
            "id": 5,
            "phase": "designing",
            "created_at": now,
            "updated_at": now,
            "strategy_name": None,
            "operation_id": None,
            "outcome": None,
        }

        db = AgentDatabase(pool)
        session = await db.get_active_session()

        assert session is not None
        assert session.id == 5
        assert session.phase == SessionPhase.DESIGNING

    @pytest.mark.asyncio
    async def test_update_session_phase(self, mock_pool):
        """Test updating session phase."""
        pool, conn = mock_pool
        now = datetime.now(timezone.utc)
        conn.fetchrow.return_value = {
            "id": 1,
            "phase": "training",
            "created_at": now,
            "updated_at": now,
            "strategy_name": "my_strategy",
            "operation_id": "op_456",
            "outcome": None,
        }

        db = AgentDatabase(pool)
        session = await db.update_session(
            session_id=1,
            phase=SessionPhase.TRAINING,
            strategy_name="my_strategy",
            operation_id="op_456",
        )

        assert session.phase == SessionPhase.TRAINING
        assert session.strategy_name == "my_strategy"
        assert session.operation_id == "op_456"

    @pytest.mark.asyncio
    async def test_complete_session(self, mock_pool):
        """Test completing a session with outcome."""
        pool, conn = mock_pool
        now = datetime.now(timezone.utc)
        conn.fetchrow.return_value = {
            "id": 1,
            "phase": "complete",
            "created_at": now,
            "updated_at": now,
            "strategy_name": "my_strategy",
            "operation_id": None,
            "outcome": "success",
            "assessment_text": None,
            "assessment_metrics": None,
        }

        db = AgentDatabase(pool)
        session = await db.complete_session(
            session_id=1,
            outcome=SessionOutcome.SUCCESS,
        )

        assert session.phase == SessionPhase.COMPLETE
        assert session.outcome == SessionOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_complete_session_with_assessment(self, mock_pool):
        """Test completing a session with assessment data (Task 2.7)."""
        pool, conn = mock_pool
        now = datetime.now(timezone.utc)
        assessment_text = "Strategy showed promising results with 52% accuracy."
        assessment_metrics = {
            "training": {"accuracy": 0.52, "final_loss": 0.65},
            "backtest": {"win_rate": 0.48, "sharpe_ratio": 0.12},
        }
        conn.fetchrow.return_value = {
            "id": 1,
            "phase": "complete",
            "created_at": now,
            "updated_at": now,
            "strategy_name": "my_strategy",
            "operation_id": None,
            "outcome": "success",
            "assessment_text": assessment_text,
            "assessment_metrics": assessment_metrics,
        }

        db = AgentDatabase(pool)
        session = await db.complete_session(
            session_id=1,
            outcome=SessionOutcome.SUCCESS,
            assessment_text=assessment_text,
            assessment_metrics=assessment_metrics,
        )

        assert session.phase == SessionPhase.COMPLETE
        assert session.outcome == SessionOutcome.SUCCESS
        assert session.assessment_text == assessment_text
        assert session.assessment_metrics == assessment_metrics
        assert session.assessment_metrics["training"]["accuracy"] == 0.52

    @pytest.mark.asyncio
    async def test_get_session_with_assessment(self, mock_pool):
        """Test getting a session with assessment data (Task 2.7)."""
        pool, conn = mock_pool
        now = datetime.now(timezone.utc)
        assessment_text = "Full cycle completed successfully."
        assessment_metrics = {"training": {"accuracy": 0.55}}
        conn.fetchrow.return_value = {
            "id": 1,
            "phase": "complete",
            "created_at": now,
            "updated_at": now,
            "strategy_name": "test_strategy",
            "operation_id": None,
            "outcome": "success",
            "assessment_text": assessment_text,
            "assessment_metrics": assessment_metrics,
        }

        db = AgentDatabase(pool)
        session = await db.get_session(1)

        assert session is not None
        assert session.assessment_text == assessment_text
        assert session.assessment_metrics == assessment_metrics

    @pytest.mark.asyncio
    async def test_log_action(self, mock_pool):
        """Test logging a tool call action."""
        pool, conn = mock_pool
        now = datetime.now(timezone.utc)
        conn.fetchrow.return_value = {
            "id": 100,
            "session_id": 1,
            "tool_name": "start_training",
            "tool_args": {"strategy": "test"},
            "result": {"operation_id": "op_123"},
            "created_at": now,
            "input_tokens": 500,
            "output_tokens": 200,
        }

        db = AgentDatabase(pool)
        action = await db.log_action(
            session_id=1,
            tool_name="start_training",
            tool_args={"strategy": "test"},
            result={"operation_id": "op_123"},
            input_tokens=500,
            output_tokens=200,
        )

        assert action.id == 100
        assert action.tool_name == "start_training"
        assert action.input_tokens == 500

    @pytest.mark.asyncio
    async def test_get_session_actions(self, mock_pool):
        """Test getting all actions for a session."""
        pool, conn = mock_pool
        now = datetime.now(timezone.utc)
        conn.fetch.return_value = [
            {
                "id": 1,
                "session_id": 10,
                "tool_name": "tool_1",
                "tool_args": {},
                "result": {},
                "created_at": now,
                "input_tokens": None,
                "output_tokens": None,
            },
            {
                "id": 2,
                "session_id": 10,
                "tool_name": "tool_2",
                "tool_args": {},
                "result": {},
                "created_at": now,
                "input_tokens": None,
                "output_tokens": None,
            },
        ]

        db = AgentDatabase(pool)
        actions = await db.get_session_actions(10)

        assert len(actions) == 2
        assert actions[0].tool_name == "tool_1"
        assert actions[1].tool_name == "tool_2"


class TestAgentDatabaseConnection:
    """Tests for database connection management."""

    @pytest.mark.asyncio
    async def test_connect_creates_tables(self):
        """Test that connect creates tables if they don't exist."""
        with patch("research_agents.database.queries.asyncpg") as mock_asyncpg:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()

            # Mock create_pool to return a coroutine that resolves to mock_pool
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            # Setup acquire context manager
            acquire_cm = MagicMock()
            acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            acquire_cm.__aexit__ = AsyncMock(return_value=None)
            mock_pool.acquire.return_value = acquire_cm

            db = AgentDatabase(pool=None)
            await db.connect("postgresql://test:test@localhost/test")

            # Verify pool was created
            mock_asyncpg.create_pool.assert_called_once()
            # Verify tables were created
            mock_conn.execute.assert_called()

    @pytest.mark.asyncio
    async def test_disconnect_closes_pool(self):
        """Test that disconnect closes the connection pool."""
        mock_pool = AsyncMock()
        db = AgentDatabase(pool=mock_pool)

        await db.disconnect()

        mock_pool.close.assert_called_once()

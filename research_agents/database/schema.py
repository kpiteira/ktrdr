"""
Database schema definitions for research agents.

Defines dataclasses for agent_sessions and agent_actions tables.
Phase 0 minimal set - only what's needed for basic plumbing validation.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class SessionPhase(str, Enum):
    """Phase of the agent research cycle."""

    IDLE = "idle"
    DESIGNING = "designing"
    DESIGNED = "designed"  # Design complete, ready for training (Phase 1 end state)
    TRAINING = "training"
    BACKTESTING = "backtesting"
    ASSESSING = "assessing"
    COMPLETE = "complete"


class SessionOutcome(str, Enum):
    """Outcome of a completed research cycle."""

    SUCCESS = "success"
    FAILED_DESIGN = "failed_design"
    FAILED_TRAINING = "failed_training"
    FAILED_TRAINING_GATE = "failed_training_gate"
    FAILED_BACKTEST = "failed_backtest"
    FAILED_BACKTEST_GATE = "failed_backtest_gate"
    FAILED_ASSESSMENT = "failed_assessment"


@dataclass
class AgentSession:
    """Represents an agent research cycle session.

    Tracks the state of a single research cycle from start to completion.
    Each session goes through phases: IDLE -> DESIGNING -> TRAINING ->
    BACKTESTING -> ASSESSING -> COMPLETE (or fails at any stage).

    Attributes:
        id: Unique session identifier.
        phase: Current phase of the research cycle.
        created_at: When the session was created.
        updated_at: When the session was last updated.
        strategy_name: Name of the strategy being designed (if set).
        operation_id: ID of the current KTRDR operation (training/backtest).
        outcome: Final outcome when session completes.
    """

    id: int
    phase: SessionPhase
    created_at: datetime
    updated_at: datetime | None = None
    strategy_name: str | None = None
    operation_id: str | None = None
    outcome: SessionOutcome | None = None

    @property
    def is_active(self) -> bool:
        """Check if session is currently active (not idle or complete)."""
        return self.phase not in (SessionPhase.IDLE, SessionPhase.COMPLETE)


@dataclass
class AgentAction:
    """Log entry for an agent tool call.

    Records every MCP tool call made by the agent for debugging,
    cost tracking, and observability.

    Attributes:
        id: Unique action identifier.
        session_id: ID of the parent session.
        tool_name: Name of the MCP tool called.
        tool_args: Arguments passed to the tool.
        result: Result returned by the tool.
        created_at: When the action was logged.
        input_tokens: Number of input tokens (for cost tracking).
        output_tokens: Number of output tokens (for cost tracking).
    """

    id: int
    session_id: int
    tool_name: str
    tool_args: dict[str, Any]
    result: dict[str, Any]
    created_at: datetime
    input_tokens: int | None = None
    output_tokens: int | None = None


# SQL statements for table creation
CREATE_TABLES_SQL = """
-- Agent sessions table
CREATE TABLE IF NOT EXISTS agent_sessions (
    id SERIAL PRIMARY KEY,
    phase VARCHAR(50) NOT NULL DEFAULT 'idle',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    strategy_name VARCHAR(255),
    operation_id VARCHAR(255),
    outcome VARCHAR(50)
);

-- Index for finding active sessions quickly
CREATE INDEX IF NOT EXISTS idx_agent_sessions_phase
ON agent_sessions(phase)
WHERE phase NOT IN ('idle', 'complete');

-- Agent actions table
CREATE TABLE IF NOT EXISTS agent_actions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES agent_sessions(id),
    tool_name VARCHAR(255) NOT NULL,
    tool_args JSONB NOT NULL DEFAULT '{}',
    result JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    input_tokens INTEGER,
    output_tokens INTEGER
);

-- Index for finding actions by session
CREATE INDEX IF NOT EXISTS idx_agent_actions_session_id
ON agent_actions(session_id);
"""

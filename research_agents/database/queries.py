"""
Database query helpers for research agents.

Provides async methods for interacting with agent_sessions and agent_actions tables.
Uses asyncpg for PostgreSQL connectivity.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

from research_agents.database.schema import (
    CREATE_TABLES_SQL,
    AgentAction,
    AgentSession,
    SessionOutcome,
    SessionPhase,
)

logger = structlog.get_logger(__name__)


class AgentDatabase:
    """Database interface for agent sessions and actions.

    Provides async methods for CRUD operations on agent state.
    Manages connection pool lifecycle.

    Usage:
        db = AgentDatabase()
        await db.connect(database_url)
        session = await db.create_session()
        ...
        await db.disconnect()

    Or with existing pool:
        db = AgentDatabase(pool=existing_pool)
    """

    def __init__(self, pool: asyncpg.Pool | None = None):
        """Initialize database interface.

        Args:
            pool: Optional existing connection pool. If None, call connect() first.
        """
        self._pool = pool

    @property
    def pool(self) -> asyncpg.Pool:
        """Get connection pool, raising if not connected."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    async def connect(self, database_url: str | None = None) -> None:
        """Connect to the database and create tables if needed.

        Args:
            database_url: PostgreSQL connection URL. If None, uses DATABASE_URL env var.

        Raises:
            RuntimeError: If already connected.
            asyncpg.PostgresError: If connection fails.
        """
        if self._pool is not None:
            raise RuntimeError("Already connected. Call disconnect() first.")

        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("No database URL provided and DATABASE_URL not set")

        logger.info("Connecting to database", url=url.split("@")[-1])  # Log host only

        self._pool = await asyncpg.create_pool(url, min_size=1, max_size=5)

        # Create tables if they don't exist
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)

        logger.info("Database connected and tables created")

    async def disconnect(self) -> None:
        """Close the database connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Database disconnected")

    # Session operations

    async def create_session(self) -> AgentSession:
        """Create a new agent session in IDLE phase.

        Returns:
            The newly created session.
        """
        query = """
            INSERT INTO agent_sessions (phase, created_at)
            VALUES ($1, $2)
            RETURNING id, phase, created_at, updated_at, strategy_name, operation_id, outcome
        """
        now = datetime.now(timezone.utc)

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, SessionPhase.IDLE.value, now)

        return self._row_to_session(row)

    async def get_session(self, session_id: int) -> AgentSession | None:
        """Get a session by ID.

        Args:
            session_id: The session ID to retrieve.

        Returns:
            The session if found, None otherwise.
        """
        query = """
            SELECT id, phase, created_at, updated_at, strategy_name, operation_id, outcome
            FROM agent_sessions
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, session_id)

        if row is None:
            return None

        return self._row_to_session(row)

    async def get_active_session(self) -> AgentSession | None:
        """Get the currently active session (if any).

        An active session is one not in IDLE or COMPLETE phase.

        Returns:
            The active session if found, None otherwise.
        """
        query = """
            SELECT id, phase, created_at, updated_at, strategy_name, operation_id, outcome
            FROM agent_sessions
            WHERE phase NOT IN ($1, $2)
            ORDER BY created_at DESC
            LIMIT 1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query, SessionPhase.IDLE.value, SessionPhase.COMPLETE.value
            )

        if row is None:
            return None

        return self._row_to_session(row)

    async def update_session(
        self,
        session_id: int,
        phase: SessionPhase | None = None,
        strategy_name: str | None = None,
        operation_id: str | None = None,
    ) -> AgentSession:
        """Update session state.

        Args:
            session_id: The session to update.
            phase: New phase (optional).
            strategy_name: Strategy name to set (optional).
            operation_id: Operation ID to set (optional).

        Returns:
            The updated session.

        Raises:
            ValueError: If session not found.
        """
        # Build dynamic update query
        updates = ["updated_at = $1"]
        params: list[Any] = [datetime.now(timezone.utc)]
        param_idx = 2

        if phase is not None:
            updates.append(f"phase = ${param_idx}")
            params.append(phase.value)
            param_idx += 1

        if strategy_name is not None:
            updates.append(f"strategy_name = ${param_idx}")
            params.append(strategy_name)
            param_idx += 1

        if operation_id is not None:
            updates.append(f"operation_id = ${param_idx}")
            params.append(operation_id)
            param_idx += 1

        params.append(session_id)

        query = f"""
            UPDATE agent_sessions
            SET {", ".join(updates)}
            WHERE id = ${param_idx}
            RETURNING id, phase, created_at, updated_at, strategy_name, operation_id, outcome
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if row is None:
            raise ValueError(f"Session {session_id} not found")

        return self._row_to_session(row)

    async def complete_session(
        self,
        session_id: int,
        outcome: SessionOutcome,
    ) -> AgentSession:
        """Complete a session with the given outcome.

        Args:
            session_id: The session to complete.
            outcome: The final outcome.

        Returns:
            The completed session.

        Raises:
            ValueError: If session not found.
        """
        query = """
            UPDATE agent_sessions
            SET phase = $1, outcome = $2, updated_at = $3, operation_id = NULL
            WHERE id = $4
            RETURNING id, phase, created_at, updated_at, strategy_name, operation_id, outcome
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                SessionPhase.COMPLETE.value,
                outcome.value,
                datetime.now(timezone.utc),
                session_id,
            )

        if row is None:
            raise ValueError(f"Session {session_id} not found")

        return self._row_to_session(row)

    # Action operations

    async def log_action(
        self,
        session_id: int,
        tool_name: str,
        tool_args: dict[str, Any],
        result: dict[str, Any],
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> AgentAction:
        """Log a tool call action.

        Args:
            session_id: The parent session ID.
            tool_name: Name of the tool called.
            tool_args: Arguments passed to the tool.
            result: Result returned by the tool.
            input_tokens: Number of input tokens (optional).
            output_tokens: Number of output tokens (optional).

        Returns:
            The logged action.
        """
        query = """
            INSERT INTO agent_actions
                (session_id, tool_name, tool_args, result, created_at, input_tokens, output_tokens)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, session_id, tool_name, tool_args, result, created_at, input_tokens, output_tokens
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                session_id,
                tool_name,
                json.dumps(tool_args),
                json.dumps(result),
                datetime.now(timezone.utc),
                input_tokens,
                output_tokens,
            )

        return self._row_to_action(row)

    async def get_session_actions(self, session_id: int) -> list[AgentAction]:
        """Get all actions for a session.

        Args:
            session_id: The session ID.

        Returns:
            List of actions in chronological order.
        """
        query = """
            SELECT id, session_id, tool_name, tool_args, result, created_at, input_tokens, output_tokens
            FROM agent_actions
            WHERE session_id = $1
            ORDER BY created_at ASC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, session_id)

        return [self._row_to_action(row) for row in rows]

    async def get_recent_completed_sessions(
        self, n: int = 5
    ) -> list[dict[str, Any]]:
        """Get the N most recent completed sessions with strategy info.

        Returns sessions that have an outcome (completed), ordered by created_at DESC.

        Args:
            n: Maximum number of sessions to return.

        Returns:
            List of dicts with: id, strategy_name, outcome, created_at
        """
        query = """
            SELECT id, strategy_name, outcome, created_at
            FROM agent_sessions
            WHERE outcome IS NOT NULL
            ORDER BY created_at DESC
            LIMIT $1
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, n)

        return [
            {
                "id": row["id"],
                "strategy_name": row["strategy_name"],
                "outcome": row["outcome"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # Helper methods

    def _row_to_session(self, row: asyncpg.Record) -> AgentSession:
        """Convert a database row to an AgentSession."""
        return AgentSession(
            id=row["id"],
            phase=SessionPhase(row["phase"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            strategy_name=row["strategy_name"],
            operation_id=row["operation_id"],
            outcome=SessionOutcome(row["outcome"]) if row["outcome"] else None,
        )

    def _row_to_action(self, row: asyncpg.Record) -> AgentAction:
        """Convert a database row to an AgentAction."""
        # Handle both string and dict for JSONB columns
        tool_args = row["tool_args"]
        result = row["result"]

        if isinstance(tool_args, str):
            tool_args = json.loads(tool_args)
        if isinstance(result, str):
            result = json.loads(result)

        return AgentAction(
            id=row["id"],
            session_id=row["session_id"],
            tool_name=row["tool_name"],
            tool_args=tool_args,
            result=result,
            created_at=row["created_at"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
        )


# Singleton instance for convenience
_db: AgentDatabase | None = None


async def get_agent_db() -> AgentDatabase:
    """Get the global AgentDatabase instance.

    Creates and connects the database on first call.

    Returns:
        The connected AgentDatabase instance.
    """
    global _db
    if _db is None:
        _db = AgentDatabase()
        await _db.connect()
    return _db

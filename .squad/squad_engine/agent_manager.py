"""AgentManager — session lifecycle and spawn_agent tool.

Manages PersistentAgentSession instances for squad agents.
First call for a role creates a new session; subsequent calls
reuse the existing session (multi-turn within a cycle).
"""

from __future__ import annotations

from pathlib import Path

from ktrdr import get_logger
from ktrdr.agents.runtime.protocol import AgentResult
from squad_engine.context import ContextLoader
from squad_engine.session import PersistentAgentSession

logger = get_logger(__name__)

# All valid squad roles
ALL_ROLES = {"director", "engineer", "quant", "inventor", "scout", "critic", "architect", "scribe"}


class AgentManager:
    """Manages squad agent sessions within a cycle.

    Creates sessions on first spawn, reuses on subsequent calls.
    Tears down all sessions at cycle end.
    """

    def __init__(
        self,
        context_loader: ContextLoader,
        charter_dir: Path | None = None,
        allowed_roles: set[str] | None = None,
    ) -> None:
        self._context_loader = context_loader
        self._charter_dir = charter_dir or Path(__file__).resolve().parent.parent / "agents"
        self._allowed_roles = allowed_roles or ALL_ROLES
        self._sessions: dict[str, PersistentAgentSession] = {}

    @property
    def active_sessions(self) -> dict[str, PersistentAgentSession]:
        return dict(self._sessions)

    @property
    def total_cost_usd(self) -> float:
        return sum(s.total_cost_usd for s in self._sessions.values())

    async def spawn_agent(
        self,
        role: str,
        message: str,
        context: list[str] | None = None,
    ) -> AgentResult:
        """Spawn an agent or send a message to an existing session.

        First call for a role: creates PersistentAgentSession with charter + history.
        Subsequent calls: sends message to existing session (multi-turn).
        """
        if role not in self._allowed_roles:
            raise ValueError(
                f"Role '{role}' not allowed. Allowed: {sorted(self._allowed_roles)}"
            )

        if role not in self._sessions:
            session = self._create_session(role)
            self._sessions[role] = session

            # Resolve context file paths
            context_paths = None
            if context:
                context_paths = [
                    str(self._context_loader.shared_dir / p) for p in context
                ]

            await session.start(context_files=context_paths)
            logger.info("Spawned new session for %s", role)

        session = self._sessions[role]
        return await session.query(message)

    async def teardown_all(self) -> None:
        """Stop all active sessions. Called at end of cycle."""
        for role, session in self._sessions.items():
            try:
                await session.stop()
            except Exception:
                logger.exception("Error tearing down %s session", role)

        self._sessions.clear()
        logger.info("All sessions torn down")

    def _create_session(self, role: str) -> PersistentAgentSession:
        """Create a new PersistentAgentSession for a role."""
        charter_path = self._charter_dir / role / "charter.md"
        history_path = self._context_loader.shared_dir / "agents" / role / "history.md"

        return PersistentAgentSession(
            role=role,
            charter_path=charter_path,
            history_path=history_path if history_path.exists() else None,
        )

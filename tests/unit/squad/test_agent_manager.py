"""Tests for AgentManager — session lifecycle + spawn_agent tool."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure .squad/ is on sys.path
_squad_dir = str(Path(__file__).resolve().parents[3] / ".squad")
if _squad_dir not in sys.path:
    sys.path.insert(0, _squad_dir)

from squad_engine.agent_manager import AgentManager  # noqa: E402
from squad_engine.context import ContextLoader  # noqa: E402

from ktrdr.agents.runtime.protocol import AgentResult  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    """Create mock KB + charter structure."""
    # Charters in .squad/agents/
    squad_dir = tmp_path / "squad"
    for role in ("engineer", "scribe", "director", "quant"):
        agent_dir = squad_dir / "agents" / role
        agent_dir.mkdir(parents=True)
        (agent_dir / "charter.md").write_text(f"You are the {role}.")

    # KB shared dir with histories
    shared_dir = tmp_path / "shared"
    for role in ("engineer", "scribe", "director", "quant"):
        history_dir = shared_dir / "agents" / role
        history_dir.mkdir(parents=True)
        (history_dir / "history.md").write_text(f"## {role} history")

    return tmp_path


@pytest.fixture
def context_loader(kb_dir: Path) -> ContextLoader:
    return ContextLoader(shared_dir=str(kb_dir / "shared"))


def _make_mock_session():
    """Create a mock PersistentAgentSession."""
    session = AsyncMock()
    session.start = AsyncMock()
    session.query = AsyncMock(
        return_value=AgentResult(
            output="Done.",
            cost_usd=0.05,
            turns=1,
            transcript=[],
            session_id="sess_1",
        )
    )
    session.stop = AsyncMock()
    session.is_alive = True
    session.total_cost_usd = 0.05
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgentManager:
    @pytest.mark.asyncio
    async def test_first_spawn_creates_new_session(
        self, kb_dir: Path, context_loader: ContextLoader
    ):
        manager = AgentManager(
            context_loader=context_loader,
            charter_dir=kb_dir / "squad" / "agents",
        )
        mock_session = _make_mock_session()

        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            return_value=mock_session,
        ):
            result = await manager.spawn_agent("engineer", "Design a strategy")

        assert isinstance(result, AgentResult)
        assert result.output == "Done."
        assert "engineer" in manager.active_sessions
        mock_session.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_second_spawn_reuses_session(
        self, kb_dir: Path, context_loader: ContextLoader
    ):
        manager = AgentManager(
            context_loader=context_loader,
            charter_dir=kb_dir / "squad" / "agents",
        )
        mock_session = _make_mock_session()

        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            return_value=mock_session,
        ):
            await manager.spawn_agent("engineer", "First message")
            await manager.spawn_agent("engineer", "Second message")

        # start() called only once (first spawn), query() called for both
        mock_session.start.assert_awaited_once()
        assert mock_session.query.await_count == 2

    @pytest.mark.asyncio
    async def test_invalid_role_raises_error(
        self, kb_dir: Path, context_loader: ContextLoader
    ):
        manager = AgentManager(
            context_loader=context_loader,
            charter_dir=kb_dir / "squad" / "agents",
            allowed_roles={"engineer", "scribe"},
        )

        with pytest.raises(ValueError, match="quant"):
            await manager.spawn_agent("quant", "Check costs")

    @pytest.mark.asyncio
    async def test_teardown_all_stops_all_sessions(
        self, kb_dir: Path, context_loader: ContextLoader
    ):
        manager = AgentManager(
            context_loader=context_loader,
            charter_dir=kb_dir / "squad" / "agents",
        )
        mock_eng = _make_mock_session()
        mock_scribe = _make_mock_session()
        sessions = {"engineer": mock_eng, "scribe": mock_scribe}

        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            side_effect=lambda **kw: sessions[kw["role"]],
        ):
            await manager.spawn_agent("engineer", "Work")
            await manager.spawn_agent("scribe", "Record")
            await manager.teardown_all()

        mock_eng.stop.assert_awaited_once()
        mock_scribe.stop.assert_awaited_once()
        assert len(manager.active_sessions) == 0

    @pytest.mark.asyncio
    async def test_total_cost_aggregates_across_sessions(
        self, kb_dir: Path, context_loader: ContextLoader
    ):
        manager = AgentManager(
            context_loader=context_loader,
            charter_dir=kb_dir / "squad" / "agents",
        )
        mock_eng = _make_mock_session()
        mock_eng.total_cost_usd = 0.10
        mock_scribe = _make_mock_session()
        mock_scribe.total_cost_usd = 0.05

        sessions = {"engineer": mock_eng, "scribe": mock_scribe}
        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            side_effect=lambda **kw: sessions[kw["role"]],
        ):
            await manager.spawn_agent("engineer", "Work")
            await manager.spawn_agent("scribe", "Record")

        assert manager.total_cost_usd == pytest.approx(0.15)

    @pytest.mark.asyncio
    async def test_context_files_passed_to_session(
        self, kb_dir: Path, context_loader: ContextLoader
    ):
        manager = AgentManager(
            context_loader=context_loader,
            charter_dir=kb_dir / "squad" / "agents",
        )
        mock_session = _make_mock_session()

        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            return_value=mock_session,
        ):
            await manager.spawn_agent(
                "engineer",
                "Design strategy",
                context=["knowledge/synthesis.md"],
            )

        # Context files should be resolved and passed to start()
        start_call = mock_session.start.call_args
        assert start_call is not None
        expected_path = str(context_loader.shared_dir / "knowledge/synthesis.md")
        assert expected_path in start_call.kwargs.get("context_files", [])

    @pytest.mark.asyncio
    async def test_spawn_after_teardown_creates_fresh(
        self, kb_dir: Path, context_loader: ContextLoader
    ):
        manager = AgentManager(
            context_loader=context_loader,
            charter_dir=kb_dir / "squad" / "agents",
        )
        mock_session1 = _make_mock_session()
        mock_session2 = _make_mock_session()
        call_count = {"n": 0}

        def make_session(**kw):
            call_count["n"] += 1
            return mock_session1 if call_count["n"] == 1 else mock_session2

        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            side_effect=make_session,
        ):
            await manager.spawn_agent("engineer", "First cycle")
            await manager.teardown_all()
            await manager.spawn_agent("engineer", "Second cycle")

        # Two separate sessions created
        assert call_count["n"] == 2
        mock_session1.stop.assert_awaited_once()
        mock_session2.start.assert_awaited_once()


# ---------------------------------------------------------------------------
# M2: Full Agent Roster + Concurrent Sessions
# ---------------------------------------------------------------------------


class TestM2AllRolesAvailable:
    """All 7 agent roles should be spawnable when no restriction applied."""

    ALL_CONSULTANT_ROLES = [
        "engineer",
        "quant",
        "inventor",
        "scout",
        "critic",
        "architect",
        "scribe",
    ]

    @pytest.fixture
    def full_kb_dir(self, tmp_path: Path) -> Path:
        """Create KB + charter structure for all 7 roles."""
        squad_dir = tmp_path / "squad"
        shared_dir = tmp_path / "shared"
        for role in self.ALL_CONSULTANT_ROLES:
            agent_dir = squad_dir / "agents" / role
            agent_dir.mkdir(parents=True)
            (agent_dir / "charter.md").write_text(f"You are the {role}.")
            history_dir = shared_dir / "agents" / role
            history_dir.mkdir(parents=True)
            (history_dir / "history.md").write_text(f"## {role} history")
        return tmp_path

    @pytest.fixture
    def full_context_loader(self, full_kb_dir: Path) -> ContextLoader:
        return ContextLoader(shared_dir=str(full_kb_dir / "shared"))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ALL_CONSULTANT_ROLES)
    async def test_all_roles_spawnable(self, full_kb_dir, full_context_loader, role):
        """Each of the 7 roles should be spawnable without error."""
        manager = AgentManager(
            context_loader=full_context_loader,
            charter_dir=full_kb_dir / "squad" / "agents",
        )
        mock_session = _make_mock_session()

        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            return_value=mock_session,
        ):
            result = await manager.spawn_agent(role, f"Hello {role}")

        assert isinstance(result, AgentResult)
        assert role in manager.active_sessions

    @pytest.mark.asyncio
    async def test_concurrent_three_sessions(self, full_kb_dir, full_context_loader):
        """3+ concurrent sessions (engineer + quant + critic) maintained without interference."""
        manager = AgentManager(
            context_loader=full_context_loader,
            charter_dir=full_kb_dir / "squad" / "agents",
        )
        mock_eng = _make_mock_session()
        mock_quant = _make_mock_session()
        mock_critic = _make_mock_session()
        sessions = {"engineer": mock_eng, "quant": mock_quant, "critic": mock_critic}

        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            side_effect=lambda **kw: sessions[kw["role"]],
        ):
            await manager.spawn_agent("engineer", "Design strategy")
            await manager.spawn_agent("quant", "Check costs")
            await manager.spawn_agent("critic", "Challenge design")

        assert len(manager.active_sessions) == 3
        assert set(manager.active_sessions.keys()) == {"engineer", "quant", "critic"}

    @pytest.mark.asyncio
    async def test_concurrent_cost_aggregation(self, full_kb_dir, full_context_loader):
        """Total cost aggregated across all concurrent sessions."""
        manager = AgentManager(
            context_loader=full_context_loader,
            charter_dir=full_kb_dir / "squad" / "agents",
        )
        mock_eng = _make_mock_session()
        mock_eng.total_cost_usd = 0.20
        mock_quant = _make_mock_session()
        mock_quant.total_cost_usd = 0.10
        mock_critic = _make_mock_session()
        mock_critic.total_cost_usd = 0.15
        sessions = {"engineer": mock_eng, "quant": mock_quant, "critic": mock_critic}

        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            side_effect=lambda **kw: sessions[kw["role"]],
        ):
            await manager.spawn_agent("engineer", "Work")
            await manager.spawn_agent("quant", "Costs")
            await manager.spawn_agent("critic", "Challenge")

        assert manager.total_cost_usd == pytest.approx(0.45)

    @pytest.mark.asyncio
    async def test_teardown_all_cleans_concurrent_sessions(
        self, full_kb_dir, full_context_loader
    ):
        """teardown_all stops all concurrent sessions."""
        manager = AgentManager(
            context_loader=full_context_loader,
            charter_dir=full_kb_dir / "squad" / "agents",
        )
        mock_eng = _make_mock_session()
        mock_quant = _make_mock_session()
        mock_critic = _make_mock_session()
        sessions = {"engineer": mock_eng, "quant": mock_quant, "critic": mock_critic}

        with patch(
            "squad_engine.agent_manager.PersistentAgentSession",
            side_effect=lambda **kw: sessions[kw["role"]],
        ):
            await manager.spawn_agent("engineer", "Work")
            await manager.spawn_agent("quant", "Costs")
            await manager.spawn_agent("critic", "Challenge")
            await manager.teardown_all()

        mock_eng.stop.assert_awaited_once()
        mock_quant.stop.assert_awaited_once()
        mock_critic.stop.assert_awaited_once()
        assert len(manager.active_sessions) == 0

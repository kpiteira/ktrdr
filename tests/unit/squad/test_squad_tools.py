"""Tests for squad MCP tool creation."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure .squad/ is on sys.path
_squad_dir = str(Path(__file__).resolve().parents[3] / ".squad")
if _squad_dir not in sys.path:
    sys.path.insert(0, _squad_dir)

from squad_engine.squad_tools import (  # noqa: E402
    ConversationEntry,
    CycleState,
    create_squad_mcp_server,
)

from ktrdr.agents.runtime.protocol import AgentResult  # noqa: E402


class TestCycleState:
    def test_initial_state(self):
        state = CycleState()
        assert state.agents_spawned == []
        assert state.experiment_result is None
        assert state.cadence_next == "full_squad"
        assert state.cycle_complete is False
        assert state.conversation_log == []

    def test_conversation_entry_captures_exchange(self):
        entry = ConversationEntry(
            role="engineer",
            message_to_agent="Design a strategy for EURUSD 1h",
            agent_response="Here's a GRU-based strategy...",
            cost_usd=0.50,
            turns=3,
        )
        assert entry.role == "engineer"
        assert "EURUSD" in entry.message_to_agent
        assert "GRU" in entry.agent_response
        assert entry.cost_usd == 0.50


class TestCreateSquadMcpServer:
    def test_creates_mcp_server(self):
        mock_manager = AsyncMock()
        state = CycleState()

        with patch("squad_engine.session._get_sdk") as mock_sdk_fn:
            mock_sdk = MagicMock()
            # Mock the tool decorator to return a passthrough
            mock_sdk.tool = lambda **kw: lambda fn: fn
            mock_sdk.create_sdk_mcp_server = MagicMock(return_value={"type": "sdk"})
            mock_sdk_fn.return_value = mock_sdk

            create_squad_mcp_server(
                agent_manager=mock_manager,
                cycle_state=state,
            )

        # create_sdk_mcp_server was called with 4 tools
        mock_sdk.create_sdk_mcp_server.assert_called_once()
        call_kwargs = mock_sdk.create_sdk_mcp_server.call_args
        assert call_kwargs[1]["name"] == "squad" or call_kwargs[0][0] == "squad"


# ---------------------------------------------------------------------------
# M2: spawn_agent tool schema lists all 7 roles
# ---------------------------------------------------------------------------


class TestM2SpawnAgentSchema:
    """The spawn_agent tool must advertise all 7 consultant roles."""

    ALL_ROLES = [
        "engineer",
        "quant",
        "inventor",
        "scout",
        "critic",
        "architect",
        "scribe",
    ]

    def test_spawn_agent_schema_includes_all_roles(self):
        """The spawn_agent MCP tool's input_schema should list all 7 roles."""
        mock_manager = AsyncMock()
        state = CycleState()

        captured_schemas = {}

        with patch("squad_engine.session._get_sdk") as mock_sdk_fn:
            mock_sdk = MagicMock()

            def capture_tool(**kw):
                name = kw.get("name", "")
                schema = kw.get("input_schema", {})
                captured_schemas[name] = schema
                return lambda fn: fn

            mock_sdk.tool = capture_tool
            mock_sdk.create_sdk_mcp_server = MagicMock(return_value={"type": "sdk"})
            mock_sdk_fn.return_value = mock_sdk

            create_squad_mcp_server(
                agent_manager=mock_manager,
                cycle_state=state,
            )

        assert "spawn_agent" in captured_schemas
        schema = captured_schemas["spawn_agent"]
        role_enum = schema["properties"]["role"]["enum"]
        for role in self.ALL_ROLES:
            assert role in role_enum, f"Role '{role}' missing from spawn_agent schema"

    def test_spawn_agent_description_mentions_consultants(self):
        """spawn_agent description should mention consultant roles, not just M1 roles."""
        mock_manager = AsyncMock()
        state = CycleState()

        captured_descriptions = {}

        with patch("squad_engine.session._get_sdk") as mock_sdk_fn:
            mock_sdk = MagicMock()

            def capture_tool(**kw):
                name = kw.get("name", "")
                desc = kw.get("description", "")
                captured_descriptions[name] = desc
                return lambda fn: fn

            mock_sdk.tool = capture_tool
            mock_sdk.create_sdk_mcp_server = MagicMock(return_value={"type": "sdk"})
            mock_sdk_fn.return_value = mock_sdk

            create_squad_mcp_server(
                agent_manager=mock_manager,
                cycle_state=state,
            )

        assert "spawn_agent" in captured_descriptions
        desc = captured_descriptions["spawn_agent"]
        # Should mention consultant roles, not be limited to M1's "engineer and scribe"
        assert (
            "quant" in desc.lower()
            or "consultant" in desc.lower()
            or "all" in desc.lower()
        )


# ---------------------------------------------------------------------------
# M3: Debate Depth Control — Turn Pair Tracking + Safety Valve
# ---------------------------------------------------------------------------


class TestM3DebateTurnPairTracking:
    """CycleState tracks debate turn pairs and enforces limits."""

    def test_debate_pairs_initialized_empty(self):
        """Fresh CycleState has empty debate pair tracking."""
        state = CycleState()
        assert state.debate_pairs == {}

    def test_debate_pairs_track_role_pairs(self):
        """record_debate_turn tracks turns between role pairs."""
        state = CycleState()
        state.record_debate_turn("engineer", "critic")
        assert state.debate_pairs[("critic", "engineer")] == 1

    def test_debate_pairs_increment_on_repeated_turn(self):
        """Multiple turns between same pair increment the count."""
        state = CycleState()
        state.record_debate_turn("engineer", "critic")
        state.record_debate_turn("critic", "engineer")
        state.record_debate_turn("engineer", "critic")
        # All three are the same pair (sorted)
        assert state.debate_pairs[("critic", "engineer")] == 3

    def test_debate_pairs_sorted_key(self):
        """Pair key is sorted so (A,B) == (B,A)."""
        state = CycleState()
        state.record_debate_turn("engineer", "critic")
        state.record_debate_turn("critic", "engineer")
        # Only one key, sorted alphabetically
        assert len(state.debate_pairs) == 1
        assert ("critic", "engineer") in state.debate_pairs

    def test_different_pairs_tracked_independently(self):
        """engineer↔critic and engineer↔inventor are separate pairs."""
        state = CycleState()
        state.record_debate_turn("engineer", "critic")
        state.record_debate_turn("engineer", "critic")
        state.record_debate_turn("engineer", "inventor")
        assert state.debate_pairs[("critic", "engineer")] == 2
        assert state.debate_pairs[("engineer", "inventor")] == 1

    def test_is_debate_limit_reached_false_under_limit(self):
        """Under 5 turns: limit not reached."""
        state = CycleState()
        for _ in range(4):
            state.record_debate_turn("engineer", "critic")
        assert not state.is_debate_limit_reached("engineer", "critic")

    def test_is_debate_limit_reached_true_at_limit(self):
        """At 5 turns: limit reached."""
        state = CycleState()
        for _ in range(5):
            state.record_debate_turn("engineer", "critic")
        assert state.is_debate_limit_reached("engineer", "critic")

    def test_is_debate_limit_reached_false_for_untracked_pair(self):
        """Pair with no turns: limit not reached."""
        state = CycleState()
        assert not state.is_debate_limit_reached("engineer", "architect")


class TestM3DebateMetadata:
    """CycleState tracks debate metadata for CycleResult."""

    def test_debates_list_initialized_empty(self):
        """Fresh CycleState has empty debates list."""
        state = CycleState()
        assert state.debates == []

    def test_record_debate_adds_metadata(self):
        """record_debate stores structured debate metadata."""
        state = CycleState()
        state.record_debate(
            roles=["engineer", "critic"],
            turns=3,
            revised=True,
            resolution="Engineer removed 4 correlated features",
        )
        assert len(state.debates) == 1
        debate = state.debates[0]
        assert debate["roles"] == ["engineer", "critic"]
        assert debate["turns"] == 3
        assert debate["revised"] is True
        assert "correlated features" in debate["resolution"]

    def test_multiple_debates_recorded(self):
        """Multiple debates in one cycle are all recorded."""
        state = CycleState()
        state.record_debate(
            roles=["engineer", "critic"],
            turns=3,
            revised=True,
            resolution="Feature count reduced",
        )
        state.record_debate(
            roles=["engineer", "inventor"],
            turns=2,
            revised=False,
            resolution="Kept original approach — inventor's idea deferred to future cycle",
        )
        assert len(state.debates) == 2


# ---------------------------------------------------------------------------
# M3: spawn_agent Debate Enforcement
# ---------------------------------------------------------------------------


class TestM3SpawnAgentDebateEnforcement:
    """spawn_agent tool tracks debate turns and enforces the 5-turn limit."""

    def _make_tool_handler(self, mock_manager, cycle_state):
        """Create the spawn_agent tool handler via create_squad_mcp_server."""
        captured_handlers = {}

        with patch("squad_engine.session._get_sdk") as mock_sdk_fn:
            mock_sdk = MagicMock()

            def capture_tool(**kw):
                name = kw.get("name", "")

                def decorator(fn):
                    captured_handlers[name] = fn
                    return fn

                return decorator

            mock_sdk.tool = capture_tool
            mock_sdk.create_sdk_mcp_server = MagicMock(return_value={"type": "sdk"})
            mock_sdk_fn.return_value = mock_sdk

            create_squad_mcp_server(
                agent_manager=mock_manager,
                cycle_state=cycle_state,
            )

        return captured_handlers.get("spawn_agent")

    def _make_mock_manager(self):
        mock = AsyncMock()
        mock.spawn_agent = AsyncMock(
            return_value=AgentResult(
                output="Response from agent.",
                cost_usd=0.05,
                turns=1,
                transcript=[],
                session_id="sess_1",
            )
        )
        return mock

    @pytest.mark.asyncio
    async def test_consecutive_different_roles_records_debate_turn(self):
        """Spawning role B after role A records a debate turn for that pair."""
        state = CycleState()
        mock_manager = self._make_mock_manager()
        handler = self._make_tool_handler(mock_manager, state)

        await handler({"role": "engineer", "message": "Design strategy"})
        await handler({"role": "critic", "message": "Challenge it"})

        assert state.debate_pairs.get(("critic", "engineer"), 0) == 1

    @pytest.mark.asyncio
    async def test_same_role_twice_no_debate_turn(self):
        """Spawning the same role twice doesn't create a debate turn."""
        state = CycleState()
        mock_manager = self._make_mock_manager()
        handler = self._make_tool_handler(mock_manager, state)

        await handler({"role": "engineer", "message": "First"})
        await handler({"role": "engineer", "message": "Second"})

        assert state.debate_pairs == {}

    @pytest.mark.asyncio
    async def test_debate_limit_returns_message_instead_of_spawning(self):
        """After 5 turns, spawn_agent returns a limit message without calling the agent."""
        state = CycleState()
        mock_manager = self._make_mock_manager()
        handler = self._make_tool_handler(mock_manager, state)

        # Simulate 5 turns of engineer↔critic debate
        for _ in range(5):
            state.record_debate_turn("engineer", "critic")

        # Set last_spawned_role so the next spawn triggers the pair check
        state.last_spawned_role = "engineer"

        result = await handler({"role": "critic", "message": "One more challenge"})

        # Should return limit message, NOT call the agent
        assert "limit" in result["output"].lower() or "5" in result["output"]
        # spawn_agent should NOT have been called for the limited pair
        # (it was called 0 times because we set up debate_pairs manually)
        mock_manager.spawn_agent.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_debate_limit_only_affects_limited_pair(self):
        """Limit on engineer↔critic doesn't block engineer↔inventor."""
        state = CycleState()
        mock_manager = self._make_mock_manager()
        handler = self._make_tool_handler(mock_manager, state)

        # Max out engineer↔critic
        for _ in range(5):
            state.record_debate_turn("engineer", "critic")

        # Spawn inventor after engineer — different pair, should work
        state.last_spawned_role = "engineer"
        result = await handler({"role": "inventor", "message": "New ideas"})

        assert result["output"] == "Response from agent."
        mock_manager.spawn_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_last_spawned_role_tracked(self):
        """CycleState.last_spawned_role updated after each spawn."""
        state = CycleState()
        mock_manager = self._make_mock_manager()
        handler = self._make_tool_handler(mock_manager, state)

        assert state.last_spawned_role is None
        await handler({"role": "engineer", "message": "Hello"})
        assert state.last_spawned_role == "engineer"
        await handler({"role": "critic", "message": "Challenge"})
        assert state.last_spawned_role == "critic"

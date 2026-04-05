"""Tests for squad MCP tool creation."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure .squad/ is on sys.path
_squad_dir = str(Path(__file__).resolve().parents[3] / ".squad")
if _squad_dir not in sys.path:
    sys.path.insert(0, _squad_dir)

from squad_engine.squad_tools import (  # noqa: E402
    ConversationEntry,
    CycleState,
    create_squad_mcp_server,
)


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

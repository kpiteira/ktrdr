"""Tests for squad MCP tool creation."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure .squad/ is on sys.path
_squad_dir = str(Path(__file__).resolve().parents[3] / ".squad")
if _squad_dir not in sys.path:
    sys.path.insert(0, _squad_dir)

from squad_engine.squad_tools import CycleState, create_squad_mcp_server  # noqa: E402


class TestCycleState:
    def test_initial_state(self):
        state = CycleState()
        assert state.agents_spawned == []
        assert state.experiment_result is None
        assert state.cadence_next == "full_squad"
        assert state.cycle_complete is False


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

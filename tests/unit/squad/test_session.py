"""Tests for PersistentAgentSession — multi-turn wrapper over claude_agent_sdk."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure .squad/ is on sys.path for orchestrator imports
_squad_dir = str(Path(__file__).resolve().parents[3] / ".squad")
if _squad_dir not in sys.path:
    sys.path.insert(0, _squad_dir)

from squad_engine.session import PersistentAgentSession  # noqa: E402

from ktrdr.agents.runtime.protocol import AgentResult  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CHARTER_TEXT = "You are the Engineer. You design strategies."
HISTORY_TEXT = "## Cycle 1\nLearned that RSI alone plateaus at 64%."


@pytest.fixture
def charter_file(tmp_path: Path) -> Path:
    p = tmp_path / "charter.md"
    p.write_text(CHARTER_TEXT)
    return p


@pytest.fixture
def history_file(tmp_path: Path) -> Path:
    p = tmp_path / "history.md"
    p.write_text(HISTORY_TEXT)
    return p


def _make_mock_sdk():
    """Create a mock SDK module with all required message types."""
    sdk = MagicMock()
    sdk.ResultMessage = type("ResultMessage", (), {})
    sdk.AssistantMessage = type("AssistantMessage", (), {})
    sdk.TextBlock = type("TextBlock", (), {})
    sdk.ToolUseBlock = type("ToolUseBlock", (), {})
    return sdk


def _make_result_msg(sdk, output="Strategy YAML written to file.", cost=0.05, turns=1):
    """Create a mock ResultMessage."""
    msg = MagicMock(spec=sdk.ResultMessage)
    # Make isinstance check work
    msg.__class__ = sdk.ResultMessage
    msg.session_id = "sess_123"
    msg.total_cost_usd = cost
    msg.num_turns = turns
    msg.result = output
    return msg


@pytest.fixture
def mock_session_env():
    """Set up a mock environment for PersistentAgentSession.

    Mocks both _create_client (to avoid real SDK client creation)
    and _get_sdk (to avoid real SDK import in _collect_response).
    """
    sdk = _make_mock_sdk()
    result_msg = _make_result_msg(sdk)

    client = AsyncMock()
    client.connect = AsyncMock()
    client.query = AsyncMock()
    client.disconnect = AsyncMock()

    async def mock_receive():
        yield result_msg

    client.receive_response = mock_receive

    return client, sdk, result_msg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPersistentAgentSession:
    """Unit tests for PersistentAgentSession."""

    def test_init_sets_role_and_paths(self, charter_file: Path):
        session = PersistentAgentSession(
            role="engineer",
            charter_path=charter_file,
        )
        assert session.role == "engineer"
        assert not session.is_alive
        assert session.total_cost_usd == 0.0
        assert session.total_turns == 0

    @pytest.mark.asyncio
    async def test_start_connects_and_sends_charter(
        self, charter_file: Path, history_file: Path, mock_session_env
    ):
        client, sdk, _ = mock_session_env
        session = PersistentAgentSession(
            role="engineer",
            charter_path=charter_file,
            history_path=history_file,
        )

        with (
            patch.object(session, "_create_client", return_value=client),
            patch("squad_engine.session._get_sdk", return_value=sdk),
        ):
            await session.start()

        # connect() called with no args (spike gotcha)
        client.connect.assert_awaited_once_with()
        assert session.is_alive

    @pytest.mark.asyncio
    async def test_query_returns_agent_result(
        self, charter_file: Path, mock_session_env
    ):
        client, sdk, _ = mock_session_env
        session = PersistentAgentSession(
            role="engineer",
            charter_path=charter_file,
        )

        with (
            patch.object(session, "_create_client", return_value=client),
            patch("squad_engine.session._get_sdk", return_value=sdk),
        ):
            await session.start()
            result = await session.query("Design a strategy for EURUSD 5m")

        assert isinstance(result, AgentResult)
        assert result.output == "Strategy YAML written to file."
        assert result.cost_usd == 0.05
        assert result.turns == 1
        assert result.session_id == "sess_123"

    @pytest.mark.asyncio
    async def test_multiple_queries_accumulate_cost_and_turns(
        self, charter_file: Path, mock_session_env
    ):
        client, sdk, _ = mock_session_env
        session = PersistentAgentSession(
            role="engineer",
            charter_path=charter_file,
        )

        with (
            patch.object(session, "_create_client", return_value=client),
            patch("squad_engine.session._get_sdk", return_value=sdk),
        ):
            await session.start()
            await session.query("First message")
            await session.query("Second message")

        # start() consumes 1 response (0.05) + 2 queries (0.05 each) = 0.15
        assert session.total_cost_usd == pytest.approx(0.15)
        # start() counts 1 turn + 2 query turns = 3
        assert session.total_turns == 3

    @pytest.mark.asyncio
    async def test_stop_handles_cancelled_error(
        self, charter_file: Path, mock_session_env
    ):
        """disconnect() throws CancelledError — must be handled gracefully."""
        client, sdk, _ = mock_session_env
        client.disconnect = AsyncMock(side_effect=asyncio.CancelledError())
        session = PersistentAgentSession(
            role="engineer",
            charter_path=charter_file,
        )

        with (
            patch.object(session, "_create_client", return_value=client),
            patch("squad_engine.session._get_sdk", return_value=sdk),
        ):
            await session.start()
            # Should not raise
            await session.stop()

        assert not session.is_alive

    @pytest.mark.asyncio
    async def test_claudecode_env_var_managed(
        self, charter_file: Path, mock_session_env
    ):
        """CLAUDECODE env var must be removed during session, restored after."""
        client, sdk, _ = mock_session_env
        session = PersistentAgentSession(
            role="engineer",
            charter_path=charter_file,
        )

        os.environ["CLAUDECODE"] = "original_value"
        try:
            with (
                patch.object(session, "_create_client", return_value=client),
                patch("squad_engine.session._get_sdk", return_value=sdk),
            ):
                await session.start()
                # During session, CLAUDECODE should be removed
                assert "CLAUDECODE" not in os.environ
                await session.stop()
            # After stop, CLAUDECODE should be restored
            assert os.environ.get("CLAUDECODE") == "original_value"
        finally:
            os.environ.pop("CLAUDECODE", None)

    @pytest.mark.asyncio
    async def test_is_alive_reflects_state(
        self, charter_file: Path, mock_session_env
    ):
        client, sdk, _ = mock_session_env
        session = PersistentAgentSession(
            role="engineer",
            charter_path=charter_file,
        )

        assert not session.is_alive

        with (
            patch.object(session, "_create_client", return_value=client),
            patch("squad_engine.session._get_sdk", return_value=sdk),
        ):
            await session.start()
            assert session.is_alive
            await session.stop()

        assert not session.is_alive

    @pytest.mark.asyncio
    async def test_context_files_included_in_initial_message(
        self, charter_file: Path, history_file: Path, mock_session_env, tmp_path: Path
    ):
        """Context files should be loaded and sent in the initial system setup."""
        client, sdk, _ = mock_session_env

        # Create a context file
        ctx_file = tmp_path / "synthesis.md"
        ctx_file.write_text("## Synthesis\nStandard indicators exhausted.")

        session = PersistentAgentSession(
            role="engineer",
            charter_path=charter_file,
            history_path=history_file,
        )

        with (
            patch.object(session, "_create_client", return_value=client),
            patch("squad_engine.session._get_sdk", return_value=sdk),
        ):
            await session.start(context_files=[str(ctx_file)])

        # The initial query after connect should include charter + history + context
        client.query.assert_called()
        initial_msg = client.query.call_args[0][0]
        assert CHARTER_TEXT in initial_msg
        assert HISTORY_TEXT in initial_msg
        assert "Standard indicators exhausted" in initial_msg

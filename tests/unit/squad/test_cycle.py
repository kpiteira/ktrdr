"""Tests for Director system prompt assembly and cycle loop."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Ensure .squad/ is on sys.path
_squad_dir = str(Path(__file__).resolve().parents[3] / ".squad")
if _squad_dir not in sys.path:
    sys.path.insert(0, _squad_dir)

from squad_engine.director_prompt import build_director_prompt  # noqa: E402
from squad_engine.loop import CycleResult, run_cycle  # noqa: E402

from ktrdr.agents.runtime.protocol import AgentResult  # noqa: E402

# ---------------------------------------------------------------------------
# Director Prompt Tests
# ---------------------------------------------------------------------------


class TestDirectorPrompt:
    def test_includes_tool_descriptions(self, tmp_path: Path):
        charter = tmp_path / "charter.md"
        charter.write_text("You are the Director.")
        prompt = build_director_prompt(
            charter_path=charter,
            iteration=1,
            cadence="full_squad",
            nudges="",
        )
        assert "spawn_agent" in prompt
        assert "validate_strategy" in prompt
        assert "execute_experiment" in prompt

    def test_includes_cycle_context(self, tmp_path: Path):
        charter = tmp_path / "charter.md"
        charter.write_text("You are the Director.")
        prompt = build_director_prompt(
            charter_path=charter,
            iteration=5,
            cadence="quick_iteration",
            nudges="Focus on 5m EURUSD",
        )
        assert "Cycle 5" in prompt
        assert "quick_iteration" in prompt
        assert "Focus on 5m EURUSD" in prompt

    def test_includes_kb_file_map(self, tmp_path: Path):
        charter = tmp_path / "charter.md"
        charter.write_text("You are the Director.")
        prompt = build_director_prompt(
            charter_path=charter,
            iteration=1,
            cadence="full_squad",
            nudges="",
        )
        assert "experiments.md" in prompt
        assert "synthesis.md" in prompt
        assert "frontiers.md" in prompt

    def test_instructs_delegation(self, tmp_path: Path):
        charter = tmp_path / "charter.md"
        charter.write_text("You are the Director.")
        prompt = build_director_prompt(
            charter_path=charter,
            iteration=1,
            cadence="full_squad",
            nudges="",
        )
        assert "Engineer" in prompt
        assert "Scribe" in prompt
        assert "Do NOT design strategies" in prompt


# ---------------------------------------------------------------------------
# Cycle Loop Tests
# ---------------------------------------------------------------------------


class TestRunCycle:
    @pytest.mark.asyncio
    async def test_cycle_returns_result(self, tmp_path: Path):
        """Mock Director to verify CycleResult structure."""
        shared_dir = tmp_path / "shared"
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "synthesis.md").write_text("Patterns.")
        (shared_dir / "knowledge" / "experiments.md").write_text("No experiments.")
        (shared_dir / "knowledge" / "frontiers.md").write_text("F1 active.")
        (shared_dir / "loop").mkdir()
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad")
        (shared_dir / "loop" / "nudges.md").write_text("")
        for role in ("engineer", "scribe", "director"):
            d = shared_dir / "agents" / role
            d.mkdir(parents=True)
            (d / "history.md").write_text("")

        charter_dir = tmp_path / "charters"
        for role in ("engineer", "scribe", "director"):
            d = charter_dir / role
            d.mkdir(parents=True)
            (d / "charter.md").write_text(f"You are the {role}.")

        mock_director_result = AgentResult(
            output="CYCLE_COMPLETE",
            cost_usd=0.50,
            turns=5,
            transcript=[],
            session_id="dir_sess",
        )

        mock_agent_manager = AsyncMock()
        mock_agent_manager.spawn_agent = AsyncMock(
            return_value=AgentResult(
                output="Done.",
                cost_usd=0.05,
                turns=1,
                transcript=[],
            )
        )
        mock_agent_manager.teardown_all = AsyncMock()
        mock_agent_manager.total_cost_usd = 0.10

        result = await run_cycle(
            iteration=1,
            shared_dir=str(shared_dir),
            charter_dir=str(charter_dir),
            _agent_manager=mock_agent_manager,
            _director_response=mock_director_result,
        )

        assert isinstance(result, CycleResult)
        assert result.iteration == 1
        mock_agent_manager.teardown_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cycle_cost_is_additive(self, tmp_path: Path):
        """Director cost + agent_manager cost should both be included."""
        shared_dir = tmp_path / "shared"
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "synthesis.md").write_text("")
        (shared_dir / "knowledge" / "experiments.md").write_text("")
        (shared_dir / "knowledge" / "frontiers.md").write_text("")
        (shared_dir / "loop").mkdir()
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad")
        (shared_dir / "loop" / "nudges.md").write_text("")
        for role in ("engineer", "scribe", "director"):
            d = shared_dir / "agents" / role
            d.mkdir(parents=True)
            (d / "history.md").write_text("")

        charter_dir = tmp_path / "charters"
        for role in ("engineer", "scribe", "director"):
            d = charter_dir / role
            d.mkdir(parents=True)
            (d / "charter.md").write_text(f"You are the {role}.")

        mock_director_result = AgentResult(
            output="CYCLE_COMPLETE",
            cost_usd=0.30,
            turns=3,
            transcript=[],
        )

        mock_agent_manager = AsyncMock()
        mock_agent_manager.teardown_all = AsyncMock()
        mock_agent_manager.total_cost_usd = 0.10

        result = await run_cycle(
            iteration=3,
            shared_dir=str(shared_dir),
            charter_dir=str(charter_dir),
            _agent_manager=mock_agent_manager,
            _director_response=mock_director_result,
        )

        # Director cost (0.30) + agent_manager cost (0.10) = 0.40
        assert result.total_cost_usd == pytest.approx(0.40)

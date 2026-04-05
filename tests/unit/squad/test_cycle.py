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
from squad_engine.loop import (  # noqa: E402
    CycleResult,
    _write_conversation_log,
    run_cycle,
)
from squad_engine.squad_tools import ConversationEntry  # noqa: E402

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


# ---------------------------------------------------------------------------
# M2: Context Routing Guidance
# ---------------------------------------------------------------------------


class TestM2ContextRouting:
    """Director prompt should include context routing guidance for each role."""

    def test_prompt_includes_context_routing_table(self, tmp_path: Path):
        """Director prompt must have a context routing guidance section."""
        charter = tmp_path / "charter.md"
        charter.write_text("You are the Director.")
        prompt = build_director_prompt(
            charter_path=charter,
            iteration=1,
            cadence="full_squad",
            nudges="",
        )
        assert "Context Routing" in prompt or "context routing" in prompt.lower()

    def test_prompt_context_routing_mentions_all_consultant_roles(self, tmp_path: Path):
        """Context routing guidance should mention what each consultant typically needs."""
        charter = tmp_path / "charter.md"
        charter.write_text("You are the Director.")
        prompt = build_director_prompt(
            charter_path=charter,
            iteration=1,
            cadence="full_squad",
            nudges="",
        )
        prompt_lower = prompt.lower()
        for role in [
            "engineer",
            "quant",
            "inventor",
            "scout",
            "critic",
            "architect",
            "scribe",
        ]:
            assert role in prompt_lower, f"Context routing should mention {role}"

    def test_prompt_context_routing_mentions_key_files(self, tmp_path: Path):
        """Routing guidance should reference key KB files like synthesis.md, frontiers.md."""
        charter = tmp_path / "charter.md"
        charter.write_text("You are the Director.")
        prompt = build_director_prompt(
            charter_path=charter,
            iteration=1,
            cadence="full_squad",
            nudges="",
        )
        assert "synthesis.md" in prompt
        assert "frontiers.md" in prompt
        assert "components.md" in prompt

    def test_context_routing_is_guidance_not_enforcement(self, tmp_path: Path):
        """Routing table should be framed as suggestions, not hard rules."""
        charter = tmp_path / "charter.md"
        charter.write_text("You are the Director.")
        prompt = build_director_prompt(
            charter_path=charter,
            iteration=1,
            cadence="full_squad",
            nudges="",
        )
        prompt_lower = prompt.lower()
        assert (
            "suggestion" in prompt_lower
            or "guidance" in prompt_lower
            or "typical" in prompt_lower
        )


# ---------------------------------------------------------------------------
# M2: Consultant Selection Triggers + Cadence Adaptation
# ---------------------------------------------------------------------------


class TestM2ConsultantTriggers:
    """Director prompt should include when to consult each agent and cadence adaptation."""

    def _build_prompt(self, tmp_path, cadence="full_squad"):
        charter = tmp_path / "charter.md"
        charter.write_text("You are the Director.")
        return build_director_prompt(
            charter_path=charter,
            iteration=1,
            cadence=cadence,
            nudges="",
        )

    def test_prompt_has_dedicated_consultation_section(self, tmp_path: Path):
        """Prompt should have a dedicated 'When to Consult' section with per-agent triggers."""
        prompt = self._build_prompt(tmp_path)
        # Must be a dedicated section, not just mentions in tool descriptions
        assert "When to Consult" in prompt or "Consultant Selection" in prompt

    def test_prompt_consultant_triggers_are_specific(self, tmp_path: Path):
        """Each consultant trigger should describe specific conditions."""
        prompt = self._build_prompt(tmp_path)
        # Quant trigger: cost/profitability evaluation
        assert "profitability" in prompt.lower() or "cost" in prompt.lower()
        # Inventor trigger: frontier exhausted, diminishing returns
        assert (
            "exhausted" in prompt.lower()
            or "diminishing" in prompt.lower()
            or "incrementalism" in prompt.lower()
        )
        # Scout trigger: new frontier, external techniques
        assert "external" in prompt.lower() or "outside" in prompt.lower()
        # Critic trigger: before/after execution
        assert "before execution" in prompt.lower() or "challenge" in prompt.lower()
        # Architect trigger: capability gap
        assert "gap" in prompt.lower() or "infrastructure" in prompt.lower()

    def test_prompt_has_relay_pattern_section(self, tmp_path: Path):
        """Prompt should have relay guidance with good vs bad example patterns."""
        prompt = self._build_prompt(tmp_path)
        # Should have a dedicated relay section with examples
        assert "Relay" in prompt or "relay" in prompt
        # Should show contrasting good/bad patterns
        assert (
            "Bad:" in prompt
            or "bad:" in prompt
            or "Don't:" in prompt
            or "Instead:" in prompt
        )

    def test_prompt_adapts_work_section_to_quick_iteration(self, tmp_path: Path):
        """quick_iteration cadence should instruct Director to use fewer agents."""
        full_prompt = self._build_prompt(tmp_path, cadence="full_squad")
        quick_prompt = self._build_prompt(tmp_path, cadence="quick_iteration")
        # The prompts should differ in their task/work instructions
        assert full_prompt != quick_prompt
        # Quick iteration should mention restriction
        assert "quick_iteration" in quick_prompt
        quick_lower = quick_prompt.lower()
        assert (
            "engineer only" in quick_lower
            or "skip consult" in quick_lower
            or "minor variant" in quick_lower
        )

    def test_prompt_adapts_work_section_to_full_squad(self, tmp_path: Path):
        """full_squad cadence should include all consultant triggers."""
        prompt = self._build_prompt(tmp_path, cadence="full_squad")
        prompt_lower = prompt.lower()
        for role in ["quant", "inventor", "scout", "critic", "architect"]:
            assert (
                role in prompt_lower
            ), f"{role} should be mentioned in full_squad prompt"

    def test_prompt_within_token_budget(self, tmp_path: Path):
        """Assembled prompt should stay within reasonable token budget."""
        prompt = self._build_prompt(tmp_path)
        estimated_tokens = len(prompt) // 4
        assert estimated_tokens < 4000, f"Prompt too large: ~{estimated_tokens} tokens"

    def test_prompt_when_not_to_consult(self, tmp_path: Path):
        """Prompt should have specific guidance on when NOT to consult."""
        prompt = self._build_prompt(tmp_path)
        prompt_lower = prompt.lower()
        # Should mention synthesis cadence (Director + Scribe only)
        assert "synthesis" in prompt_lower
        # Should mention quick_iteration restriction
        assert "quick_iteration" in prompt_lower


# ---------------------------------------------------------------------------
# M2: Conversation Log
# ---------------------------------------------------------------------------


class TestM2ConversationLog:
    """Conversation log captures full Director-agent exchanges for review."""

    def test_write_conversation_log_creates_file(self, tmp_path: Path):
        """_write_conversation_log writes a readable markdown file."""
        result = CycleResult(
            iteration=42,
            status="COMPLETE",
            total_cost_usd=3.50,
            agents_spawned=["engineer", "quant"],
            cadence_next="quick_iteration",
            duration_seconds=120.5,
            conversation_log=[
                ConversationEntry(
                    role="engineer",
                    message_to_agent="Design a GRU strategy for EURUSD 1h",
                    agent_response="Here's the strategy YAML with MACD features...",
                    cost_usd=1.20,
                    turns=5,
                ),
                ConversationEntry(
                    role="quant",
                    message_to_agent="Check cost viability of 5m EURUSD",
                    agent_response="Spread cost is $1.20/trade, need >$2/trade profit",
                    cost_usd=0.80,
                    turns=2,
                ),
            ],
            director_transcript=[
                {"role": "assistant", "type": "text", "content": "Reading KB state..."},
                {"role": "assistant", "type": "tool_use", "tool": "spawn_agent",
                 "input": {"role": "engineer", "message": "Design a GRU strategy"}, "id": "t1"},
                {"role": "assistant", "type": "text", "content": "Engineer produced a design. Checking costs."},
                {"role": "assistant", "type": "tool_use", "tool": "spawn_agent",
                 "input": {"role": "quant", "message": "Check costs"}, "id": "t2"},
            ],
        )

        _write_conversation_log(result, tmp_path)

        log_path = tmp_path / "logs" / "cycle_42_conversation.md"
        assert log_path.exists()

        content = log_path.read_text()
        assert "Cycle 42" in content
        assert "COMPLETE" in content
        assert "$3.5000" in content
        assert "engineer, quant" in content

    def test_conversation_log_includes_agent_exchanges(self, tmp_path: Path):
        """Log should include the full message-to-agent and agent-response."""
        result = CycleResult(
            iteration=1,
            conversation_log=[
                ConversationEntry(
                    role="critic",
                    message_to_agent="Challenge this RSI strategy design",
                    agent_response="The RSI period is too short for 1h data",
                    cost_usd=0.50,
                    turns=1,
                ),
            ],
        )

        _write_conversation_log(result, tmp_path)
        content = (tmp_path / "logs" / "cycle_1_conversation.md").read_text()

        assert "CRITIC" in content
        assert "Challenge this RSI strategy design" in content
        assert "RSI period is too short" in content

    def test_conversation_log_includes_director_reasoning(self, tmp_path: Path):
        """Log should include the Director's own text reasoning."""
        result = CycleResult(
            iteration=1,
            director_transcript=[
                {"role": "assistant", "type": "text",
                 "content": "Frontiers show 5m EURUSD is promising but costly. I'll consult Quant first."},
            ],
        )

        _write_conversation_log(result, tmp_path)
        content = (tmp_path / "logs" / "cycle_1_conversation.md").read_text()

        assert "Director's Reasoning" in content
        assert "5m EURUSD is promising" in content

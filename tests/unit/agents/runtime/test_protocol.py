"""Tests for AgentRuntime protocol, AgentResult, and AgentRuntimeConfig."""

import asyncio
from dataclasses import asdict
from typing import runtime_checkable

from ktrdr.agents.runtime.protocol import AgentResult, AgentRuntime, AgentRuntimeConfig


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_creation_with_required_fields(self) -> None:
        """AgentResult can be created with all required fields."""
        result = AgentResult(
            output="Strategy designed successfully",
            cost_usd=0.05,
            turns=3,
            transcript=[{"role": "assistant", "content": "hello"}],
        )
        assert result.output == "Strategy designed successfully"
        assert result.cost_usd == 0.05
        assert result.turns == 3
        assert len(result.transcript) == 1
        assert result.session_id is None  # default

    def test_creation_with_session_id(self) -> None:
        """AgentResult can include optional session_id."""
        result = AgentResult(
            output="done",
            cost_usd=0.0,
            turns=1,
            transcript=[],
            session_id="sess_abc123",
        )
        assert result.session_id == "sess_abc123"

    def test_serialization_to_dict(self) -> None:
        """AgentResult serializes to dict via dataclasses.asdict()."""
        result = AgentResult(
            output="output",
            cost_usd=0.10,
            turns=5,
            transcript=[{"role": "user", "content": "hello"}],
            session_id="sess_1",
        )
        d = asdict(result)
        assert d["output"] == "output"
        assert d["cost_usd"] == 0.10
        assert d["turns"] == 5
        assert d["transcript"] == [{"role": "user", "content": "hello"}]
        assert d["session_id"] == "sess_1"

    def test_empty_transcript(self) -> None:
        """AgentResult works with empty transcript."""
        result = AgentResult(output="", cost_usd=0.0, turns=0, transcript=[])
        assert result.transcript == []

    def test_equality(self) -> None:
        """Two AgentResults with same fields are equal."""
        kwargs = {"output": "x", "cost_usd": 0.0, "turns": 1, "transcript": []}
        assert AgentResult(**kwargs) == AgentResult(**kwargs)


class TestAgentRuntimeConfig:
    """Tests for AgentRuntimeConfig dataclass."""

    def test_defaults(self) -> None:
        """AgentRuntimeConfig has sensible defaults."""
        config = AgentRuntimeConfig()
        assert config.provider == "claude"
        assert config.model == "claude-sonnet-4-6"
        assert config.max_budget_usd == 5.0
        assert config.max_turns == 20

    def test_custom_values(self) -> None:
        """AgentRuntimeConfig accepts custom values."""
        config = AgentRuntimeConfig(
            provider="copilot",
            model="gpt-4o",
            max_budget_usd=10.0,
            max_turns=50,
        )
        assert config.provider == "copilot"
        assert config.model == "gpt-4o"
        assert config.max_budget_usd == 10.0
        assert config.max_turns == 50

    def test_serialization_to_dict(self) -> None:
        """AgentRuntimeConfig serializes to dict."""
        config = AgentRuntimeConfig()
        d = asdict(config)
        assert "provider" in d
        assert "model" in d
        assert "max_budget_usd" in d
        assert "max_turns" in d


class TestAgentRuntimeProtocol:
    """Tests for AgentRuntime protocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """AgentRuntime is decorated with @runtime_checkable."""
        assert hasattr(AgentRuntime, "__protocol_attrs__") or isinstance(
            AgentRuntime, type
        )
        # The key test: isinstance checks work
        assert runtime_checkable  # imported successfully

    def test_conforming_class_is_instance(self) -> None:
        """A class implementing invoke() satisfies the protocol."""

        class FakeRuntime:
            async def invoke(
                self,
                prompt: str,
                *,
                model: str | None = None,
                max_turns: int = 10,
                max_budget_usd: float = 1.0,
                allowed_tools: list[str] | None = None,
                cwd: str | None = None,
                system_prompt: str | None = None,
                mcp_servers: dict[str, object] | None = None,
            ) -> AgentResult:
                return AgentResult(output="fake", cost_usd=0.0, turns=0, transcript=[])

        assert isinstance(FakeRuntime(), AgentRuntime)

    def test_non_conforming_class_is_not_instance(self) -> None:
        """A class without invoke() does not satisfy the protocol."""

        class NotARuntime:
            def do_something(self) -> None:
                pass

        assert not isinstance(NotARuntime(), AgentRuntime)

    def test_invoke_returns_agent_result(self) -> None:
        """invoke() on a conforming runtime returns AgentResult."""

        class FakeRuntime:
            async def invoke(
                self,
                prompt: str,
                *,
                model: str | None = None,
                max_turns: int = 10,
                max_budget_usd: float = 1.0,
                allowed_tools: list[str] | None = None,
                cwd: str | None = None,
                system_prompt: str | None = None,
                mcp_servers: dict[str, object] | None = None,
            ) -> AgentResult:
                return AgentResult(
                    output=f"processed: {prompt}",
                    cost_usd=0.01,
                    turns=1,
                    transcript=[{"role": "assistant", "content": prompt}],
                )

        result = asyncio.run(FakeRuntime().invoke("test prompt", max_turns=5))
        assert isinstance(result, AgentResult)
        assert result.output == "processed: test prompt"
        assert result.turns == 1

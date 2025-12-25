"""Tests for consolidated runner module.

Tests verify that task execution functions work correctly after
being moved from task_runner.py to runner.py (M4 consolidation).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.config import OrchestratorConfig
from orchestrator.haiku_brain import InterpretationResult
from orchestrator.models import ClaudeResult, Task


def make_task(task_id: str = "2.1", title: str = "Test Task") -> Task:
    """Create a test Task."""
    return Task(
        id=task_id,
        title=title,
        description="Test description",
        file_path="test.py",
        acceptance_criteria=["Criterion 1"],
        plan_file="docs/plan.md",
        milestone_id="M2",
    )


def make_claude_result(
    result: str = "Task completed",
    is_error: bool = False,
    cost: float = 0.05,
    duration_ms: int = 60000,
    num_turns: int = 5,
) -> ClaudeResult:
    """Create a test ClaudeResult."""
    return ClaudeResult(
        is_error=is_error,
        result=result,
        total_cost_usd=cost,
        duration_ms=duration_ms,
        num_turns=num_turns,
        session_id="test-session-123",
    )


def make_interpretation_result(
    status: str = "completed",
    summary: str = "Task finished",
    error: str | None = None,
    question: str | None = None,
    options: list[str] | None = None,
    recommendation: str | None = None,
) -> InterpretationResult:
    """Create a test InterpretationResult."""
    return InterpretationResult(
        status=status,
        summary=summary,
        error=error,
        question=question,
        options=options,
        recommendation=recommendation,
    )


class TestRunnerModuleExports:
    """Test that runner module exports the required functions."""

    def test_run_task_is_exported(self):
        """run_task should be importable from runner."""
        from orchestrator.runner import run_task

        assert callable(run_task)

    def test_run_task_with_escalation_is_exported(self):
        """run_task_with_escalation should be importable from runner."""
        from orchestrator.runner import run_task_with_escalation

        assert callable(run_task_with_escalation)

    def test_build_prompt_helper_is_exported(self):
        """_build_prompt should be importable from runner."""
        from orchestrator.runner import _build_prompt

        assert callable(_build_prompt)

    def test_estimate_tokens_helper_is_exported(self):
        """_estimate_tokens should be importable from runner."""
        from orchestrator.runner import _estimate_tokens

        assert callable(_estimate_tokens)


class TestBuildPrompt:
    """Test prompt construction function."""

    def test_includes_task_id(self):
        """Prompt should include task ID."""
        from orchestrator.runner import _build_prompt

        task = make_task(task_id="3.5")
        prompt = _build_prompt(task, "docs/plan.md")
        assert "3.5" in prompt

    def test_includes_plan_path(self):
        """Prompt should include plan path."""
        from orchestrator.runner import _build_prompt

        task = make_task()
        prompt = _build_prompt(task, "docs/my-plan.md")
        assert "docs/my-plan.md" in prompt

    def test_uses_ktask_format(self):
        """Prompt should use /ktask format."""
        from orchestrator.runner import _build_prompt

        task = make_task(task_id="4.1")
        prompt = _build_prompt(task, "docs/plan.md")
        assert "/ktask" in prompt
        assert "impl:" in prompt
        assert "task:" in prompt

    def test_includes_human_guidance_when_provided(self):
        """Prompt should include human guidance when provided."""
        from orchestrator.runner import _build_prompt

        task = make_task()
        prompt = _build_prompt(task, "docs/plan.md", human_guidance="Use option A")
        assert "Use option A" in prompt
        assert "guidance" in prompt.lower()

    def test_no_guidance_when_none(self):
        """Prompt should not mention guidance when None."""
        from orchestrator.runner import _build_prompt

        task = make_task()
        prompt = _build_prompt(task, "docs/plan.md", human_guidance=None)
        assert "Additional guidance" not in prompt


class TestEstimateTokens:
    """Test token estimation function."""

    def test_zero_cost_returns_zero(self):
        """Zero cost should return zero tokens."""
        from orchestrator.runner import _estimate_tokens

        assert _estimate_tokens(0.0) == 0

    def test_negative_cost_returns_zero(self):
        """Negative cost should return zero tokens."""
        from orchestrator.runner import _estimate_tokens

        assert _estimate_tokens(-0.01) == 0

    def test_positive_cost_returns_tokens(self):
        """Positive cost should return estimated tokens."""
        from orchestrator.runner import _estimate_tokens

        tokens = _estimate_tokens(0.01)
        assert tokens > 0
        # ~$0.01 per 1000 tokens, so 0.01 should be ~1000 tokens
        assert tokens == 1000


class TestRunTask:
    """Test run_task function behavior."""

    @pytest.mark.asyncio
    async def test_invokes_sandbox_with_prompt(self):
        """run_task should invoke sandbox with constructed prompt."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, sandbox, config, task.plan_file)

        sandbox.invoke_claude.assert_called_once()
        call_args = sandbox.invoke_claude.call_args
        prompt = call_args[1]["prompt"]
        assert task.id in prompt

    @pytest.mark.asyncio
    async def test_uses_streaming_when_callback_provided(self):
        """run_task should use streaming mode when on_tool_use callback provided."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude_streaming = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        def callback(tool: str, data: dict) -> None:
            pass

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, sandbox, config, task.plan_file, on_tool_use=callback)

        sandbox.invoke_claude_streaming.assert_called_once()

    @pytest.mark.asyncio
    async def test_interprets_result_with_brain(self):
        """run_task should use HaikuBrain for result interpretation."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed successfully")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        mock_brain.interpret_result.assert_called_once_with("Task completed successfully")
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_maps_needs_help_to_needs_human(self):
        """run_task should map 'needs_help' status to 'needs_human'."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(return_value=make_claude_result("Need help"))

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="needs_help",
            question="Which option?",
            options=["A", "B"],
            recommendation="A",
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.status == "needs_human"
        assert result.question == "Which option?"

    @pytest.mark.asyncio
    async def test_returns_task_result_with_cost(self):
        """run_task should return TaskResult with cost info."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Done", cost=0.05)
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.cost_usd == 0.05
        assert result.task_id == task.id

    @pytest.mark.asyncio
    async def test_passes_model_to_sandbox(self):
        """run_task should pass model parameter to sandbox."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(return_value=make_claude_result("Done"))

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, sandbox, config, task.plan_file, model="opus")

        call_args = sandbox.invoke_claude.call_args
        assert call_args[1]["model"] == "opus"

    @pytest.mark.asyncio
    async def test_passes_session_id_for_resume(self):
        """run_task should pass session_id for resume functionality."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(return_value=make_claude_result("Done"))

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(
                task, sandbox, config, task.plan_file, session_id="prev-session"
            )

        call_args = sandbox.invoke_claude.call_args
        assert call_args[1]["session_id"] == "prev-session"

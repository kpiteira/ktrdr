"""Tests for task runner module.

These tests verify task execution via Claude Code and result parsing.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.config import OrchestratorConfig
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


class TestRunTaskPromptConstruction:
    """Test that run_task constructs proper prompts."""

    @pytest.mark.asyncio
    async def test_prompt_includes_ktask_command(self):
        """Prompt should include /ktask command with plan and task ID."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        await run_task(task, sandbox, config)

        call_args = sandbox.invoke_claude.call_args
        prompt = call_args[1]["prompt"]
        assert "/ktask" in prompt
        assert task.plan_file in prompt
        assert task.id in prompt

    @pytest.mark.asyncio
    async def test_prompt_includes_human_guidance_when_provided(self):
        """Prompt should include human guidance when provided."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        await run_task(task, sandbox, config, human_guidance="Use option A")

        call_args = sandbox.invoke_claude.call_args
        prompt = call_args[1]["prompt"]
        assert "Use option A" in prompt

    @pytest.mark.asyncio
    async def test_uses_config_max_turns(self):
        """Should use max_turns from config."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig(max_turns=100)
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        await run_task(task, sandbox, config)

        call_kwargs = sandbox.invoke_claude.call_args[1]
        assert call_kwargs["max_turns"] == 100

    @pytest.mark.asyncio
    async def test_uses_config_timeout(self):
        """Should use task_timeout_seconds from config."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig(task_timeout_seconds=1200)
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        await run_task(task, sandbox, config)

        call_kwargs = sandbox.invoke_claude.call_args[1]
        assert call_kwargs["timeout"] == 1200


class TestRunTaskStatusParsing:
    """Test parsing of STATUS from Claude output."""

    @pytest.mark.asyncio
    async def test_parses_completed_status(self):
        """Should parse 'completed' status from output."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result(
                "Task done successfully.\n\nSTATUS: completed"
            )
        )

        result = await run_task(task, sandbox, config)

        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_parses_failed_status(self):
        """Should parse 'failed' status from output."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result(
                "Could not complete.\n\nSTATUS: failed\nERROR: Module not found"
            )
        )

        result = await run_task(task, sandbox, config)

        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_parses_needs_human_status(self):
        """Should parse 'needs_human' status from output."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result(
                "Need clarification.\n\nSTATUS: needs_human\n"
                "QUESTION: Which approach?\nOPTIONS: A, B\nRECOMMENDATION: A"
            )
        )

        result = await run_task(task, sandbox, config)

        assert result.status == "needs_human"


class TestRunTaskErrorExtraction:
    """Test extraction of error information."""

    @pytest.mark.asyncio
    async def test_extracts_error_for_failed_status(self):
        """Should extract error message when status is failed."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result(
                "STATUS: failed\nERROR: Import error in module"
            )
        )

        result = await run_task(task, sandbox, config)

        assert result.error is not None
        assert "Import error" in result.error


class TestRunTaskNeedsHumanExtraction:
    """Test extraction of needs_human information."""

    @pytest.mark.asyncio
    async def test_extracts_question(self):
        """Should extract question for needs_human status."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result(
                "STATUS: needs_human\nQUESTION: Should I use Redis or PostgreSQL?"
            )
        )

        result = await run_task(task, sandbox, config)

        assert result.question is not None
        assert "Redis" in result.question

    @pytest.mark.asyncio
    async def test_extracts_options(self):
        """Should extract options for needs_human status."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result(
                "STATUS: needs_human\nQUESTION: Which?\nOPTIONS: A, B, C"
            )
        )

        result = await run_task(task, sandbox, config)

        assert result.options is not None
        assert "A" in result.options
        assert "B" in result.options

    @pytest.mark.asyncio
    async def test_extracts_recommendation(self):
        """Should extract recommendation for needs_human status."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result(
                "STATUS: needs_human\nQUESTION: Which?\n"
                "OPTIONS: A, B\nRECOMMENDATION: Option A is safer"
            )
        )

        result = await run_task(task, sandbox, config)

        assert result.recommendation is not None
        assert "Option A" in result.recommendation


class TestRunTaskResultFields:
    """Test that TaskResult fields are properly populated."""

    @pytest.mark.asyncio
    async def test_result_contains_task_id(self):
        """Result should contain the task ID."""
        from orchestrator.task_runner import run_task

        task = make_task(task_id="3.5")
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        result = await run_task(task, sandbox, config)

        assert result.task_id == "3.5"

    @pytest.mark.asyncio
    async def test_result_contains_cost(self):
        """Result should contain cost from Claude result."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed", cost=0.12)
        )

        result = await run_task(task, sandbox, config)

        assert result.cost_usd == 0.12

    @pytest.mark.asyncio
    async def test_result_contains_session_id(self):
        """Result should contain session ID from Claude result."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        result = await run_task(task, sandbox, config)

        assert result.session_id == "test-session-123"

    @pytest.mark.asyncio
    async def test_result_contains_output(self):
        """Result should contain full Claude output."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        output_text = "Detailed task output here.\n\nSTATUS: completed"
        sandbox.invoke_claude = AsyncMock(return_value=make_claude_result(output_text))

        result = await run_task(task, sandbox, config)

        assert "Detailed task output" in result.output

    @pytest.mark.asyncio
    async def test_result_contains_duration(self):
        """Result should contain execution duration."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        result = await run_task(task, sandbox, config)

        assert result.duration_seconds >= 0


class TestParseTaskOutput:
    """Test the parse_task_output helper function."""

    def test_parse_completed_status(self):
        """Should parse completed status."""
        from orchestrator.task_runner import parse_task_output

        status, question, options, recommendation, error = parse_task_output(
            "Done!\n\nSTATUS: completed"
        )

        assert status == "completed"
        assert question is None
        assert error is None

    def test_parse_failed_with_error(self):
        """Should parse failed status with error."""
        from orchestrator.task_runner import parse_task_output

        status, question, options, recommendation, error = parse_task_output(
            "STATUS: failed\nERROR: Something broke"
        )

        assert status == "failed"
        assert error is not None
        assert "Something broke" in error

    def test_parse_needs_human_with_all_fields(self):
        """Should parse needs_human with question, options, recommendation."""
        from orchestrator.task_runner import parse_task_output

        output = (
            "STATUS: needs_human\n"
            "QUESTION: What should I do?\n"
            "OPTIONS: A, B, C\n"
            "RECOMMENDATION: Choose B"
        )
        status, question, options, recommendation, error = parse_task_output(output)

        assert status == "needs_human"
        assert question == "What should I do?"
        assert options == ["A", "B", "C"]
        assert recommendation == "Choose B"

    def test_defaults_to_completed_when_no_status(self):
        """Should default to completed when no STATUS marker found."""
        from orchestrator.task_runner import parse_task_output

        status, question, options, recommendation, error = parse_task_output(
            "Task finished successfully"
        )

        assert status == "completed"

"""Tests for task runner module.

These tests verify task execution via Claude Code and result parsing.
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


class TestRunTaskPromptConstruction:
    """Test that run_task constructs proper prompts."""

    @pytest.mark.asyncio
    async def test_prompt_includes_task_details(self):
        """Prompt should include task ID, title, and details."""
        from orchestrator.task_runner import run_task

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

        call_args = sandbox.invoke_claude.call_args
        prompt = call_args[1]["prompt"]
        # /ktask invocation: /ktask impl: <plan_path> task: <task_id>
        assert task.id in prompt
        assert task.plan_file in prompt

    @pytest.mark.asyncio
    async def test_prompt_includes_human_guidance_when_provided(self):
        """Prompt should include human guidance when provided."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(
                task, sandbox, config, task.plan_file, human_guidance="Use option A"
            )

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
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, sandbox, config, task.plan_file)

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
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, sandbox, config, task.plan_file)

        call_kwargs = sandbox.invoke_claude.call_args[1]
        assert call_kwargs["timeout"] == 1200


class TestRunTaskStatusParsing:
    """Test parsing of status via HaikuBrain semantic interpretation."""

    @pytest.mark.asyncio
    async def test_parses_completed_status(self):
        """Should detect 'completed' status via HaikuBrain."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task done successfully.")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed", summary="Task finished"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_parses_failed_status(self):
        """Should detect 'failed' status via HaikuBrain."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Could not complete.")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="failed", summary="Task failed", error="Module not found"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_parses_needs_human_status(self):
        """Should detect 'needs_human' status via HaikuBrain."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Need clarification.")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="needs_help",
            question="Which approach?",
            options=["A", "B"],
            recommendation="A",
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.status == "needs_human"


class TestRunTaskErrorExtraction:
    """Test extraction of error information via HaikuBrain."""

    @pytest.mark.asyncio
    async def test_extracts_error_for_failed_status(self):
        """Should extract error message via HaikuBrain when status is failed."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Import error in module")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="failed", summary="Task failed", error="Import error in module"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.error is not None
        assert "Import error" in result.error


class TestRunTaskNeedsHumanExtraction:
    """Test extraction of needs_human information via HaikuBrain."""

    @pytest.mark.asyncio
    async def test_extracts_question(self):
        """Should extract question via HaikuBrain for needs_human status."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Should I use Redis or PostgreSQL?")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="needs_help", question="Should I use Redis or PostgreSQL?"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.question is not None
        assert "Redis" in result.question

    @pytest.mark.asyncio
    async def test_extracts_options(self):
        """Should extract options via HaikuBrain for needs_human status."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Which option?")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="needs_help", question="Which?", options=["A", "B", "C"]
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.options is not None
        assert "A" in result.options
        assert "B" in result.options

    @pytest.mark.asyncio
    async def test_extracts_recommendation(self):
        """Should extract recommendation via HaikuBrain for needs_human status."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Which option?")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="needs_help",
            question="Which?",
            options=["A", "B"],
            recommendation="Option A is safer",
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

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
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.task_id == "3.5"

    @pytest.mark.asyncio
    async def test_result_contains_cost(self):
        """Result should contain cost from Claude result."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed", cost=0.12)
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.cost_usd == 0.12

    @pytest.mark.asyncio
    async def test_result_contains_session_id(self):
        """Result should contain session ID from Claude result."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.session_id == "test-session-123"

    @pytest.mark.asyncio
    async def test_result_contains_output(self):
        """Result should contain full Claude output."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        output_text = "Detailed task output here."
        sandbox.invoke_claude = AsyncMock(return_value=make_claude_result(output_text))

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert "Detailed task output" in result.output

    @pytest.mark.asyncio
    async def test_result_contains_duration(self):
        """Result should contain execution duration."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.duration_seconds >= 0


class TestRunTaskHaikuBrainInterpretation:
    """Test that run_task uses HaikuBrain for semantic interpretation."""

    @pytest.mark.asyncio
    async def test_uses_haiku_brain_for_interpretation(self):
        """Should use HaikuBrain.interpret_result() for status detection."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()

        # Output without STATUS marker - requires semantic understanding
        output_text = "Task finished successfully. All tests pass."
        sandbox.invoke_claude = AsyncMock(return_value=make_claude_result(output_text))

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed", summary="Task finished"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        # HaikuBrain should have been used
        mock_brain.interpret_result.assert_called_once_with(output_text)
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_maps_needs_help_to_needs_human(self):
        """Should map InterpretationResult 'needs_help' to TaskResult 'needs_human'."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Which approach should I use?")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="needs_help",
            question="Which approach should I use?",
            options=["A", "B"],
            recommendation="Option A is safer",
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        # Status should be mapped to needs_human
        assert result.status == "needs_human"
        assert result.question == "Which approach should I use?"
        assert result.options == ["A", "B"]
        assert result.recommendation == "Option A is safer"

    @pytest.mark.asyncio
    async def test_extracts_error_for_failed_status(self):
        """Should extract error from InterpretationResult when status is failed."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Tests failed with error")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="failed",
            summary="Tests failed",
            error="Import error in module",
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, sandbox, config, task.plan_file)

        assert result.status == "failed"
        assert result.error == "Import error in module"

    @pytest.mark.asyncio
    async def test_full_output_passed_to_haiku_brain(self):
        """Should pass full output to HaikuBrain without truncation."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()

        # Large output (10k+ chars)
        large_output = "A" * 15000
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result(large_output)
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, sandbox, config, task.plan_file)

        # Full output should be passed (no truncation)
        call_args = mock_brain.interpret_result.call_args[0]
        assert len(call_args[0]) == 15000


class TestRunTaskStreaming:
    """Test streaming support in run_task."""

    @pytest.mark.asyncio
    async def test_uses_streaming_when_callback_provided(self):
        """Should use invoke_claude_streaming when on_tool_use is provided."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()

        # Setup streaming method
        sandbox.invoke_claude_streaming = AsyncMock(
            return_value=make_claude_result("Task completed")
        )
        # Also setup non-streaming for comparison
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        tool_calls: list[tuple[str, dict]] = []

        def on_tool(name: str, input_data: dict) -> None:
            tool_calls.append((name, input_data))

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, sandbox, config, task.plan_file, on_tool_use=on_tool)

        # Should have used streaming method
        sandbox.invoke_claude_streaming.assert_called_once()
        # Should NOT have used non-streaming method
        sandbox.invoke_claude.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_non_streaming_when_no_callback(self):
        """Should use invoke_claude when no on_tool_use callback."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()

        sandbox.invoke_claude_streaming = AsyncMock(
            return_value=make_claude_result("Task completed")
        )
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, sandbox, config, task.plan_file)

        # Should have used non-streaming method
        sandbox.invoke_claude.assert_called_once()
        # Should NOT have used streaming method
        sandbox.invoke_claude_streaming.assert_not_called()

    @pytest.mark.asyncio
    async def test_streaming_passes_callback_to_sandbox(self):
        """Callback should be passed through to sandbox streaming method."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()

        sandbox.invoke_claude_streaming = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        def my_callback(name: str, data: dict) -> None:
            pass

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, sandbox, config, task.plan_file, on_tool_use=my_callback)

        # Verify callback was passed
        call_kwargs = sandbox.invoke_claude_streaming.call_args[1]
        assert "on_tool_use" in call_kwargs
        assert call_kwargs["on_tool_use"] == my_callback

    @pytest.mark.asyncio
    async def test_streaming_passes_config_params(self):
        """Should pass max_turns and timeout to streaming method."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig(max_turns=75, task_timeout_seconds=900)
        sandbox = MagicMock()

        sandbox.invoke_claude_streaming = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(
                task, sandbox, config, task.plan_file, on_tool_use=lambda n, i: None
            )

        call_kwargs = sandbox.invoke_claude_streaming.call_args[1]
        assert call_kwargs["max_turns"] == 75
        assert call_kwargs["timeout"] == 900


class TestRunTaskWithEscalation:
    """Test run_task_with_escalation with HaikuBrain retry/escalate decisions."""

    @pytest.mark.asyncio
    async def test_returns_completed_result_immediately(self):
        """Should return immediately when task completes successfully."""
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        # Mock tracer
        mock_tracer = MagicMock()

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed"
        )

        with (
            patch("orchestrator.runner.console"),
            patch("orchestrator.runner.get_brain", return_value=mock_brain),
        ):
            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, mock_tracer
            )

        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_triggers_escalation_on_needs_human(self):
        """Should trigger escalation when task returns needs_human."""
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()

        # First call returns needs_human, second returns completed
        sandbox.invoke_claude = AsyncMock(
            side_effect=[
                make_claude_result("Which approach?"),
                make_claude_result("Task completed"),
            ]
        )

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.side_effect = [
            make_interpretation_result(
                status="needs_help",
                question="Which approach?",
                recommendation="Use A",
            ),
            make_interpretation_result(status="completed"),
        ]

        with (
            patch("orchestrator.runner.console"),
            patch("orchestrator.runner.escalate_and_wait") as mock_escalate,
            patch("orchestrator.runner.get_brain", return_value=mock_brain),
        ):
            mock_escalate.return_value = "Use option A"

            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, mock_tracer
            )

        # Should have called escalate_and_wait
        mock_escalate.assert_called_once()
        # Final result should be completed
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_retries_with_guidance_after_escalation(self):
        """Should retry task with human guidance after escalation."""
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()

        # Track calls to verify guidance is passed
        calls = []

        async def mock_invoke(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return make_claude_result("Which option?")
            return make_claude_result("Task completed")

        sandbox.invoke_claude = mock_invoke

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.side_effect = [
            make_interpretation_result(status="needs_help", question="Which?"),
            make_interpretation_result(status="completed"),
        ]

        with (
            patch("orchestrator.runner.console"),
            patch("orchestrator.runner.escalate_and_wait") as mock_escalate,
            patch("orchestrator.runner.get_brain", return_value=mock_brain),
        ):
            mock_escalate.return_value = "Use option B"

            await run_task_with_escalation(
                task, sandbox, config, task.plan_file, mock_tracer
            )

        # Second call should have guidance in prompt
        assert len(calls) == 2
        assert "Use option B" in calls[1]["prompt"]

    @pytest.mark.asyncio
    async def test_first_failure_retries_with_haiku_guidance(self):
        """First failure should call HaikuBrain for retry decision and use guidance."""
        from orchestrator.haiku_brain import RetryDecision
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()

        # Track calls to verify guidance is passed
        calls = []

        async def mock_invoke(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return make_claude_result("Import error occurred")
            return make_claude_result("Task completed")

        sandbox.invoke_claude = mock_invoke

        mock_tracer = MagicMock()

        mock_brain = MagicMock()
        mock_brain.interpret_result.side_effect = [
            make_interpretation_result(status="failed", error="Import error"),
            make_interpretation_result(status="completed"),
        ]
        # Haiku says retry with guidance
        mock_brain.should_retry_or_escalate.return_value = RetryDecision(
            decision="retry",
            reason="First attempt, error is fixable",
            guidance_for_retry="Add the missing import at the top of the file",
        )

        with (
            patch("orchestrator.runner.console"),
            patch("orchestrator.runner.get_brain", return_value=mock_brain),
        ):
            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, mock_tracer
            )

        # Should have called should_retry_or_escalate
        mock_brain.should_retry_or_escalate.assert_called_once()
        call_args = mock_brain.should_retry_or_escalate.call_args
        assert call_args[1]["task_id"] == "4.1"
        assert call_args[1]["attempt_count"] == 1
        assert len(call_args[1]["attempt_history"]) == 1
        assert "Import error" in call_args[1]["attempt_history"][0]

        # Second call should have guidance in prompt
        assert len(calls) == 2
        assert "missing import" in calls[1]["prompt"]

        # Final result should be completed
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_same_error_three_times_escalates(self):
        """Same error 3 times should trigger HaikuBrain escalation decision."""
        from orchestrator.haiku_brain import RetryDecision
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()

        call_count = 0

        async def mock_invoke(**kwargs):
            nonlocal call_count
            call_count += 1
            # After escalation (4th call), task completes
            if call_count == 4:
                return make_claude_result("Task completed after human help")
            return make_claude_result("Same import error")

        sandbox.invoke_claude = mock_invoke

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        # First 3 fail, 4th succeeds
        mock_brain.interpret_result.side_effect = [
            make_interpretation_result(status="failed", error="Same import error"),
            make_interpretation_result(status="failed", error="Same import error"),
            make_interpretation_result(status="failed", error="Same import error"),
            make_interpretation_result(status="completed"),
        ]
        # First two times: retry. Third time: escalate
        mock_brain.should_retry_or_escalate.side_effect = [
            RetryDecision(
                decision="retry",
                reason="First attempt",
                guidance_for_retry="Try adding the import",
            ),
            RetryDecision(
                decision="retry",
                reason="Second attempt, different approach",
                guidance_for_retry="Check if module is installed",
            ),
            RetryDecision(
                decision="escalate",
                reason="Same error 3 times, stuck in a loop",
                guidance_for_retry=None,
            ),
        ]

        with (
            patch("orchestrator.runner.console"),
            patch("orchestrator.runner.escalate_and_wait") as mock_escalate,
            patch("orchestrator.runner.get_brain", return_value=mock_brain),
        ):
            mock_escalate.return_value = "Human provided guidance"

            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, mock_tracer
            )

        # Should have tried 4 times (3 fails + 1 success after human help)
        assert call_count == 4
        # Should have called should_retry_or_escalate 3 times (not for success)
        assert mock_brain.should_retry_or_escalate.call_count == 3
        # Should have escalated
        mock_escalate.assert_called_once()
        # Final result should be completed
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_different_errors_continues_retrying(self):
        """Different errors each attempt should continue retrying (making progress)."""
        from orchestrator.haiku_brain import RetryDecision
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()

        call_count = 0

        async def mock_invoke(**kwargs):
            nonlocal call_count
            call_count += 1
            return make_claude_result(f"Attempt {call_count}")

        sandbox.invoke_claude = mock_invoke

        mock_tracer = MagicMock()

        mock_brain = MagicMock()
        mock_brain.interpret_result.side_effect = [
            make_interpretation_result(status="failed", error="Import error"),
            make_interpretation_result(status="failed", error="Type error"),
            make_interpretation_result(status="completed"),
        ]
        # Haiku says retry both times (different errors = progress)
        mock_brain.should_retry_or_escalate.side_effect = [
            RetryDecision(
                decision="retry",
                reason="First attempt, fixable error",
                guidance_for_retry="Fix the import",
            ),
            RetryDecision(
                decision="retry",
                reason="Different error, making progress",
                guidance_for_retry="Fix the type annotation",
            ),
        ]

        with (
            patch("orchestrator.runner.console"),
            patch("orchestrator.runner.get_brain", return_value=mock_brain),
        ):
            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, mock_tracer
            )

        # Should have tried 3 times (2 failures + 1 success)
        assert call_count == 3
        # Should have called should_retry_or_escalate 2 times (not for success)
        assert mock_brain.should_retry_or_escalate.call_count == 2
        # Final result should be completed
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_escalation_triggered_on_haiku_escalate_decision(self):
        """Escalation should be triggered when HaikuBrain returns escalate decision."""
        from orchestrator.haiku_brain import RetryDecision
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("I need human clarification")
        )

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.side_effect = [
            make_interpretation_result(
                status="failed", error="I need clarification on which database to use"
            ),
            make_interpretation_result(status="completed"),
        ]
        # Haiku immediately says escalate
        mock_brain.should_retry_or_escalate.return_value = RetryDecision(
            decision="escalate",
            reason="Claude explicitly needs human input",
            guidance_for_retry=None,
        )

        with (
            patch("orchestrator.runner.console"),
            patch("orchestrator.runner.escalate_and_wait") as mock_escalate,
            patch("orchestrator.runner.get_brain", return_value=mock_brain),
        ):
            mock_escalate.return_value = "Use PostgreSQL"

            await run_task_with_escalation(
                task, sandbox, config, task.plan_file, mock_tracer
            )

        # Should have escalated
        mock_escalate.assert_called_once()
        info = mock_escalate.call_args[0][0]
        assert info.task_id == "4.1"
        assert "clarification" in info.question.lower() or "failed" in info.question.lower()

    @pytest.mark.asyncio
    async def test_attempt_history_tracked_correctly(self):
        """Attempt history should accumulate across retries."""
        from orchestrator.haiku_brain import RetryDecision
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()

        async def mock_invoke(**kwargs):
            return make_claude_result("Error output")

        sandbox.invoke_claude = mock_invoke

        mock_tracer = MagicMock()

        mock_brain = MagicMock()
        mock_brain.interpret_result.side_effect = [
            make_interpretation_result(status="failed", error="Error A"),
            make_interpretation_result(status="failed", error="Error B"),
            make_interpretation_result(status="completed"),
        ]
        # Track the attempt_history passed to should_retry_or_escalate
        history_calls = []

        def capture_retry_call(
            task_id: str,
            task_title: str,
            attempt_history: list[str],
            attempt_count: int,
        ) -> RetryDecision:
            history_calls.append((attempt_count, list(attempt_history)))
            return RetryDecision(
                decision="retry",
                reason="Keep trying",
                guidance_for_retry=f"Guidance {attempt_count}",
            )

        mock_brain.should_retry_or_escalate.side_effect = capture_retry_call

        with (
            patch("orchestrator.runner.console"),
            patch("orchestrator.runner.get_brain", return_value=mock_brain),
        ):
            await run_task_with_escalation(
                task, sandbox, config, task.plan_file, mock_tracer
            )

        # First call: 1 attempt, 1 error in history
        assert history_calls[0][0] == 1
        assert len(history_calls[0][1]) == 1
        assert "Error A" in history_calls[0][1][0]

        # Second call: 2 attempts, 2 errors in history
        assert history_calls[1][0] == 2
        assert len(history_calls[1][1]) == 2
        assert "Error A" in history_calls[1][1][0]
        assert "Error B" in history_calls[1][1][1]

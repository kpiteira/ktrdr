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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
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

        with patch("orchestrator.task_runner.get_brain", return_value=mock_brain):
            await run_task(
                task, sandbox, config, task.plan_file, on_tool_use=lambda n, i: None
            )

        call_kwargs = sandbox.invoke_claude_streaming.call_args[1]
        assert call_kwargs["max_turns"] == 75
        assert call_kwargs["timeout"] == 900


class TestRunTaskWithEscalation:
    """Test run_task_with_escalation for loop detection and escalation."""

    @pytest.mark.asyncio
    async def test_returns_completed_result_immediately(self):
        """Should return immediately when task completes successfully."""
        from datetime import datetime

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        state = OrchestratorState(
            milestone_id="M4", plan_path="test.md", started_at=datetime.now()
        )
        loop_detector = LoopDetector(LoopDetectorConfig(), state)

        # Mock tracer
        mock_tracer = MagicMock()

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed"
        )

        with (
            patch("orchestrator.task_runner.console"),
            patch("orchestrator.task_runner.get_brain", return_value=mock_brain),
        ):
            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, loop_detector, mock_tracer
            )

        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_triggers_escalation_on_needs_human(self):
        """Should trigger escalation when task returns needs_human."""
        from datetime import datetime

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
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

        state = OrchestratorState(
            milestone_id="M4", plan_path="test.md", started_at=datetime.now()
        )
        loop_detector = LoopDetector(LoopDetectorConfig(), state)

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
            patch("orchestrator.task_runner.console"),
            patch("orchestrator.task_runner.escalate_and_wait") as mock_escalate,
            patch("orchestrator.task_runner.get_brain", return_value=mock_brain),
        ):
            mock_escalate.return_value = "Use option A"

            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, loop_detector, mock_tracer
            )

        # Should have called escalate_and_wait
        mock_escalate.assert_called_once()
        # Final result should be completed
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_retries_with_guidance_after_escalation(self):
        """Should retry task with human guidance after escalation."""
        from datetime import datetime

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
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

        state = OrchestratorState(
            milestone_id="M4", plan_path="test.md", started_at=datetime.now()
        )
        loop_detector = LoopDetector(LoopDetectorConfig(), state)

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
            patch("orchestrator.task_runner.console"),
            patch("orchestrator.task_runner.escalate_and_wait") as mock_escalate,
            patch("orchestrator.task_runner.get_brain", return_value=mock_brain),
        ):
            mock_escalate.return_value = "Use option B"

            await run_task_with_escalation(
                task, sandbox, config, task.plan_file, loop_detector, mock_tracer
            )

        # Second call should have guidance in prompt
        assert len(calls) == 2
        assert "Use option B" in calls[1]["prompt"]

    @pytest.mark.asyncio
    async def test_records_failure_in_loop_detector(self):
        """Should record task failure in loop detector."""
        from datetime import datetime

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()

        # Fail 3 times to trigger loop detection
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Module not found error")
        )

        state = OrchestratorState(
            milestone_id="M4", plan_path="test.md", started_at=datetime.now()
        )
        loop_detector = LoopDetector(LoopDetectorConfig(max_task_attempts=3), state)

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="failed", error="Module not found"
        )

        with (
            patch("orchestrator.task_runner.console"),
            patch("orchestrator.task_runner.get_brain", return_value=mock_brain),
        ):
            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, loop_detector, mock_tracer
            )

        # Should have recorded failures
        assert state.task_attempt_counts.get("4.1", 0) == 3
        # Result should indicate loop detected
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_stops_at_loop_detection(self):
        """Should stop retrying when loop detected."""
        from datetime import datetime

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()

        call_count = 0

        async def mock_invoke(**kwargs):
            nonlocal call_count
            call_count += 1
            return make_claude_result("Module not found error")

        sandbox.invoke_claude = mock_invoke

        state = OrchestratorState(
            milestone_id="M4", plan_path="test.md", started_at=datetime.now()
        )
        loop_detector = LoopDetector(LoopDetectorConfig(max_task_attempts=3), state)

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="failed", error="Module not found"
        )

        with (
            patch("orchestrator.task_runner.console"),
            patch("orchestrator.task_runner.get_brain", return_value=mock_brain),
        ):
            await run_task_with_escalation(
                task, sandbox, config, task.plan_file, loop_detector, mock_tracer
            )

        # Should have stopped at exactly 3 attempts
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_loop_detection_includes_reason_in_error(self):
        """Loop detection should include reason in result error."""
        from datetime import datetime

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("Same error occurred")
        )

        state = OrchestratorState(
            milestone_id="M4", plan_path="test.md", started_at=datetime.now()
        )
        loop_detector = LoopDetector(LoopDetectorConfig(max_task_attempts=3), state)

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="failed", error="Same error"
        )

        with (
            patch("orchestrator.task_runner.console"),
            patch("orchestrator.task_runner.get_brain", return_value=mock_brain),
        ):
            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, loop_detector, mock_tracer
            )

        # Error should mention loop detection
        assert result.error is not None
        assert "3 times" in result.error or "loop" in result.error.lower()

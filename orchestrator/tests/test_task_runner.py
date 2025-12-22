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
    async def test_prompt_includes_task_details(self):
        """Prompt should include task ID, title, and details."""
        from orchestrator.task_runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

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
            return_value=make_claude_result("STATUS: completed")
        )

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
            return_value=make_claude_result("STATUS: completed")
        )

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
            return_value=make_claude_result("STATUS: completed")
        )

        await run_task(task, sandbox, config, task.plan_file)

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

        result = await run_task(task, sandbox, config, task.plan_file)

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

        result = await run_task(task, sandbox, config, task.plan_file)

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

        result = await run_task(task, sandbox, config, task.plan_file)

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

        result = await run_task(task, sandbox, config, task.plan_file)

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

        result = await run_task(task, sandbox, config, task.plan_file)

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

        result = await run_task(task, sandbox, config, task.plan_file)

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
            return_value=make_claude_result("STATUS: completed")
        )

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
            return_value=make_claude_result("STATUS: completed", cost=0.12)
        )

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
            return_value=make_claude_result("STATUS: completed")
        )

        result = await run_task(task, sandbox, config, task.plan_file)

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
            return_value=make_claude_result("STATUS: completed")
        )

        result = await run_task(task, sandbox, config, task.plan_file)

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
            return_value=make_claude_result("STATUS: completed")
        )
        # Also setup non-streaming for comparison
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        tool_calls: list[tuple[str, dict]] = []

        def on_tool(name: str, input_data: dict) -> None:
            tool_calls.append((name, input_data))

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
            return_value=make_claude_result("STATUS: completed")
        )
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        await run_task(task, sandbox, config, task.plan_file)  # No on_tool_use callback

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
            return_value=make_claude_result("STATUS: completed")
        )

        def my_callback(name: str, data: dict) -> None:
            pass

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
            return_value=make_claude_result("STATUS: completed")
        )

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
        from unittest.mock import patch

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: completed")
        )

        state = OrchestratorState(
            milestone_id="M4", plan_path="test.md", started_at=datetime.now()
        )
        loop_detector = LoopDetector(LoopDetectorConfig(), state)

        # Mock tracer
        mock_tracer = MagicMock()

        with patch("orchestrator.task_runner.console"):
            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, loop_detector, mock_tracer
            )

        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_triggers_escalation_on_needs_human(self):
        """Should trigger escalation when task returns needs_human."""
        from datetime import datetime
        from unittest.mock import patch

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task()
        config = OrchestratorConfig()
        sandbox = MagicMock()

        # First call returns needs_human, second returns completed
        sandbox.invoke_claude = AsyncMock(
            side_effect=[
                make_claude_result(
                    "STATUS: needs_human\nQUESTION: Which approach?\nRECOMMENDATION: Use A"
                ),
                make_claude_result("STATUS: completed"),
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

        with (
            patch("orchestrator.task_runner.console"),
            patch("orchestrator.task_runner.escalate_and_wait") as mock_escalate,
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
        from unittest.mock import patch

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
                return make_claude_result("STATUS: needs_human\nQUESTION: Which?")
            return make_claude_result("STATUS: completed")

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

        with (
            patch("orchestrator.task_runner.console"),
            patch("orchestrator.task_runner.escalate_and_wait") as mock_escalate,
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
        from unittest.mock import patch

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()

        # Fail 3 times to trigger loop detection
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: failed\nERROR: Module not found")
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

        with patch("orchestrator.task_runner.console"):
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
        from unittest.mock import patch

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
            return make_claude_result("STATUS: failed\nERROR: Module not found")

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

        with patch("orchestrator.task_runner.console"):
            await run_task_with_escalation(
                task, sandbox, config, task.plan_file, loop_detector, mock_tracer
            )

        # Should have stopped at exactly 3 attempts
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_loop_detection_includes_reason_in_error(self):
        """Loop detection should include reason in result error."""
        from datetime import datetime
        from unittest.mock import patch

        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState
        from orchestrator.task_runner import run_task_with_escalation

        task = make_task(task_id="4.1")
        config = OrchestratorConfig()
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("STATUS: failed\nERROR: Same error")
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

        with patch("orchestrator.task_runner.console"):
            result = await run_task_with_escalation(
                task, sandbox, config, task.plan_file, loop_detector, mock_tracer
            )

        # Error should mention loop detection
        assert result.error is not None
        assert "3 times" in result.error or "loop" in result.error.lower()

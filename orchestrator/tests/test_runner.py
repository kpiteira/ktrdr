"""Tests for consolidated runner module.

Tests verify that task execution functions work correctly after
being moved from task_runner.py to runner.py (M4 consolidation).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.llm.haiku_brain import InterpretationResult
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
    async def test_invokes_container_with_prompt(self):
        """run_task should invoke container with constructed prompt."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, container, config, task.plan_file)

        container.invoke_claude.assert_called_once()
        call_args = container.invoke_claude.call_args
        prompt = call_args[1]["prompt"]
        assert task.id in prompt

    @pytest.mark.asyncio
    async def test_uses_streaming_when_callback_provided(self):
        """run_task should use streaming mode when on_tool_use callback provided."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        container = MagicMock()
        container.invoke_claude_streaming = AsyncMock(
            return_value=make_claude_result("Task completed")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        def callback(tool: str, data: dict) -> None:
            pass

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, container, config, task.plan_file, on_tool_use=callback)

        container.invoke_claude_streaming.assert_called_once()

    @pytest.mark.asyncio
    async def test_interprets_result_with_brain(self):
        """run_task should use HaikuBrain for result interpretation."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("Task completed successfully")
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, container, config, task.plan_file)

        mock_brain.interpret_result.assert_called_once_with("Task completed successfully")
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_maps_needs_help_to_needs_human(self):
        """run_task should map 'needs_help' status to 'needs_human'."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        container = MagicMock()
        container.invoke_claude = AsyncMock(return_value=make_claude_result("Need help"))

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="needs_help",
            question="Which option?",
            options=["A", "B"],
            recommendation="A",
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, container, config, task.plan_file)

        assert result.status == "needs_human"
        assert result.question == "Which option?"

    @pytest.mark.asyncio
    async def test_returns_task_result_with_cost(self):
        """run_task should return TaskResult with cost info."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("Done", cost=0.05)
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_task(task, container, config, task.plan_file)

        assert result.cost_usd == 0.05
        assert result.task_id == task.id

    @pytest.mark.asyncio
    async def test_passes_model_to_container(self):
        """run_task should pass model parameter to container."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        container = MagicMock()
        container.invoke_claude = AsyncMock(return_value=make_claude_result("Done"))

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(task, container, config, task.plan_file, model="opus")

        call_args = container.invoke_claude.call_args
        assert call_args[1]["model"] == "opus"

    @pytest.mark.asyncio
    async def test_passes_session_id_for_resume(self):
        """run_task should pass session_id for resume functionality."""
        from orchestrator.runner import run_task

        task = make_task()
        config = OrchestratorConfig()
        container = MagicMock()
        container.invoke_claude = AsyncMock(return_value=make_claude_result("Done"))

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_task(
                task, container, config, task.plan_file, session_id="prev-session"
            )

        call_args = container.invoke_claude.call_args
        assert call_args[1]["session_id"] == "prev-session"


# =============================================================================
# E2E EXECUTION TESTS (Task 4.2 - Merged from e2e_runner.py)
# =============================================================================


class TestE2EResultInRunner:
    """Test E2EResult dataclass in runner.py."""

    def test_e2e_result_is_exported(self):
        """E2EResult should be importable from runner."""
        from orchestrator.runner import E2EResult

        assert E2EResult is not None

    def test_e2e_result_has_all_required_fields(self):
        """E2EResult should have all required fields."""
        from orchestrator.runner import E2EResult

        result = E2EResult(
            status="passed",
            duration_seconds=45.0,
            tokens_used=5000,
            cost_usd=0.05,
            diagnosis=None,
            fix_suggestion=None,
            is_fixable=False,
            raw_output="Test output",
        )

        assert result.status == "passed"
        assert result.duration_seconds == 45.0
        assert result.tokens_used == 5000
        assert result.cost_usd == 0.05
        assert result.diagnosis is None
        assert result.is_fixable is False


class TestRunE2ETestsInRunner:
    """Test run_e2e_tests function in runner.py."""

    def test_run_e2e_tests_is_exported(self):
        """run_e2e_tests should be importable from runner."""
        from orchestrator.runner import run_e2e_tests

        assert callable(run_e2e_tests)

    @pytest.mark.asyncio
    async def test_executes_e2e_via_claude(self):
        """Should invoke Claude with E2E scenario."""
        from orchestrator.runner import run_e2e_tests

        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("E2E tests completed")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            await run_e2e_tests(
                milestone_id="M5",
                e2e_scenario="Run pytest tests/",
                container=container,
                config=config,
                tracer=tracer,
            )

        container.invoke_claude.assert_called_once()
        call_kwargs = container.invoke_claude.call_args[1]
        assert "pytest tests/" in call_kwargs["prompt"]
        assert "M5" in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_uses_haiku_brain_for_interpretation(self):
        """Should use HaikuBrain for E2E result interpretation."""
        from orchestrator.runner import run_e2e_tests

        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("All tests pass ✓")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed", summary="All tests passed"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_e2e_tests(
                milestone_id="M5",
                e2e_scenario="Test scenario",
                container=container,
                config=config,
                tracer=tracer,
            )

        # Verify HaikuBrain was used
        mock_brain.interpret_result.assert_called_once_with("All tests pass ✓")
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_maps_completed_to_passed(self):
        """Should map HaikuBrain 'completed' status to E2E 'passed'."""
        from orchestrator.runner import run_e2e_tests

        container = MagicMock()
        container.invoke_claude = AsyncMock(return_value=make_claude_result("Done"))
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="completed"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_e2e_tests(
                milestone_id="M5",
                e2e_scenario="Test",
                container=container,
                config=config,
                tracer=tracer,
            )

        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_maps_failed_to_failed(self):
        """Should map HaikuBrain 'failed' status to E2E 'failed'."""
        from orchestrator.runner import run_e2e_tests

        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("Error: test failed")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="failed", error="Assertion error in test_foo"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_e2e_tests(
                milestone_id="M5",
                e2e_scenario="Test",
                container=container,
                config=config,
                tracer=tracer,
            )

        assert result.status == "failed"
        assert result.diagnosis is not None

    @pytest.mark.asyncio
    async def test_maps_needs_help_to_unclear(self):
        """Should map HaikuBrain 'needs_help' status to E2E 'unclear'."""
        from orchestrator.runner import run_e2e_tests

        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("I'm not sure what to do")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result(
            status="needs_help", question="How should I proceed?"
        )

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_e2e_tests(
                milestone_id="M5",
                e2e_scenario="Test",
                container=container,
                config=config,
                tracer=tracer,
            )

        assert result.status == "unclear"

    @pytest.mark.asyncio
    async def test_records_duration(self):
        """Should record execution duration in result."""
        from orchestrator.runner import run_e2e_tests

        container = MagicMock()
        container.invoke_claude = AsyncMock(return_value=make_claude_result("Done"))
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = make_interpretation_result()

        with patch("orchestrator.runner.get_brain", return_value=mock_brain):
            result = await run_e2e_tests(
                milestone_id="M5",
                e2e_scenario="Test",
                container=container,
                config=config,
                tracer=tracer,
            )

        assert result.duration_seconds >= 0


class TestApplyE2EFixInRunner:
    """Test apply_e2e_fix function in runner.py."""

    def test_apply_e2e_fix_is_exported(self):
        """apply_e2e_fix should be importable from runner."""
        from orchestrator.runner import apply_e2e_fix

        assert callable(apply_e2e_fix)

    @pytest.mark.asyncio
    async def test_applies_fix_via_claude(self):
        """Should invoke Claude with fix plan."""
        from orchestrator.runner import apply_e2e_fix

        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("FIX_APPLIED: yes")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await apply_e2e_fix(
            fix_plan="Add 'app.include_router(new_router)' to main.py",
            container=container,
            config=config,
            tracer=tracer,
        )

        container.invoke_claude.assert_called_once()
        call_kwargs = container.invoke_claude.call_args[1]
        assert "app.include_router" in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        """Should return True when fix is applied successfully."""
        from orchestrator.runner import apply_e2e_fix

        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("Fix complete.\n\nFIX_APPLIED: yes")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        result = await apply_e2e_fix(
            fix_plan="Add router to main.py",
            container=container,
            config=config,
            tracer=tracer,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self):
        """Should return False when fix cannot be applied."""
        from orchestrator.runner import apply_e2e_fix

        container = MagicMock()
        container.invoke_claude = AsyncMock(
            return_value=make_claude_result("FIX_APPLIED: no\nREASON: File not found")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        result = await apply_e2e_fix(
            fix_plan="Add router to main.py",
            container=container,
            config=config,
            tracer=tracer,
        )

        assert result is False


# =============================================================================
# ESCALATION TESTS (Task 4.3 - Merged from escalation.py)
# =============================================================================


class TestEscalationInfoInRunner:
    """Test EscalationInfo dataclass in runner.py."""

    def test_escalation_info_is_exported(self):
        """EscalationInfo should be importable from runner."""
        from orchestrator.runner import EscalationInfo

        assert EscalationInfo is not None

    def test_escalation_info_has_all_required_fields(self):
        """EscalationInfo should have all required fields."""
        from orchestrator.runner import EscalationInfo

        info = EscalationInfo(
            task_id="3.1",
            question="Which database should I use?",
            options=["PostgreSQL", "MySQL"],
            recommendation="PostgreSQL",
            raw_output="Full Claude output here",
        )

        assert info.task_id == "3.1"
        assert info.question == "Which database should I use?"
        assert info.options == ["PostgreSQL", "MySQL"]
        assert info.recommendation == "PostgreSQL"
        assert info.raw_output == "Full Claude output here"

    def test_escalation_info_allows_none_options(self):
        """EscalationInfo should allow None for optional fields."""
        from orchestrator.runner import EscalationInfo

        info = EscalationInfo(
            task_id="3.1",
            question="Help needed",
            options=None,
            recommendation=None,
            raw_output="Output",
        )

        assert info.options is None
        assert info.recommendation is None


class TestEscalateAndWaitInRunner:
    """Test escalate_and_wait function in runner.py."""

    def test_escalate_and_wait_is_exported(self):
        """escalate_and_wait should be importable from runner."""
        from orchestrator.runner import escalate_and_wait

        assert callable(escalate_and_wait)

    @pytest.mark.asyncio
    async def test_displays_question_and_gets_response(self):
        """Should display question and collect user response."""
        from orchestrator.runner import EscalationInfo, escalate_and_wait

        info = EscalationInfo(
            task_id="3.1",
            question="Which option?",
            options=["A", "B"],
            recommendation="A",
            raw_output="Full output",
        )

        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        # Mock the Prompt.ask to simulate user input
        with patch("orchestrator.runner.Prompt.ask", return_value="Use option B"):
            with patch("orchestrator.runner.send_notification"):
                response = await escalate_and_wait(info, tracer, notify=False)

        assert response == "Use option B"

    @pytest.mark.asyncio
    async def test_uses_recommendation_on_skip(self):
        """Should use recommendation when user enters 'skip'."""
        from orchestrator.runner import EscalationInfo, escalate_and_wait

        info = EscalationInfo(
            task_id="3.1",
            question="Which option?",
            options=["A", "B"],
            recommendation="Use PostgreSQL for production",
            raw_output="Full output",
        )

        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        with patch("orchestrator.runner.Prompt.ask", return_value="skip"):
            with patch("orchestrator.runner.send_notification"):
                response = await escalate_and_wait(info, tracer, notify=False)

        assert response == "Use PostgreSQL for production"

    @pytest.mark.asyncio
    async def test_sends_notification_when_enabled(self):
        """Should send notification when notify=True."""
        from orchestrator.runner import EscalationInfo, escalate_and_wait

        info = EscalationInfo(
            task_id="3.1",
            question="Help needed",
            options=None,
            recommendation=None,
            raw_output="Output",
        )

        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        with patch("orchestrator.runner.Prompt.ask", return_value="response"):
            with patch("orchestrator.runner.send_notification") as mock_notify:
                await escalate_and_wait(info, tracer, notify=True)

        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args[1]
        assert "3.1" in call_kwargs["message"]


class TestGetBrainInRunner:
    """Test get_brain function in runner.py."""

    def test_get_brain_is_exported(self):
        """get_brain should be importable from runner."""
        from orchestrator.runner import get_brain

        assert callable(get_brain)

    def test_get_brain_returns_haiku_brain(self):
        """get_brain should return a HaikuBrain instance."""
        from ktrdr.llm.haiku_brain import HaikuBrain
        from orchestrator.runner import get_brain

        brain = get_brain()
        assert isinstance(brain, HaikuBrain)

    def test_get_brain_returns_singleton(self):
        """get_brain should return the same instance on subsequent calls."""
        from orchestrator.runner import get_brain

        brain1 = get_brain()
        brain2 = get_brain()
        assert brain1 is brain2


class TestConfigureInterpreterInRunner:
    """Test configure_interpreter function in runner.py."""

    def test_configure_interpreter_is_exported(self):
        """configure_interpreter should be importable from runner."""
        from orchestrator.runner import configure_interpreter

        assert callable(configure_interpreter)

    def test_configure_interpreter_resets_brain(self):
        """configure_interpreter should reset the brain singleton."""
        from orchestrator.runner import configure_interpreter, get_brain

        # Get initial brain
        brain1 = get_brain()

        # Configure interpreter (should reset)
        configure_interpreter(llm_only=True)

        # Get new brain - should be a new instance
        brain2 = get_brain()

        # They should be different instances
        assert brain1 is not brain2

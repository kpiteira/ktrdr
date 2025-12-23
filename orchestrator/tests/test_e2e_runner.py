"""Tests for E2E runner module.

These tests verify E2E test execution via Claude Code and result parsing.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.config import OrchestratorConfig
from orchestrator.models import ClaudeResult


def make_claude_result(
    result: str = "E2E tests completed",
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


class TestE2EResult:
    """Test E2EResult dataclass."""

    def test_e2e_result_has_all_required_fields(self):
        """E2EResult should have all required fields."""
        from orchestrator.e2e_runner import E2EResult

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
        assert result.fix_suggestion is None
        assert result.is_fixable is False
        assert result.raw_output == "Test output"

    def test_e2e_result_with_failure_details(self):
        """E2EResult should support failure details."""
        from orchestrator.e2e_runner import E2EResult

        result = E2EResult(
            status="failed",
            duration_seconds=30.0,
            tokens_used=3000,
            cost_usd=0.03,
            diagnosis="The endpoint returns 404",
            fix_suggestion="Add router to main.py",
            is_fixable=True,
            raw_output="E2E_STATUS: failed\nDIAGNOSIS: The endpoint returns 404",
        )

        assert result.status == "failed"
        assert result.diagnosis == "The endpoint returns 404"
        assert result.fix_suggestion == "Add router to main.py"
        assert result.is_fixable is True


class TestParseE2EStatus:
    """Test E2E status parsing from Claude output."""

    def test_parse_passed_status(self):
        """Should parse 'passed' status from explicit marker."""
        from orchestrator.e2e_runner import _parse_e2e_status

        status = _parse_e2e_status("All tests completed.\n\nE2E_STATUS: passed")
        assert status == "passed"

    def test_parse_failed_status(self):
        """Should parse 'failed' status from explicit marker."""
        from orchestrator.e2e_runner import _parse_e2e_status

        status = _parse_e2e_status("Test failed.\n\nE2E_STATUS: failed")
        assert status == "failed"

    def test_infer_passed_from_heuristics(self):
        """Should infer passed status from heuristics when no marker."""
        from orchestrator.e2e_runner import _parse_e2e_status

        status = _parse_e2e_status("All tests pass. ✓ Everything works!")
        assert status == "passed"

    def test_infer_failed_from_heuristics(self):
        """Should infer failed status from heuristics when no marker."""
        from orchestrator.e2e_runner import _parse_e2e_status

        status = _parse_e2e_status("Test failed: assertion error")
        assert status == "failed"

    def test_unclear_when_no_signals(self):
        """Should return unclear when no status signals."""
        from orchestrator.e2e_runner import _parse_e2e_status

        status = _parse_e2e_status("The system is running.")
        assert status == "unclear"


class TestExtractDiagnosis:
    """Test diagnosis extraction from Claude output."""

    def test_extract_diagnosis_from_marker(self):
        """Should extract diagnosis from DIAGNOSIS marker."""
        from orchestrator.e2e_runner import _extract_diagnosis

        output = (
            "E2E_STATUS: failed\n"
            "DIAGNOSIS: The endpoint returns 404 because the route wasn't registered.\n"
            "FIXABLE: yes"
        )
        diagnosis = _extract_diagnosis(output)
        assert diagnosis is not None
        assert "endpoint returns 404" in diagnosis
        assert "route wasn't registered" in diagnosis

    def test_returns_none_when_no_diagnosis(self):
        """Should return None when no diagnosis marker."""
        from orchestrator.e2e_runner import _extract_diagnosis

        output = "E2E_STATUS: failed\nSomething went wrong."
        diagnosis = _extract_diagnosis(output)
        assert diagnosis is None


class TestExtractFixPlan:
    """Test fix plan extraction from Claude output."""

    def test_extract_fix_plan_from_marker(self):
        """Should extract fix plan from FIX_PLAN marker."""
        from orchestrator.e2e_runner import _extract_fix_plan

        output = (
            "DIAGNOSIS: Missing router\n"
            "FIXABLE: yes\n"
            "FIX_PLAN: Add 'app.include_router(new_router)' to main.py line 45"
        )
        fix_plan = _extract_fix_plan(output)
        assert fix_plan is not None
        assert "app.include_router" in fix_plan

    def test_returns_none_when_no_fix_plan(self):
        """Should return None when no FIX_PLAN marker."""
        from orchestrator.e2e_runner import _extract_fix_plan

        output = "DIAGNOSIS: External service is down\nFIXABLE: no"
        fix_plan = _extract_fix_plan(output)
        assert fix_plan is None


class TestDetectFixable:
    """Test fixable detection from Claude output."""

    def test_detect_fixable_yes(self):
        """Should detect fixable when FIXABLE: yes present."""
        from orchestrator.e2e_runner import _detect_fixable

        assert _detect_fixable("FIXABLE: yes") is True

    def test_detect_fixable_no(self):
        """Should detect not fixable when FIXABLE: no present."""
        from orchestrator.e2e_runner import _detect_fixable

        assert _detect_fixable("FIXABLE: no") is False

    def test_detect_fixable_default_false(self):
        """Should default to False when no FIXABLE marker."""
        from orchestrator.e2e_runner import _detect_fixable

        assert _detect_fixable("Some output without FIXABLE") is False


class TestRunE2ETests:
    """Test run_e2e_tests function."""

    @pytest.mark.asyncio
    async def test_executes_e2e_via_claude(self):
        """Should invoke Claude with E2E scenario."""
        from orchestrator.e2e_runner import run_e2e_tests

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("E2E_STATUS: passed")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await run_e2e_tests(
            milestone_id="M5",
            e2e_scenario="Run pytest tests/",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        # Should have invoked Claude
        sandbox.invoke_claude.assert_called_once()
        # Prompt should contain the scenario
        call_kwargs = sandbox.invoke_claude.call_args[1]
        assert "pytest tests/" in call_kwargs["prompt"]
        assert "M5" in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_returns_passed_result(self):
        """Should return E2EResult with passed status."""
        from orchestrator.e2e_runner import run_e2e_tests

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("E2E_STATUS: passed", cost=0.08)
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        result = await run_e2e_tests(
            milestone_id="M5",
            e2e_scenario="Test scenario",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        assert result.status == "passed"
        assert result.cost_usd == 0.08
        assert result.is_fixable is False

    @pytest.mark.asyncio
    async def test_returns_failed_with_diagnosis(self):
        """Should return E2EResult with diagnosis for failures."""
        from orchestrator.e2e_runner import run_e2e_tests

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result(
                "E2E_STATUS: failed\n"
                "DIAGNOSIS: Endpoint returns 404\n"
                "FIXABLE: yes\n"
                "FIX_PLAN: Add router to main.py"
            )
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=span
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        result = await run_e2e_tests(
            milestone_id="M5",
            e2e_scenario="Test scenario",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        assert result.status == "failed"
        assert result.diagnosis is not None
        assert "Endpoint returns 404" in result.diagnosis
        assert result.is_fixable is True
        assert result.fix_suggestion is not None
        assert "router" in result.fix_suggestion

    @pytest.mark.asyncio
    async def test_uses_config_timeout(self):
        """Should use task_timeout_seconds from config."""
        from orchestrator.e2e_runner import run_e2e_tests

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("E2E_STATUS: passed")
        )
        config = OrchestratorConfig(task_timeout_seconds=1200)
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await run_e2e_tests(
            milestone_id="M5",
            e2e_scenario="Test scenario",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        call_kwargs = sandbox.invoke_claude.call_args[1]
        assert call_kwargs["timeout"] == 1200

    @pytest.mark.asyncio
    async def test_uses_limited_max_turns(self):
        """Should use 30 max turns for E2E tests."""
        from orchestrator.e2e_runner import run_e2e_tests

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("E2E_STATUS: passed")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await run_e2e_tests(
            milestone_id="M5",
            e2e_scenario="Test scenario",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        call_kwargs = sandbox.invoke_claude.call_args[1]
        assert call_kwargs["max_turns"] == 30

    @pytest.mark.asyncio
    async def test_records_duration(self):
        """Should record execution duration in result."""
        from orchestrator.e2e_runner import run_e2e_tests

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("E2E_STATUS: passed")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        result = await run_e2e_tests(
            milestone_id="M5",
            e2e_scenario="Test scenario",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_records_raw_output(self):
        """Should store raw Claude output in result."""
        from orchestrator.e2e_runner import run_e2e_tests

        output = "Detailed E2E execution log...\n\nE2E_STATUS: passed"
        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(return_value=make_claude_result(output))
        config = OrchestratorConfig()
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        result = await run_e2e_tests(
            milestone_id="M5",
            e2e_scenario="Test scenario",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        assert result.raw_output == output


class TestRunE2ETestsTracing:
    """Test tracing integration in run_e2e_tests."""

    @pytest.mark.asyncio
    async def test_creates_span_for_e2e_test(self):
        """Should create a span for E2E test execution."""
        from orchestrator.e2e_runner import run_e2e_tests

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("E2E_STATUS: passed")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=span
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await run_e2e_tests(
            milestone_id="M5",
            e2e_scenario="Test scenario",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        tracer.start_as_current_span.assert_called_with("orchestrator.e2e_test")

    @pytest.mark.asyncio
    async def test_sets_span_attributes(self):
        """Should set milestone.id and e2e.status on span."""
        from orchestrator.e2e_runner import run_e2e_tests

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("E2E_STATUS: passed")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=span
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await run_e2e_tests(
            milestone_id="M5",
            e2e_scenario="Test scenario",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        # Check span attributes were set
        attribute_calls = {
            call[0][0]: call[0][1] for call in span.set_attribute.call_args_list
        }
        assert "milestone.id" in attribute_calls
        assert attribute_calls["milestone.id"] == "M5"
        assert "e2e.status" in attribute_calls
        assert attribute_calls["e2e.status"] == "passed"


class TestEstimateTokens:
    """Test token estimation from cost."""

    def test_estimate_tokens_from_cost(self):
        """Should estimate tokens based on cost."""
        from orchestrator.e2e_runner import _estimate_tokens

        # At ~$0.01 per 1000 tokens
        tokens = _estimate_tokens(0.10)
        assert tokens == 10000

    def test_estimate_tokens_zero_cost(self):
        """Should return 0 for zero cost."""
        from orchestrator.e2e_runner import _estimate_tokens

        tokens = _estimate_tokens(0.0)
        assert tokens == 0


class TestApplyE2EFix:
    """Test apply_e2e_fix function."""

    @pytest.mark.asyncio
    async def test_applies_fix_via_claude(self):
        """Should invoke Claude with fix plan."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("FIX_APPLIED: yes")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=span
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await apply_e2e_fix(
            fix_plan="Add 'app.include_router(new_router)' to main.py",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        # Should have invoked Claude
        sandbox.invoke_claude.assert_called_once()
        # Prompt should contain the fix plan
        call_kwargs = sandbox.invoke_claude.call_args[1]
        assert "app.include_router" in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        """Should return True when fix is applied successfully."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
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
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self):
        """Should return False when fix cannot be applied."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
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
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_marker(self):
        """Should return False when output has no FIX_APPLIED marker."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("I made some changes...")
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
            fix_plan="Add router",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_uses_limited_max_turns(self):
        """Should use 20 max turns for fixes."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
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
            fix_plan="Fix something",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        call_kwargs = sandbox.invoke_claude.call_args[1]
        assert call_kwargs["max_turns"] == 20

    @pytest.mark.asyncio
    async def test_uses_fixed_timeout(self):
        """Should use 300 second timeout for fixes."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
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
            fix_plan="Fix something",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        call_kwargs = sandbox.invoke_claude.call_args[1]
        assert call_kwargs["timeout"] == 300


class TestApplyE2EFixTracing:
    """Test tracing integration in apply_e2e_fix."""

    @pytest.mark.asyncio
    async def test_creates_span_for_fix(self):
        """Should create a span for E2E fix execution."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("FIX_APPLIED: yes")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=span
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await apply_e2e_fix(
            fix_plan="Fix something",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        tracer.start_as_current_span.assert_called_with("orchestrator.e2e_fix")

    @pytest.mark.asyncio
    async def test_sets_fix_plan_attribute(self):
        """Should set fix.plan attribute on span (truncated)."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("FIX_APPLIED: yes")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=span
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await apply_e2e_fix(
            fix_plan="Add router to main.py line 45",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        attribute_calls = {
            call[0][0]: call[0][1] for call in span.set_attribute.call_args_list
        }
        assert "fix.plan" in attribute_calls
        assert "Add router" in attribute_calls["fix.plan"]

    @pytest.mark.asyncio
    async def test_truncates_long_fix_plan(self):
        """Should truncate fix.plan attribute to 200 chars."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("FIX_APPLIED: yes")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=span
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        long_fix_plan = "A" * 500

        await apply_e2e_fix(
            fix_plan=long_fix_plan,
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        attribute_calls = {
            call[0][0]: call[0][1] for call in span.set_attribute.call_args_list
        }
        assert len(attribute_calls["fix.plan"]) == 200

    @pytest.mark.asyncio
    async def test_sets_fix_success_attribute(self):
        """Should set fix.success attribute on span."""
        from orchestrator.e2e_runner import apply_e2e_fix

        sandbox = MagicMock()
        sandbox.invoke_claude = AsyncMock(
            return_value=make_claude_result("FIX_APPLIED: yes")
        )
        config = OrchestratorConfig()
        tracer = MagicMock()
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__ = MagicMock(
            return_value=span
        )
        tracer.start_as_current_span.return_value.__exit__ = MagicMock(
            return_value=False
        )

        await apply_e2e_fix(
            fix_plan="Fix something",
            sandbox=sandbox,
            config=config,
            tracer=tracer,
        )

        attribute_calls = {
            call[0][0]: call[0][1] for call in span.set_attribute.call_args_list
        }
        assert "fix.success" in attribute_calls
        assert attribute_calls["fix.success"] is True

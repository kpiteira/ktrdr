"""Tests for HaikuBrain - Haiku-powered orchestration intelligence.

These tests verify that HaikuBrain correctly:
- Extracts tasks from milestone plans (ignoring code blocks)
- Interprets task execution results (completed/failed/needs_help)
- Decides retry vs escalate based on attempt history
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from ktrdr.llm.haiku_brain import (
    ExtractedTask,
    HaikuBrain,
    InterpretationResult,
    RetryDecision,
)


class TestExtractTasks:
    """Tests for HaikuBrain.extract_tasks()."""

    def test_simple_plan_with_two_tasks(self) -> None:
        """Simple plan with 2 tasks should extract both."""
        plan_content = """
# Milestone 1: Feature X

## Task 1.1: Create data model

**Description:** Create the data model for the feature.

## Task 1.2: Add API endpoint

**Description:** Add the API endpoint for the feature.
"""
        mock_response = json.dumps([
            {"id": "1.1", "title": "Create data model", "description": "Create the data model for the feature."},
            {"id": "1.2", "title": "Add API endpoint", "description": "Add the API endpoint for the feature."},
        ])

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            tasks = brain.extract_tasks(plan_content)

        assert len(tasks) == 2
        assert tasks[0].id == "1.1"
        assert tasks[0].title == "Create data model"
        assert tasks[1].id == "1.2"
        assert tasks[1].title == "Add API endpoint"

    def test_ignores_tasks_inside_code_blocks(self) -> None:
        """Tasks inside fenced code blocks should NOT be extracted."""
        plan_content = """
# Milestone 1: Feature X

## Task 1.1: Real Task

**Description:** This is a real task to execute.

## E2E Example

Here's what a plan looks like:

```markdown
## Task 2.1: Fake Task in Code Block

**Description:** This should NOT be extracted.

## Task 2.2: Another Fake Task

**Description:** Also should NOT be extracted.
```

The orchestrator should only find Task 1.1.
"""
        mock_response = json.dumps([
            {"id": "1.1", "title": "Real Task", "description": "This is a real task to execute."},
        ])

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            tasks = brain.extract_tasks(plan_content)

        assert len(tasks) == 1
        assert tasks[0].id == "1.1"
        assert tasks[0].title == "Real Task"

    def test_ignores_tasks_in_e2e_example_section(self) -> None:
        """Tasks mentioned as examples in E2E sections should be ignored."""
        plan_content = """
# Milestone 1: Feature X

## Task 1.1: Implement Feature

**Description:** Implement the main feature.

## Task 1.2: Write Tests

**Description:** Write tests for the feature.

## E2E Test Scenario

When running this milestone, you'll see output like:

```
Starting task 2.1: Example Task
  → Reading files...
Task 2.1: COMPLETED
```

This is just an example of expected output.
"""
        mock_response = json.dumps([
            {"id": "1.1", "title": "Implement Feature", "description": "Implement the main feature."},
            {"id": "1.2", "title": "Write Tests", "description": "Write tests for the feature."},
        ])

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            tasks = brain.extract_tasks(plan_content)

        assert len(tasks) == 2
        assert all(t.id in ["1.1", "1.2"] for t in tasks)

    def test_empty_plan_returns_empty_list(self) -> None:
        """Empty or taskless plan should return empty list."""
        plan_content = """
# Overview

This document describes the architecture but contains no tasks.

## Background

Some background information.
"""
        mock_response = json.dumps([])

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            tasks = brain.extract_tasks(plan_content)

        assert tasks == []

    def test_malformed_json_response_raises_error(self) -> None:
        """Malformed JSON response should raise a clear error."""
        plan_content = "# Some Plan\n\n## Task 1.1: Test"
        malformed_response = "This is not JSON at all"

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=malformed_response):
            with pytest.raises(ValueError, match="Failed to parse tasks from Haiku response"):
                brain.extract_tasks(plan_content)

    def test_json_wrapped_in_markdown_code_block(self) -> None:
        """JSON wrapped in markdown code block should be extracted correctly."""
        plan_content = "# Some Plan\n\n## Task 1.1: Test"
        # Haiku sometimes wraps JSON in markdown code blocks
        wrapped_response = """Here are the tasks:

```json
[
  {"id": "1.1", "title": "Test Task", "description": "A test task"}
]
```
"""
        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=wrapped_response):
            tasks = brain.extract_tasks(plan_content)

        assert len(tasks) == 1
        assert tasks[0].id == "1.1"

    def test_json_with_escaped_quotes_in_strings(self) -> None:
        """JSON with escaped quotes in strings should be parsed correctly."""
        plan_content = "# Some Plan"
        # JSON with escaped quotes inside string values
        response_with_escapes = r'[{"id": "1.1", "title": "Task with \"quoted\" word", "description": "A \"complex\" description"}]'

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=response_with_escapes):
            tasks = brain.extract_tasks(plan_content)

        assert len(tasks) == 1
        assert tasks[0].id == "1.1"
        assert tasks[0].title == 'Task with "quoted" word'
        assert tasks[0].description == 'A "complex" description'

    def test_uses_correct_model(self) -> None:
        """HaikuBrain should use the specified model."""
        brain = HaikuBrain(model="claude-haiku-4-5-20251001")
        assert brain.model == "claude-haiku-4-5-20251001"

        brain_custom = HaikuBrain(model="claude-sonnet-4-20250514")
        assert brain_custom.model == "claude-sonnet-4-20250514"


class TestInvokeHaiku:
    """Tests for the Haiku CLI invocation."""

    def test_invoke_haiku_calls_claude_cli_correctly(self) -> None:
        """_invoke_haiku should call Claude CLI with correct arguments."""
        brain = HaikuBrain()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '[]'

        with patch("ktrdr.llm.haiku_brain.find_claude_cli", return_value="/usr/local/bin/claude"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                brain._invoke_haiku("test prompt")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "/usr/local/bin/claude"
        assert "--model" in call_args
        assert "claude-haiku-4-5-20251001" in call_args
        assert "--print" in call_args
        assert "--no-session-persistence" in call_args
        assert "--allowedTools" in call_args
        assert "" in call_args  # Empty string for allowed tools
        assert "-p" in call_args
        assert "test prompt" in call_args

    def test_invoke_haiku_raises_on_cli_not_found(self) -> None:
        """_invoke_haiku should raise if Claude CLI is not found."""
        brain = HaikuBrain()

        with patch("ktrdr.llm.haiku_brain.find_claude_cli", return_value=None):
            with pytest.raises(RuntimeError, match="Claude CLI not found"):
                brain._invoke_haiku("test prompt")

    def test_invoke_haiku_raises_on_cli_failure(self) -> None:
        """_invoke_haiku should raise if Claude CLI returns non-zero."""
        brain = HaikuBrain()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Authentication failed"

        with patch("ktrdr.llm.haiku_brain.find_claude_cli", return_value="/usr/local/bin/claude"):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(RuntimeError, match="Claude CLI failed"):
                    brain._invoke_haiku("test prompt")


class TestExtractedTask:
    """Tests for the ExtractedTask dataclass."""

    def test_extracted_task_fields(self) -> None:
        """ExtractedTask should have id, title, description fields."""
        task = ExtractedTask(
            id="1.1",
            title="Create data model",
            description="Create the data model for the feature.",
        )
        assert task.id == "1.1"
        assert task.title == "Create data model"
        assert task.description == "Create the data model for the feature."


class TestInterpretResult:
    """Tests for HaikuBrain.interpret_result()."""

    def test_completed_task_with_summary(self) -> None:
        """Output with task completion summary should return status=completed."""
        output = """
## Task Complete: 1.1

**What was implemented:**
- Created the data model

**Files changed:**
- models.py (created)

All tests passing.
"""
        mock_response = json.dumps({
            "status": "completed",
            "summary": "Created data model with all tests passing",
            "error": None,
            "question": None,
            "options": None,
            "recommendation": None,
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.interpret_result(output)

        assert result.status == "completed"
        assert result.summary == "Created data model with all tests passing"
        assert result.error is None
        assert result.question is None

    def test_failed_task_with_error(self) -> None:
        """Output with unresolved error should return status=failed."""
        output = """
I attempted to implement the feature but encountered an error I couldn't resolve.

Error: ModuleNotFoundError: No module named 'some_library'

I tried installing it but it's not available in this environment.
The task cannot be completed without this dependency.
"""
        mock_response = json.dumps({
            "status": "failed",
            "summary": "Failed due to missing dependency",
            "error": "ModuleNotFoundError: No module named 'some_library'",
            "question": None,
            "options": None,
            "recommendation": None,
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.interpret_result(output)

        assert result.status == "failed"
        assert "dependency" in result.summary.lower() or "missing" in result.summary.lower()
        assert result.error is not None
        assert "some_library" in result.error

    def test_needs_help_with_ask_user_question(self) -> None:
        """Output with AskUserQuestion tool call should return status=needs_help."""
        output = """
I need clarification before proceeding.

<tool_call>
<name>AskUserQuestion</name>
<parameters>
{"question": "Which authentication method should I use?", "options": ["JWT tokens", "API keys", "OAuth"]}
</parameters>
</tool_call>

I recommend option A (JWT) as it matches the existing user service.
"""
        mock_response = json.dumps({
            "status": "needs_help",
            "summary": "Asking about authentication method",
            "error": None,
            "question": "Which authentication method should I use?",
            "options": ["JWT tokens", "API keys", "OAuth"],
            "recommendation": "JWT tokens (matches existing user service)",
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.interpret_result(output)

        assert result.status == "needs_help"
        assert result.question is not None
        assert "authentication" in result.question.lower()
        assert result.options is not None
        assert len(result.options) == 3
        assert result.recommendation is not None

    def test_ambiguous_output_returns_needs_help(self) -> None:
        """Ambiguous output should conservatively return status=needs_help."""
        output = """
I've made some progress on the task but I'm not sure if the approach is correct.

The implementation works but there might be edge cases I haven't considered.
Should I continue with this approach?
"""
        mock_response = json.dumps({
            "status": "needs_help",
            "summary": "Uncertain about approach, seeking confirmation",
            "error": None,
            "question": "Should I continue with this approach?",
            "options": None,
            "recommendation": None,
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.interpret_result(output)

        assert result.status == "needs_help"
        assert result.question is not None

    def test_large_output_not_truncated(self) -> None:
        """Large output (10k+ chars) should be sent without truncation."""
        # Create large output > 10k characters
        large_output = "Line of text\n" * 1000  # ~13k chars
        assert len(large_output) > 10000

        mock_response = json.dumps({
            "status": "completed",
            "summary": "Task completed successfully",
            "error": None,
            "question": None,
            "options": None,
            "recommendation": None,
        })

        brain = HaikuBrain()
        captured_prompt = None

        def capture_invoke(prompt: str) -> str:
            nonlocal captured_prompt
            captured_prompt = prompt
            return mock_response

        with patch.object(brain, "_invoke_haiku", side_effect=capture_invoke):
            result = brain.interpret_result(large_output)

        # Verify full output was included in prompt (not truncated)
        assert captured_prompt is not None
        assert large_output in captured_prompt
        assert result.status == "completed"

    def test_json_parsing_error_returns_needs_help(self) -> None:
        """When JSON parsing fails, should return needs_help for safety."""
        output = "Some task output"
        invalid_response = "This is not valid JSON at all"

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=invalid_response):
            result = brain.interpret_result(output)

        # Conservative: when uncertain, treat as needs_help
        assert result.status == "needs_help"

    def test_completed_without_explicit_marker(self) -> None:
        """Task without STATUS marker but clear completion should be detected."""
        output = """
I've implemented the feature as requested.

Changes made:
1. Created models/user.py with User dataclass
2. Added validation for email format
3. Wrote 5 unit tests - all passing

The implementation follows the existing patterns in the codebase.
"""
        mock_response = json.dumps({
            "status": "completed",
            "summary": "Created User model with validation and tests",
            "error": None,
            "question": None,
            "options": None,
            "recommendation": None,
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.interpret_result(output)

        assert result.status == "completed"
        assert "tests" in result.summary.lower() or "user" in result.summary.lower()


class TestInterpretationResult:
    """Tests for the InterpretationResult dataclass."""

    def test_interpretation_result_fields(self) -> None:
        """InterpretationResult should have all required fields."""
        result = InterpretationResult(
            status="completed",
            summary="Task completed successfully",
            error=None,
            question=None,
            options=None,
            recommendation=None,
        )
        assert result.status == "completed"
        assert result.summary == "Task completed successfully"
        assert result.error is None
        assert result.question is None
        assert result.options is None
        assert result.recommendation is None

    def test_interpretation_result_with_needs_help(self) -> None:
        """InterpretationResult should store question and options for needs_help."""
        result = InterpretationResult(
            status="needs_help",
            summary="Awaiting user decision",
            error=None,
            question="Which approach should I use?",
            options=["Option A", "Option B"],
            recommendation="Option A",
        )
        assert result.status == "needs_help"
        assert result.question == "Which approach should I use?"
        assert result.options == ["Option A", "Option B"]
        assert result.recommendation == "Option A"

    def test_interpretation_result_with_failed(self) -> None:
        """InterpretationResult should store error for failed status."""
        result = InterpretationResult(
            status="failed",
            summary="Task failed due to import error",
            error="ImportError: No module named 'xyz'",
            question=None,
            options=None,
            recommendation=None,
        )
        assert result.status == "failed"
        assert result.error == "ImportError: No module named 'xyz'"


class TestRetryDecision:
    """Tests for the RetryDecision dataclass."""

    def test_retry_decision_with_retry(self) -> None:
        """RetryDecision should store decision, reason, and guidance when retrying."""
        decision = RetryDecision(
            decision="retry",
            reason="Error seems transient, first attempt",
            guidance_for_retry="Try installing the missing dependency first",
        )
        assert decision.decision == "retry"
        assert decision.reason == "Error seems transient, first attempt"
        assert decision.guidance_for_retry == "Try installing the missing dependency first"

    def test_retry_decision_with_escalate(self) -> None:
        """RetryDecision should have null guidance when escalating."""
        decision = RetryDecision(
            decision="escalate",
            reason="Same error 3 times, stuck in loop",
            guidance_for_retry=None,
        )
        assert decision.decision == "escalate"
        assert decision.reason == "Same error 3 times, stuck in loop"
        assert decision.guidance_for_retry is None


class TestShouldRetryOrEscalate:
    """Tests for HaikuBrain.should_retry_or_escalate()."""

    def test_first_failure_with_fixable_error_returns_retry(self) -> None:
        """First failure with fixable error (import error) should return retry with guidance."""
        mock_response = json.dumps({
            "decision": "retry",
            "reason": "First attempt, error is fixable",
            "guidance_for_retry": "Try adding the missing import at the top of the file",
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.should_retry_or_escalate(
                task_id="1.1",
                task_title="Create data model",
                attempt_history=["Failed: ImportError - no module named pandas"],
                attempt_count=1,
            )

        assert result.decision == "retry"
        assert result.guidance_for_retry is not None
        assert len(result.guidance_for_retry) > 0

    def test_same_error_three_times_returns_escalate(self) -> None:
        """Same error repeated 3 times should return escalate (stuck in loop)."""
        mock_response = json.dumps({
            "decision": "escalate",
            "reason": "Same error 3 times, stuck in a loop",
            "guidance_for_retry": None,
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.should_retry_or_escalate(
                task_id="1.1",
                task_title="Create data model",
                attempt_history=[
                    "Failed: ImportError - no module named pandas",
                    "Failed: ImportError - no module named pandas",
                    "Failed: ImportError - no module named pandas",
                ],
                attempt_count=3,
            )

        assert result.decision == "escalate"
        assert result.guidance_for_retry is None

    def test_different_errors_each_time_returns_retry(self) -> None:
        """Different errors each attempt means progress, should retry."""
        mock_response = json.dumps({
            "decision": "retry",
            "reason": "Errors are different, making progress",
            "guidance_for_retry": "The import error was fixed, now focus on the type error",
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.should_retry_or_escalate(
                task_id="1.1",
                task_title="Create data model",
                attempt_history=[
                    "Failed: ImportError - no module named pandas",
                    "Failed: TypeError - expected str, got int",
                ],
                attempt_count=2,
            )

        assert result.decision == "retry"
        assert result.guidance_for_retry is not None

    def test_clarification_needed_returns_escalate(self) -> None:
        """Error saying 'I need clarification' should escalate."""
        mock_response = json.dumps({
            "decision": "escalate",
            "reason": "Claude explicitly needs human input",
            "guidance_for_retry": None,
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.should_retry_or_escalate(
                task_id="1.1",
                task_title="Create data model",
                attempt_history=[
                    "Failed: I need clarification on which database to use",
                ],
                attempt_count=1,
            )

        assert result.decision == "escalate"

    def test_architecture_issue_returns_escalate(self) -> None:
        """Error mentioning architecture/design issue should escalate."""
        mock_response = json.dumps({
            "decision": "escalate",
            "reason": "This is a design issue, not a coding bug",
            "guidance_for_retry": None,
        })

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.should_retry_or_escalate(
                task_id="1.1",
                task_title="Create data model",
                attempt_history=[
                    "Failed: The current architecture doesn't support this pattern. We need to redesign the data layer.",
                ],
                attempt_count=1,
            )

        assert result.decision == "escalate"

    def test_prompt_includes_all_attempt_history(self) -> None:
        """Prompt to Haiku should include all attempt history formatted correctly."""
        mock_response = json.dumps({
            "decision": "retry",
            "reason": "Still making progress",
            "guidance_for_retry": "Keep trying",
        })

        brain = HaikuBrain()
        captured_prompt = None

        def capture_invoke(prompt: str) -> str:
            nonlocal captured_prompt
            captured_prompt = prompt
            return mock_response

        with patch.object(brain, "_invoke_haiku", side_effect=capture_invoke):
            brain.should_retry_or_escalate(
                task_id="2.3",
                task_title="Add API endpoint",
                attempt_history=[
                    "Attempt 1 error",
                    "Attempt 2 error",
                ],
                attempt_count=2,
            )

        assert captured_prompt is not None
        assert "2.3" in captured_prompt
        assert "Add API endpoint" in captured_prompt
        assert "Attempt 1: Attempt 1 error" in captured_prompt
        assert "Attempt 2: Attempt 2 error" in captured_prompt
        assert "Current attempt count: 2" in captured_prompt

    def test_json_parsing_error_returns_safe_default(self) -> None:
        """When JSON parsing fails, should return a safe escalate decision."""
        invalid_response = "This is not valid JSON"

        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", return_value=invalid_response):
            result = brain.should_retry_or_escalate(
                task_id="1.1",
                task_title="Create data model",
                attempt_history=["Some error"],
                attempt_count=1,
            )

        # Conservative: escalate when uncertain
        assert result.decision == "escalate"
        assert "parse" in result.reason.lower() or "failed" in result.reason.lower()

    def test_haiku_invocation_failure_returns_escalate(self) -> None:
        """When Haiku invocation fails, should return escalate for safety."""
        brain = HaikuBrain()
        with patch.object(brain, "_invoke_haiku", side_effect=RuntimeError("CLI failed")):
            result = brain.should_retry_or_escalate(
                task_id="1.1",
                task_title="Create data model",
                attempt_history=["Some error"],
                attempt_count=1,
            )

        assert result.decision == "escalate"
        assert "failed" in result.reason.lower() or "error" in result.reason.lower()

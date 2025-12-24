"""Tests for HaikuBrain - Haiku-powered orchestration intelligence.

These tests verify that HaikuBrain correctly extracts tasks from milestone plans,
particularly handling the edge case of ignoring tasks inside code blocks.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.haiku_brain import ExtractedTask, HaikuBrain


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

        with patch("orchestrator.haiku_brain.find_claude_cli", return_value="/usr/local/bin/claude"):
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

        with patch("orchestrator.haiku_brain.find_claude_cli", return_value=None):
            with pytest.raises(RuntimeError, match="Claude CLI not found"):
                brain._invoke_haiku("test prompt")

    def test_invoke_haiku_raises_on_cli_failure(self) -> None:
        """_invoke_haiku should raise if Claude CLI returns non-zero."""
        brain = HaikuBrain()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Authentication failed"

        with patch("orchestrator.haiku_brain.find_claude_cli", return_value="/usr/local/bin/claude"):
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

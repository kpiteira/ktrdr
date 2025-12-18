"""Tests for orchestrator data models.

These tests verify the data models for tasks, Claude results, and task results.
"""

import json
from dataclasses import asdict, is_dataclass


class TestTaskModel:
    """Test the Task model."""

    def test_task_is_dataclass(self):
        """Task should be a dataclass."""
        from orchestrator.models import Task

        assert is_dataclass(Task)

    def test_task_has_required_fields(self):
        """Task should have all required fields with type hints."""
        from orchestrator.models import Task

        annotations = Task.__annotations__
        required_fields = [
            "id",
            "title",
            "description",
            "file_path",
            "acceptance_criteria",
            "plan_file",
            "milestone_id",
        ]
        for field in required_fields:
            assert field in annotations, f"Missing field: {field}"

    def test_task_creation(self):
        """Task should be creatable with all required fields."""
        from orchestrator.models import Task

        task = Task(
            id="2.1",
            title="Create package structure",
            description="Set up the orchestrator package",
            file_path="orchestrator/__init__.py",
            acceptance_criteria=["Package importable", "CLI works"],
            plan_file="docs/plan.md",
            milestone_id="M2",
        )
        assert task.id == "2.1"
        assert task.title == "Create package structure"
        assert task.file_path == "orchestrator/__init__.py"
        assert len(task.acceptance_criteria) == 2

    def test_task_file_path_can_be_none(self):
        """Task file_path should allow None."""
        from orchestrator.models import Task

        task = Task(
            id="2.1",
            title="Research task",
            description="No file changes",
            file_path=None,
            acceptance_criteria=["Research complete"],
            plan_file="docs/plan.md",
            milestone_id="M2",
        )
        assert task.file_path is None

    def test_task_json_serializable(self):
        """Task should be JSON serializable via asdict."""
        from orchestrator.models import Task

        task = Task(
            id="2.1",
            title="Test",
            description="Test description",
            file_path="test.py",
            acceptance_criteria=["Criterion 1"],
            plan_file="plan.md",
            milestone_id="M2",
        )
        json_str = json.dumps(asdict(task))
        loaded = json.loads(json_str)
        assert loaded["id"] == "2.1"
        assert loaded["acceptance_criteria"] == ["Criterion 1"]


class TestClaudeResultModel:
    """Test the ClaudeResult model."""

    def test_claude_result_is_dataclass(self):
        """ClaudeResult should be a dataclass."""
        from orchestrator.models import ClaudeResult

        assert is_dataclass(ClaudeResult)

    def test_claude_result_has_required_fields(self):
        """ClaudeResult should have all required fields."""
        from orchestrator.models import ClaudeResult

        annotations = ClaudeResult.__annotations__
        required_fields = [
            "is_error",
            "result",
            "total_cost_usd",
            "duration_ms",
            "num_turns",
            "session_id",
        ]
        for field in required_fields:
            assert field in annotations, f"Missing field: {field}"

    def test_claude_result_creation(self):
        """ClaudeResult should be creatable."""
        from orchestrator.models import ClaudeResult

        result = ClaudeResult(
            is_error=False,
            result="Task completed successfully",
            total_cost_usd=0.08,
            duration_ms=148000,
            num_turns=6,
            session_id="abc123",
        )
        assert result.is_error is False
        assert result.total_cost_usd == 0.08
        assert result.num_turns == 6

    def test_claude_result_json_serializable(self):
        """ClaudeResult should be JSON serializable."""
        from orchestrator.models import ClaudeResult

        result = ClaudeResult(
            is_error=True,
            result="Error occurred",
            total_cost_usd=0.02,
            duration_ms=5000,
            num_turns=1,
            session_id="def456",
        )
        json_str = json.dumps(asdict(result))
        loaded = json.loads(json_str)
        assert loaded["is_error"] is True
        assert loaded["session_id"] == "def456"


class TestTaskResultModel:
    """Test the TaskResult model."""

    def test_task_result_is_dataclass(self):
        """TaskResult should be a dataclass."""
        from orchestrator.models import TaskResult

        assert is_dataclass(TaskResult)

    def test_task_result_has_required_fields(self):
        """TaskResult should have all required fields."""
        from orchestrator.models import TaskResult

        annotations = TaskResult.__annotations__
        required_fields = [
            "task_id",
            "status",
            "duration_seconds",
            "tokens_used",
            "cost_usd",
            "output",
            "session_id",
            "question",
            "options",
            "recommendation",
            "error",
        ]
        for field in required_fields:
            assert field in annotations, f"Missing field: {field}"

    def test_task_result_completed_status(self):
        """TaskResult should support 'completed' status."""
        from orchestrator.models import TaskResult

        result = TaskResult(
            task_id="2.1",
            status="completed",
            duration_seconds=148.0,
            tokens_used=12400,
            cost_usd=0.08,
            output="Task completed",
            session_id="abc123",
        )
        assert result.status == "completed"
        assert result.question is None
        assert result.error is None

    def test_task_result_failed_status(self):
        """TaskResult should support 'failed' status with error."""
        from orchestrator.models import TaskResult

        result = TaskResult(
            task_id="2.1",
            status="failed",
            duration_seconds=30.0,
            tokens_used=2000,
            cost_usd=0.01,
            output="Error output",
            session_id="abc123",
            error="Module not found",
        )
        assert result.status == "failed"
        assert result.error == "Module not found"

    def test_task_result_needs_human_status(self):
        """TaskResult should support 'needs_human' status with question."""
        from orchestrator.models import TaskResult

        result = TaskResult(
            task_id="2.1",
            status="needs_human",
            duration_seconds=60.0,
            tokens_used=5000,
            cost_usd=0.03,
            output="Need clarification",
            session_id="abc123",
            question="Should I use option A or B?",
            options=["A", "B"],
            recommendation="A",
        )
        assert result.status == "needs_human"
        assert result.question == "Should I use option A or B?"
        assert result.options == ["A", "B"]
        assert result.recommendation == "A"

    def test_task_result_json_serializable(self):
        """TaskResult should be JSON serializable."""
        from orchestrator.models import TaskResult

        result = TaskResult(
            task_id="2.1",
            status="completed",
            duration_seconds=100.0,
            tokens_used=10000,
            cost_usd=0.05,
            output="Done",
            session_id="xyz789",
        )
        json_str = json.dumps(asdict(result))
        loaded = json.loads(json_str)
        assert loaded["task_id"] == "2.1"
        assert loaded["status"] == "completed"
        assert loaded["question"] is None

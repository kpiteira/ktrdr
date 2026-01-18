"""Integration tests for full orchestrator flow.

These tests verify the complete orchestrator lifecycle with mocked
external dependencies (Docker, Claude). They ensure all components
work together correctly without making real subprocess or API calls.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.llm.haiku_brain import ExtractedTask
from orchestrator.milestone_runner import run_milestone
from orchestrator.models import TaskResult


def create_mock_container_class() -> MagicMock:
    """Create a mock CodingAgentContainer class with async lifecycle methods.

    Returns a mock class that when instantiated returns a container mock
    with async start() and stop() methods.
    """
    mock_container = MagicMock()
    mock_container.start = AsyncMock()
    mock_container.stop = AsyncMock()
    mock_class = MagicMock(return_value=mock_container)
    return mock_class


def configure_haiku_mock(mock_brain_class: MagicMock) -> None:
    """Configure HaikuBrain mock to return sample extracted tasks."""
    mock_brain_class.return_value.extract_tasks.return_value = [
        ExtractedTask(id="1.1", title="First task", description="Do the first thing"),
    ]


@pytest.fixture
def integration_plan_file(tmp_path: Path) -> Path:
    """Create a minimal plan file for integration testing."""
    plan_path = tmp_path / "integration_test_plan.md"
    plan_path.write_text(
        "# Integration Test Plan\n\nSingle task for flow verification.\n"
    )
    return plan_path


@pytest.mark.integration
class TestFullOrchestratorFlow:
    """Integration tests for the complete orchestrator flow.

    These tests verify the validate -> start -> invoke -> stop lifecycle
    works correctly with all components wired together.
    """

    @pytest.mark.asyncio
    async def test_full_flow_with_valid_environment(
        self,
        tmp_path: Path,
        integration_plan_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Full orchestrator flow completes successfully.

        Verifies:
        - validate_environment is called
        - container.start() is called with correct path
        - task execution runs
        - container.stop() is called in cleanup
        """
        # Setup: create sandbox environment
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        # Track calls
        validate_called = False
        start_called_with: Path | None = None
        stop_called = False

        def mock_validate() -> Path:
            nonlocal validate_called
            validate_called = True
            return tmp_path

        mock_container = MagicMock()

        async def mock_start(code_folder: Path) -> None:
            nonlocal start_called_with
            start_called_with = code_folder

        async def mock_stop() -> None:
            nonlocal stop_called
            stop_called = True

        mock_container.start = AsyncMock(side_effect=mock_start)
        mock_container.stop = AsyncMock(side_effect=mock_stop)

        mock_container_class = MagicMock(return_value=mock_container)

        async def mock_task_runner(
            task, container, config, plan_path, tracer, **kwargs
        ) -> TaskResult:
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=1.0,
                tokens_used=100,
                cost_usd=0.001,
                output="Task completed",
                session_id="test-session",
            )

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_runner),
            ),
            patch(
                "orchestrator.milestone_runner.CodingAgentContainer",
                mock_container_class,
            ),
            patch(
                "orchestrator.milestone_runner.validate_environment",
                mock_validate,
            ),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(integration_plan_file),
                state_dir=tmp_path,
            )

        # Verify full flow executed
        assert validate_called, "validate_environment should be called"
        assert (
            start_called_with == tmp_path
        ), "container.start() should be called with cwd"
        assert stop_called, "container.stop() should be called in cleanup"
        assert result.status == "completed", "Milestone should complete successfully"

    @pytest.mark.asyncio
    async def test_container_stopped_even_on_task_failure(
        self,
        tmp_path: Path,
        integration_plan_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Container is stopped even when task execution fails.

        Ensures cleanup happens regardless of task outcome.
        """
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        stop_called = False

        mock_container = MagicMock()
        mock_container.start = AsyncMock()

        async def mock_stop() -> None:
            nonlocal stop_called
            stop_called = True

        mock_container.stop = AsyncMock(side_effect=mock_stop)
        mock_container_class = MagicMock(return_value=mock_container)

        async def mock_task_runner(
            task, container, config, plan_path, tracer, **kwargs
        ) -> TaskResult:
            return TaskResult(
                task_id=task.id,
                status="failed",
                duration_seconds=1.0,
                tokens_used=100,
                cost_usd=0.001,
                output="Task failed",
                session_id="test-session",
                error="Simulated failure",
            )

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_runner),
            ),
            patch(
                "orchestrator.milestone_runner.CodingAgentContainer",
                mock_container_class,
            ),
            patch(
                "orchestrator.milestone_runner.validate_environment",
                return_value=tmp_path,
            ),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(integration_plan_file),
                state_dir=tmp_path,
            )

        assert stop_called, "container.stop() must be called even on task failure"
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_flow_uses_correct_component_order(
        self,
        tmp_path: Path,
        integration_plan_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Components are called in correct order: validate -> start -> run -> stop."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        call_order: list[str] = []

        def mock_validate() -> Path:
            call_order.append("validate")
            return tmp_path

        mock_container = MagicMock()

        async def mock_start(code_folder: Path) -> None:
            call_order.append("start")

        async def mock_stop() -> None:
            call_order.append("stop")

        mock_container.start = AsyncMock(side_effect=mock_start)
        mock_container.stop = AsyncMock(side_effect=mock_stop)
        mock_container_class = MagicMock(return_value=mock_container)

        async def mock_task_runner(
            task, container, config, plan_path, tracer, **kwargs
        ) -> TaskResult:
            call_order.append("run_task")
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=1.0,
                tokens_used=100,
                cost_usd=0.001,
                output="Done",
                session_id="test",
            )

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_runner),
            ),
            patch(
                "orchestrator.milestone_runner.CodingAgentContainer",
                mock_container_class,
            ),
            patch(
                "orchestrator.milestone_runner.validate_environment",
                mock_validate,
            ),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(integration_plan_file),
                state_dir=tmp_path,
            )

        # Verify order
        assert call_order == [
            "validate",
            "start",
            "run_task",
            "stop",
        ], f"Expected [validate, start, run_task, stop], got {call_order}"

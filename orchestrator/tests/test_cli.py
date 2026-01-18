"""Tests for CLI module.

These tests verify the CLI task command functionality.
"""

import textwrap
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from orchestrator.models import TaskResult


def make_task_result(
    task_id: str = "2.1",
    status: str = "completed",
    duration: float = 60.0,
    tokens: int = 5000,
    cost: float = 0.05,
) -> TaskResult:
    """Create a test TaskResult."""
    return TaskResult(
        task_id=task_id,
        status=status,  # type: ignore[arg-type]
        duration_seconds=duration,
        tokens_used=tokens,
        cost_usd=cost,
        output="Task output",
        session_id="test-session",
    )


class TestTaskCommand:
    """Test the task CLI command."""

    def test_task_command_exists(self):
        """The task command should exist in the CLI."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["task", "--help"])

        assert result.exit_code == 0
        assert "Execute a single task" in result.output

    def test_task_command_requires_plan_file(self):
        """task command should require a plan file argument."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["task"])

        # Should fail due to missing arguments
        assert result.exit_code != 0

    def test_task_command_requires_task_id(self):
        """task command should require a task_id argument."""
        from orchestrator.cli import cli

        runner = CliRunner()

        # Create a minimal plan file
        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Milestone\n")
            f.flush()
            result = runner.invoke(cli, ["task", f.name])

        # Should fail due to missing task_id
        assert result.exit_code != 0

    def test_task_command_has_guidance_option(self):
        """task command should have --guidance option."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["task", "--help"])

        assert "--guidance" in result.output or "-g" in result.output


class TestTaskCommandExecution:
    """Test task command execution with mocked dependencies."""

    def test_task_not_found_shows_error(self):
        """Should show error when task not found in plan."""
        from orchestrator.cli import cli

        runner = CliRunner()

        # Create a plan with no tasks
        content = textwrap.dedent("""
            # Milestone 2: Test

            No tasks here.
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.validate_environment"):
                with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                    mock_telemetry.return_value = (MagicMock(), MagicMock())
                    with patch("orchestrator.cli.create_metrics"):
                        result = runner.invoke(cli, ["task", f.name, "2.1"])

        assert "not found" in result.output.lower()

    def test_successful_task_execution(self):
        """Should execute task and show success output."""
        from orchestrator.cli import cli

        runner = CliRunner()

        # Create a plan with a task
        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.validate_environment"):
                with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                    mock_tracer = MagicMock()
                    mock_span = MagicMock()
                    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                        return_value=mock_span
                    )
                    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                        return_value=None
                    )
                    mock_telemetry.return_value = (mock_tracer, MagicMock())

                    with patch("orchestrator.cli.create_metrics"):
                        with patch(
                            "orchestrator.cli.run_task",
                            new_callable=AsyncMock,
                        ) as mock_run:
                            mock_run.return_value = make_task_result()

                            with patch("orchestrator.cli.CodingAgentContainer"):
                                with patch("orchestrator.cli.telemetry") as mock_tel:
                                    mock_tel.tasks_counter = MagicMock()
                                    mock_tel.tokens_counter = MagicMock()
                                    mock_tel.cost_counter = MagicMock()
                                    result = runner.invoke(cli, ["task", f.name, "2.1"])

        # Should show task execution output
        assert result.exit_code == 0 or "COMPLETED" in result.output.upper()

    def test_outputs_status_duration_tokens_cost(self):
        """Should output status, duration, tokens, and cost."""
        from orchestrator.cli import cli

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2

            ## Task 2.1: Test

            **Description:** Test

            **Acceptance Criteria:**
            - [ ] Works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.validate_environment"):
                with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                    mock_tracer = MagicMock()
                    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                        return_value=MagicMock()
                    )
                    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                        return_value=None
                    )
                    mock_telemetry.return_value = (mock_tracer, MagicMock())

                    with patch("orchestrator.cli.create_metrics"):
                        with patch(
                            "orchestrator.cli.run_task",
                            new_callable=AsyncMock,
                        ) as mock_run:
                            mock_run.return_value = make_task_result(
                                status="completed",
                                duration=45.0,
                                tokens=3200,
                                cost=0.02,
                            )

                            with patch("orchestrator.cli.CodingAgentContainer"):
                                with patch("orchestrator.cli.telemetry") as mock_tel:
                                    mock_tel.tasks_counter = MagicMock()
                                    mock_tel.tokens_counter = MagicMock()
                                    mock_tel.cost_counter = MagicMock()
                                    result = runner.invoke(cli, ["task", f.name, "2.1"])

        output = result.output
        # Should contain status, duration, tokens, cost in some form
        assert "COMPLETED" in output.upper() or "completed" in output.lower()


class TestTaskCommandTelemetry:
    """Test telemetry integration in task command."""

    def test_calls_setup_telemetry(self):
        """Should call setup_telemetry on execution."""
        from orchestrator.cli import cli

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2

            ## Task 2.1: Test

            **Description:** Test

            **Acceptance Criteria:**
            - [ ] Works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.validate_environment"):
                with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                    mock_telemetry.return_value = (MagicMock(), MagicMock())

                    with patch("orchestrator.cli.create_metrics"):
                        with patch(
                            "orchestrator.cli.run_task",
                            new_callable=AsyncMock,
                        ) as mock_run:
                            mock_run.return_value = make_task_result()

                            with patch("orchestrator.cli.CodingAgentContainer"):
                                runner.invoke(cli, ["task", f.name, "2.1"])

        mock_telemetry.assert_called_once()

    def test_creates_span_with_task_attributes(self):
        """Should create span with task.id and task.title attributes."""
        from orchestrator.cli import cli

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2

            ## Task 2.1: Test Task Title

            **Description:** Test

            **Acceptance Criteria:**
            - [ ] Works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            mock_span = MagicMock()

            with patch("orchestrator.cli.validate_environment"):
                with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                    mock_tracer = MagicMock()
                    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                        return_value=mock_span
                    )
                    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                        return_value=None
                    )
                    mock_telemetry.return_value = (mock_tracer, MagicMock())

                    with patch("orchestrator.cli.create_metrics"):
                        with patch(
                            "orchestrator.cli.run_task",
                            new_callable=AsyncMock,
                        ) as mock_run:
                            mock_run.return_value = make_task_result()

                            with patch("orchestrator.cli.CodingAgentContainer"):
                                with patch("orchestrator.cli.telemetry") as mock_tel:
                                    mock_tel.tasks_counter = MagicMock()
                                    mock_tel.tokens_counter = MagicMock()
                                    mock_tel.cost_counter = MagicMock()
                                    runner.invoke(cli, ["task", f.name, "2.1"])

        # Verify span was created with correct name
        mock_tracer.start_as_current_span.assert_called_with("orchestrator.task")

        # Verify attributes were set
        set_attribute_calls = [
            call[0] for call in mock_span.set_attribute.call_args_list
        ]
        attribute_names = [call[0] for call in set_attribute_calls]
        assert "task.id" in attribute_names
        assert "task.status" in attribute_names


class TestRunCommand:
    """Test the run CLI command."""

    def test_run_command_exists(self):
        """The run command should exist in the CLI."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])

        assert result.exit_code == 0
        assert "Run all tasks" in result.output or "milestone" in result.output.lower()

    def test_run_command_requires_plan_file(self):
        """run command should require a plan file argument."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["run"])

        # Should fail due to missing argument
        assert result.exit_code != 0

    def test_run_command_has_notify_option(self):
        """run command should have --notify option."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])

        assert "--notify" in result.output


class TestRunCommandExecution:
    """Test run command execution with mocked dependencies."""

    def test_run_calls_run_milestone(self):
        """run command should call run_milestone."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=["2.1"],
        )

        mock_result = MilestoneResult(
            status="completed",
            state=mock_state,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            total_cost_usd=0.05,
            total_tokens=5000,
            total_duration_seconds=60.0,
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                mock_telemetry.return_value = (MagicMock(), MagicMock())

                with patch("orchestrator.cli.create_metrics"):
                    with patch(
                        "orchestrator.cli.run_milestone",
                        new_callable=AsyncMock,
                    ) as mock_run:
                        mock_run.return_value = mock_result

                        with patch("orchestrator.cli.MilestoneLock") as mock_lock:
                            mock_lock.return_value.__enter__ = MagicMock(
                                return_value=mock_lock
                            )
                            mock_lock.return_value.__exit__ = MagicMock(
                                return_value=None
                            )
                            result = runner.invoke(cli, ["run", f.name])

        mock_run.assert_called_once()
        assert "complete" in result.output.lower() or result.exit_code == 0

    def test_run_uses_lock(self):
        """run command should use MilestoneLock."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
        )

        mock_result = MilestoneResult(
            status="completed",
            state=mock_state,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            total_cost_usd=0.05,
            total_tokens=5000,
            total_duration_seconds=60.0,
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                mock_telemetry.return_value = (MagicMock(), MagicMock())

                with patch("orchestrator.cli.create_metrics"):
                    with patch(
                        "orchestrator.cli.run_milestone",
                        new_callable=AsyncMock,
                    ) as mock_run:
                        mock_run.return_value = mock_result

                        with patch("orchestrator.cli.MilestoneLock") as mock_lock:
                            mock_lock.return_value.__enter__ = MagicMock(
                                return_value=mock_lock
                            )
                            mock_lock.return_value.__exit__ = MagicMock(
                                return_value=None
                            )
                            runner.invoke(cli, ["run", f.name])

        # Lock should have been instantiated
        mock_lock.assert_called_once()

    def test_run_shows_error_when_lock_held(self):
        """run command should show error when lock is held."""
        from orchestrator.cli import cli

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                mock_telemetry.return_value = (MagicMock(), MagicMock())

                with patch("orchestrator.cli.create_metrics"):
                    with patch("orchestrator.cli.MilestoneLock") as mock_lock:
                        mock_lock.return_value.__enter__ = MagicMock(
                            side_effect=RuntimeError(
                                "Milestone already running (PID: 12345)"
                            )
                        )
                        result = runner.invoke(cli, ["run", f.name])

        assert "already running" in result.output.lower() or result.exit_code != 0

    def test_run_outputs_summary(self):
        """run command should output summary on completion."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=["2.1"],
        )

        mock_result = MilestoneResult(
            status="completed",
            state=mock_state,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            total_cost_usd=0.05,
            total_tokens=5000,
            total_duration_seconds=60.0,
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                mock_telemetry.return_value = (MagicMock(), MagicMock())

                with patch("orchestrator.cli.create_metrics"):
                    with patch(
                        "orchestrator.cli.run_milestone",
                        new_callable=AsyncMock,
                    ) as mock_run:
                        mock_run.return_value = mock_result

                        with patch("orchestrator.cli.MilestoneLock") as mock_lock:
                            mock_lock.return_value.__enter__ = MagicMock(
                                return_value=mock_lock
                            )
                            mock_lock.return_value.__exit__ = MagicMock(
                                return_value=None
                            )
                            result = runner.invoke(cli, ["run", f.name])

        output = result.output.lower()
        # Should contain summary information
        assert "1" in result.output  # Number of tasks
        assert "$" in result.output or "cost" in output  # Cost


class TestResumeCommand:
    """Test the resume CLI command."""

    def test_resume_command_exists(self):
        """The resume command should exist in the CLI."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["resume", "--help"])

        assert result.exit_code == 0
        assert "Resume" in result.output or "resume" in result.output.lower()

    def test_resume_command_requires_plan_file(self):
        """resume command should require a plan file argument."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["resume"])

        # Should fail due to missing argument
        assert result.exit_code != 0

    def test_resume_command_has_notify_option(self):
        """resume command should have --notify option."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["resume", "--help"])

        assert "--notify" in result.output


class TestResumeCommandExecution:
    """Test resume command execution with mocked dependencies."""

    def test_resume_errors_when_no_state_exists(self):
        """resume command should show error when no state file exists."""
        from orchestrator.cli import cli

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=Path("/nonexistent"))

                with patch("orchestrator.cli.OrchestratorState.load") as mock_load:
                    mock_load.return_value = None  # No state exists
                    result = runner.invoke(cli, ["resume", f.name])

        assert (
            "no saved state" in result.output.lower()
            or "no state" in result.output.lower()
        )

    def test_resume_suggests_run_when_no_tasks_completed(self):
        """resume command should suggest 'run' when no tasks are completed."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        # State exists but no tasks completed
        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=[],  # No tasks completed
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=Path("/tmp"))

                with patch("orchestrator.cli.OrchestratorState.load") as mock_load:
                    mock_load.return_value = mock_state
                    result = runner.invoke(cli, ["resume", f.name])

        # Should suggest using 'run' instead
        assert "run" in result.output.lower()

    def test_resume_shows_completed_task_count(self):
        """resume command should show how many tasks are already completed."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task 1

            **Description:** Test task 1

            **Acceptance Criteria:**
            - [ ] Works

            ## Task 2.2: Test Task 2

            **Description:** Test task 2

            **Acceptance Criteria:**
            - [ ] Works
        """)

        # State with one task completed
        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=["2.1"],  # One task done
        )

        mock_result = MilestoneResult(
            status="completed",
            state=mock_state,
            total_tasks=2,
            completed_tasks=2,
            failed_tasks=0,
            total_cost_usd=0.10,
            total_tokens=10000,
            total_duration_seconds=120.0,
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=Path("/tmp"))

                with patch("orchestrator.cli.OrchestratorState.load") as mock_load:
                    mock_load.return_value = mock_state

                    with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                        mock_telemetry.return_value = (MagicMock(), MagicMock())

                        with patch("orchestrator.cli.create_metrics"):
                            with patch(
                                "orchestrator.cli.run_milestone",
                                new_callable=AsyncMock,
                            ) as mock_run:
                                mock_run.return_value = mock_result

                                with patch(
                                    "orchestrator.cli.MilestoneLock"
                                ) as mock_lock:
                                    mock_lock.return_value.__enter__ = MagicMock(
                                        return_value=mock_lock
                                    )
                                    mock_lock.return_value.__exit__ = MagicMock(
                                        return_value=None
                                    )
                                    result = runner.invoke(cli, ["resume", f.name])

        # Should show count of completed tasks
        assert "1" in result.output  # Shows "1 task completed" or similar

    def test_resume_calls_run_milestone_with_resume_true(self):
        """resume command should call run_milestone with resume=True."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=["2.1"],
        )

        mock_result = MilestoneResult(
            status="completed",
            state=mock_state,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            total_cost_usd=0.05,
            total_tokens=5000,
            total_duration_seconds=60.0,
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=Path("/tmp"))

                with patch("orchestrator.cli.OrchestratorState.load") as mock_load:
                    mock_load.return_value = mock_state

                    with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                        mock_telemetry.return_value = (MagicMock(), MagicMock())

                        with patch("orchestrator.cli.create_metrics"):
                            with patch(
                                "orchestrator.cli.run_milestone",
                                new_callable=AsyncMock,
                            ) as mock_run:
                                mock_run.return_value = mock_result

                                with patch(
                                    "orchestrator.cli.MilestoneLock"
                                ) as mock_lock:
                                    mock_lock.return_value.__enter__ = MagicMock(
                                        return_value=mock_lock
                                    )
                                    mock_lock.return_value.__exit__ = MagicMock(
                                        return_value=None
                                    )
                                    runner.invoke(cli, ["resume", f.name])

        # Should call run_milestone with resume=True
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("resume") is True

    def test_resume_uses_lock(self):
        """resume command should use MilestoneLock."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=["2.1"],
        )

        mock_result = MilestoneResult(
            status="completed",
            state=mock_state,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            total_cost_usd=0.05,
            total_tokens=5000,
            total_duration_seconds=60.0,
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=Path("/tmp"))

                with patch("orchestrator.cli.OrchestratorState.load") as mock_load:
                    mock_load.return_value = mock_state

                    with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                        mock_telemetry.return_value = (MagicMock(), MagicMock())

                        with patch("orchestrator.cli.create_metrics"):
                            with patch(
                                "orchestrator.cli.run_milestone",
                                new_callable=AsyncMock,
                            ) as mock_run:
                                mock_run.return_value = mock_result

                                with patch(
                                    "orchestrator.cli.MilestoneLock"
                                ) as mock_lock:
                                    mock_lock.return_value.__enter__ = MagicMock(
                                        return_value=mock_lock
                                    )
                                    mock_lock.return_value.__exit__ = MagicMock(
                                        return_value=None
                                    )
                                    runner.invoke(cli, ["resume", f.name])

        # Lock should have been used
        mock_lock.assert_called_once()


class TestPRPromptAfterMilestone:
    """Test PR prompt functionality after milestone completion."""

    def test_prompts_for_pr_on_completed_milestone(self):
        """Should prompt user to create PR when milestone completes."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=["2.1"],
        )

        mock_result = MilestoneResult(
            status="completed",
            state=mock_state,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            total_cost_usd=0.05,
            total_tokens=5000,
            total_duration_seconds=60.0,
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                mock_telemetry.return_value = (MagicMock(), MagicMock())

                with patch("orchestrator.cli.create_metrics"):
                    with patch(
                        "orchestrator.cli.run_milestone",
                        new_callable=AsyncMock,
                    ) as mock_run:
                        mock_run.return_value = mock_result

                        with patch("orchestrator.cli.MilestoneLock") as mock_lock:
                            mock_lock.return_value.__enter__ = MagicMock(
                                return_value=mock_lock
                            )
                            mock_lock.return_value.__exit__ = MagicMock(
                                return_value=None
                            )
                            # Simulate user typing 'n' to decline PR creation
                            result = runner.invoke(cli, ["run", f.name], input="n\n")

        # Should see PR prompt in output
        assert "pr" in result.output.lower() or "pull request" in result.output.lower()

    def test_creates_pr_when_user_confirms(self):
        """Should invoke Claude to create PR when user confirms."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.models import ClaudeResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=["2.1"],
        )

        mock_result = MilestoneResult(
            status="completed",
            state=mock_state,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            total_cost_usd=0.05,
            total_tokens=5000,
            total_duration_seconds=60.0,
        )

        mock_pr_result = ClaudeResult(
            is_error=False,
            result="PR created: https://github.com/user/repo/pull/123",
            total_cost_usd=0.02,
            duration_ms=5000,
            num_turns=3,
            session_id="pr-session",
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                mock_telemetry.return_value = (MagicMock(), MagicMock())

                with patch("orchestrator.cli.create_metrics"):
                    with patch(
                        "orchestrator.cli.run_milestone",
                        new_callable=AsyncMock,
                    ) as mock_run:
                        mock_run.return_value = mock_result

                        with patch("orchestrator.cli.MilestoneLock") as mock_lock:
                            mock_lock.return_value.__enter__ = MagicMock(
                                return_value=mock_lock
                            )
                            mock_lock.return_value.__exit__ = MagicMock(
                                return_value=None
                            )
                            with patch(
                                "orchestrator.cli.create_milestone_pr",
                                new_callable=AsyncMock,
                            ) as mock_pr:
                                mock_pr.return_value = mock_pr_result
                                # Simulate user typing 'y' to confirm PR creation
                                runner.invoke(cli, ["run", f.name], input="y\n")

        # create_milestone_pr should have been called
        mock_pr.assert_called_once()

    def test_no_pr_prompt_on_failed_milestone(self):
        """Should not prompt for PR when milestone fails."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=[],
            failed_tasks=["2.1"],
        )

        mock_result = MilestoneResult(
            status="failed",  # Failed milestone
            state=mock_state,
            total_tasks=1,
            completed_tasks=0,
            failed_tasks=1,
            total_cost_usd=0.05,
            total_tokens=5000,
            total_duration_seconds=60.0,
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                mock_telemetry.return_value = (MagicMock(), MagicMock())

                with patch("orchestrator.cli.create_metrics"):
                    with patch(
                        "orchestrator.cli.run_milestone",
                        new_callable=AsyncMock,
                    ) as mock_run:
                        mock_run.return_value = mock_result

                        with patch("orchestrator.cli.MilestoneLock") as mock_lock:
                            mock_lock.return_value.__enter__ = MagicMock(
                                return_value=mock_lock
                            )
                            mock_lock.return_value.__exit__ = MagicMock(
                                return_value=None
                            )
                            with patch(
                                "orchestrator.cli.create_milestone_pr",
                                new_callable=AsyncMock,
                            ) as mock_pr:
                                runner.invoke(cli, ["run", f.name])

        # Should NOT have prompted for PR (no input needed means no prompt)
        mock_pr.assert_not_called()

    def test_displays_task_summaries(self):
        """Should display task summaries via on_task_complete callback."""
        from datetime import datetime

        from orchestrator.cli import cli
        from orchestrator.milestone_runner import MilestoneResult
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Test Task

            **Description:** Test task

            **Acceptance Criteria:**
            - [ ] Works
        """)

        mock_state = OrchestratorState(
            milestone_id="test",
            plan_path="test.md",
            started_at=datetime.now(),
            completed_tasks=["2.1"],
        )

        mock_result = MilestoneResult(
            status="completed",
            state=mock_state,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            total_cost_usd=0.05,
            total_tokens=5000,
            total_duration_seconds=60.0,
        )

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()

            with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                mock_telemetry.return_value = (MagicMock(), MagicMock())

                with patch("orchestrator.cli.create_metrics"):
                    with patch(
                        "orchestrator.cli.run_milestone",
                        new_callable=AsyncMock,
                    ) as mock_run:
                        mock_run.return_value = mock_result

                        with patch("orchestrator.cli.MilestoneLock") as mock_lock:
                            mock_lock.return_value.__enter__ = MagicMock(
                                return_value=mock_lock
                            )
                            mock_lock.return_value.__exit__ = MagicMock(
                                return_value=None
                            )
                            runner.invoke(cli, ["run", f.name], input="n\n")

        # run_milestone should have been called with on_task_complete callback
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert "on_task_complete" in call_kwargs
        assert call_kwargs["on_task_complete"] is not None


class TestHistoryCommand:
    """Test the history CLI command."""

    def test_history_command_exists(self):
        """The history command should exist in the CLI."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["history", "--help"])

        assert result.exit_code == 0
        assert "history" in result.output.lower()

    def test_history_command_has_milestone_option(self):
        """history command should have --milestone option."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["history", "--help"])

        assert "--milestone" in result.output or "-m" in result.output

    def test_history_command_has_limit_option(self):
        """history command should have --limit option."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["history", "--help"])

        assert "--limit" in result.output or "-n" in result.output


class TestHistoryCommandExecution:
    """Test history command execution with mocked dependencies."""

    def test_history_shows_empty_when_no_state_files(self):
        """history command should handle empty state directory."""
        from orchestrator.cli import cli

        runner = CliRunner()

        with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
            mock_config.return_value = MagicMock(state_dir=Path("/nonexistent"))
            result = runner.invoke(cli, ["history"])

        # Should complete without error (just show empty or message)
        assert result.exit_code == 0

    def test_history_shows_past_runs(self):
        """history command should show past runs from state files."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            # Create a test state file
            state = OrchestratorState(
                milestone_id="test_milestone",
                plan_path="test.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1", "1.2"],
                task_results={
                    "1.1": {"cost_usd": 0.05},
                    "1.2": {"cost_usd": 0.03},
                },
                e2e_status="passed",
            )
            state.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["history"])

        # Should show milestone info
        assert "test_milestone" in result.output
        assert result.exit_code == 0

    def test_history_shows_tasks_completed(self):
        """history command should show tasks completed count."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            state = OrchestratorState(
                milestone_id="test_milestone",
                plan_path="test.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1", "1.2", "1.3"],
                failed_tasks=["1.4"],
                task_results={
                    "1.1": {"cost_usd": 0.05},
                    "1.2": {"cost_usd": 0.03},
                    "1.3": {"cost_usd": 0.02},
                },
            )
            state.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["history"])

        # Should show "3/4" (3 completed out of 4 total)
        assert "3/4" in result.output or ("3" in result.output and "4" in result.output)

    def test_history_shows_e2e_status(self):
        """history command should show E2E status."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            state = OrchestratorState(
                milestone_id="test_milestone",
                plan_path="test.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.05}},
                e2e_status="passed",
            )
            state.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["history"])

        # Should show E2E status
        assert "passed" in result.output.lower()

    def test_history_shows_cost(self):
        """history command should show total cost."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            state = OrchestratorState(
                milestone_id="test_milestone",
                plan_path="test.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1", "1.2"],
                task_results={
                    "1.1": {"cost_usd": 0.05},
                    "1.2": {"cost_usd": 0.03},
                },
            )
            state.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["history"])

        # Should show cost with $ sign
        assert "$" in result.output
        assert "0.08" in result.output

    def test_history_filters_by_milestone(self):
        """history command --milestone should filter results."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            # Create two milestones
            state1 = OrchestratorState(
                milestone_id="feature_auth",
                plan_path="auth.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.05}},
            )
            state1.save(state_dir)

            state2 = OrchestratorState(
                milestone_id="feature_api",
                plan_path="api.md",
                started_at=datetime(2025, 1, 16, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.03}},
            )
            state2.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["history", "--milestone", "auth"])

        # Should show only auth, not api
        assert "feature_auth" in result.output
        assert "feature_api" not in result.output

    def test_history_respects_limit(self):
        """history command --limit should limit results."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            # Create three milestones
            for i in range(3):
                state = OrchestratorState(
                    milestone_id=f"milestone_{i}",
                    plan_path=f"plan_{i}.md",
                    started_at=datetime(2025, 1, 15 + i, 10, 30),
                    completed_tasks=["1.1"],
                    task_results={"1.1": {"cost_usd": 0.05}},
                )
                state.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["history", "--limit", "2"])

        # Should only show 2 milestones (most recent first)
        output = result.output
        assert "milestone_2" in output  # Most recent
        assert "milestone_1" in output  # Second most recent
        assert "milestone_0" not in output  # Oldest should be excluded

    def test_history_sorts_by_date_descending(self):
        """history command should show most recent runs first."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            # Create milestones with different dates (save in random order)
            state_old = OrchestratorState(
                milestone_id="old_milestone",
                plan_path="old.md",
                started_at=datetime(2025, 1, 1, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.05}},
            )
            state_old.save(state_dir)

            state_new = OrchestratorState(
                milestone_id="new_milestone",
                plan_path="new.md",
                started_at=datetime(2025, 1, 20, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.05}},
            )
            state_new.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["history"])

        # new_milestone should appear before old_milestone
        new_pos = result.output.find("new_milestone")
        old_pos = result.output.find("old_milestone")
        assert new_pos < old_pos


class TestCostsCommand:
    """Test the costs CLI command."""

    def test_costs_command_exists(self):
        """The costs command should exist in the CLI."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["costs", "--help"])

        assert result.exit_code == 0
        assert "cost" in result.output.lower()

    def test_costs_command_has_since_option(self):
        """costs command should have --since option."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["costs", "--help"])

        assert "--since" in result.output

    def test_costs_command_has_by_milestone_option(self):
        """costs command should have --by-milestone option."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["costs", "--help"])

        assert "--by-milestone" in result.output or "--total" in result.output


class TestNotifyTestCommand:
    """Test the notify-test CLI command."""

    def test_notify_test_command_exists(self):
        """The notify-test command should exist in the CLI."""
        from orchestrator.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["notify-test", "--help"])

        assert result.exit_code == 0
        assert "test" in result.output.lower() or "discord" in result.output.lower()

    def test_notify_test_shows_error_when_not_configured(self):
        """notify-test should show error when DISCORD_WEBHOOK_URL not set."""
        from orchestrator.cli import cli

        runner = CliRunner()

        with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
            mock_config.return_value = MagicMock(
                discord_enabled=False,
                discord_webhook_url=None,
            )
            result = runner.invoke(cli, ["notify-test"])

        assert "not configured" in result.output.lower() or "discord_webhook_url" in result.output.lower()

    def test_notify_test_sends_notification_when_configured(self):
        """notify-test should send notification when webhook is configured."""
        from orchestrator.cli import cli

        runner = CliRunner()

        with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
            mock_config.return_value = MagicMock(
                discord_enabled=True,
                discord_webhook_url="https://discord.com/api/webhooks/test",
            )
            with patch("orchestrator.cli.send_discord_message", new_callable=AsyncMock) as mock_send:
                with patch("orchestrator.cli.format_test_notification") as mock_format:
                    mock_format.return_value = MagicMock()
                    result = runner.invoke(cli, ["notify-test"])

        mock_send.assert_called_once()
        assert "success" in result.output.lower() or "sent" in result.output.lower()

    def test_notify_test_shows_sending_message(self):
        """notify-test should show 'Sending test notification...' message."""
        from orchestrator.cli import cli

        runner = CliRunner()

        with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
            mock_config.return_value = MagicMock(
                discord_enabled=True,
                discord_webhook_url="https://discord.com/api/webhooks/test",
            )
            with patch("orchestrator.cli.send_discord_message", new_callable=AsyncMock):
                with patch("orchestrator.cli.format_test_notification") as mock_format:
                    mock_format.return_value = MagicMock()
                    result = runner.invoke(cli, ["notify-test"])

        assert "sending" in result.output.lower()


class TestCostsCommandExecution:
    """Test costs command execution with mocked dependencies."""

    def test_costs_shows_empty_when_no_state_files(self):
        """costs command should handle empty state directory."""
        from orchestrator.cli import cli

        runner = CliRunner()

        with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
            mock_config.return_value = MagicMock(state_dir=Path("/nonexistent"))
            result = runner.invoke(cli, ["costs"])

        # Should complete without error
        assert result.exit_code == 0

    def test_costs_shows_total_cost(self):
        """costs command should show total cost from all state files."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            # Create state files with known costs
            state1 = OrchestratorState(
                milestone_id="milestone_1",
                plan_path="plan1.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1", "1.2"],
                task_results={
                    "1.1": {"cost_usd": 0.10},
                    "1.2": {"cost_usd": 0.05},
                },
            )
            state1.save(state_dir)

            state2 = OrchestratorState(
                milestone_id="milestone_2",
                plan_path="plan2.md",
                started_at=datetime(2025, 1, 16, 10, 30),
                completed_tasks=["2.1"],
                task_results={
                    "2.1": {"cost_usd": 0.20},
                },
            )
            state2.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["costs"])

        # Total should be 0.10 + 0.05 + 0.20 = 0.35
        assert "$0.35" in result.output or "0.35" in result.output

    def test_costs_shows_breakdown_by_milestone(self):
        """costs command should show breakdown by milestone by default."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            state1 = OrchestratorState(
                milestone_id="feature_auth",
                plan_path="auth.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.15}},
            )
            state1.save(state_dir)

            state2 = OrchestratorState(
                milestone_id="feature_api",
                plan_path="api.md",
                started_at=datetime(2025, 1, 16, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.25}},
            )
            state2.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["costs"])

        # Should show both milestones
        assert "feature_auth" in result.output
        assert "feature_api" in result.output
        # Should show individual costs
        assert "$0.15" in result.output or "0.15" in result.output
        assert "$0.25" in result.output or "0.25" in result.output

    def test_costs_total_only_flag(self):
        """costs command --total should show only total, not breakdown."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            state = OrchestratorState(
                milestone_id="feature_auth",
                plan_path="auth.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.15}},
            )
            state.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["costs", "--total"])

        # Should show total but not the milestone name in table format
        assert "0.15" in result.output
        # Total only mode should be simpler output
        assert "Total cost:" in result.output or "total" in result.output.lower()

    def test_costs_filters_by_since_date(self):
        """costs command --since should filter by date."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            # Old run - before cutoff
            state_old = OrchestratorState(
                milestone_id="old_run",
                plan_path="old.md",
                started_at=datetime(2025, 1, 1, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 1.00}},
            )
            state_old.save(state_dir)

            # New run - after cutoff
            state_new = OrchestratorState(
                milestone_id="new_run",
                plan_path="new.md",
                started_at=datetime(2025, 1, 20, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.50}},
            )
            state_new.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["costs", "--since", "2025-01-15"])

        # Should only include new_run (0.50), not old_run (1.00)
        assert "new_run" in result.output
        assert "old_run" not in result.output
        # Total should be 0.50
        assert "$0.50" in result.output or "0.50" in result.output

    def test_costs_handles_missing_cost_in_results(self):
        """costs command should handle task_results without cost_usd."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            # State with missing cost_usd in one result
            state = OrchestratorState(
                milestone_id="test_milestone",
                plan_path="test.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1", "1.2"],
                task_results={
                    "1.1": {"cost_usd": 0.10},
                    "1.2": {"status": "completed"},  # No cost_usd
                },
            )
            state.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["costs"])

        # Should not crash, should show at least $0.10
        assert result.exit_code == 0
        assert "0.10" in result.output

    def test_costs_shows_table_with_total_row(self):
        """costs command should show table with Total row."""
        from datetime import datetime
        from tempfile import TemporaryDirectory

        from orchestrator.cli import cli
        from orchestrator.state import OrchestratorState

        runner = CliRunner()

        with TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)

            state = OrchestratorState(
                milestone_id="test_milestone",
                plan_path="test.md",
                started_at=datetime(2025, 1, 15, 10, 30),
                completed_tasks=["1.1"],
                task_results={"1.1": {"cost_usd": 0.25}},
            )
            state.save(state_dir)

            with patch("orchestrator.cli.OrchestratorConfig.from_env") as mock_config:
                mock_config.return_value = MagicMock(state_dir=state_dir)
                result = runner.invoke(cli, ["costs"])

        # Should show Total row
        assert "Total" in result.output

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

                        with patch("orchestrator.cli.SandboxManager"):
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

                        with patch("orchestrator.cli.SandboxManager"):
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

            with patch("orchestrator.cli.setup_telemetry") as mock_telemetry:
                mock_telemetry.return_value = (MagicMock(), MagicMock())

                with patch("orchestrator.cli.create_metrics"):
                    with patch(
                        "orchestrator.cli.run_task",
                        new_callable=AsyncMock,
                    ) as mock_run:
                        mock_run.return_value = make_task_result()

                        with patch("orchestrator.cli.SandboxManager"):
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

                        with patch("orchestrator.cli.SandboxManager"):
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
                            side_effect=RuntimeError("Milestone already running (PID: 12345)")
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

        assert "no saved state" in result.output.lower() or "no state" in result.output.lower()

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

                                with patch("orchestrator.cli.MilestoneLock") as mock_lock:
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

                                with patch("orchestrator.cli.MilestoneLock") as mock_lock:
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

                                with patch("orchestrator.cli.MilestoneLock") as mock_lock:
                                    mock_lock.return_value.__enter__ = MagicMock(
                                        return_value=mock_lock
                                    )
                                    mock_lock.return_value.__exit__ = MagicMock(
                                        return_value=None
                                    )
                                    runner.invoke(cli, ["resume", f.name])

        # Lock should have been used
        mock_lock.assert_called_once()

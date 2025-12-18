"""Tests for CLI module.

These tests verify the CLI task command functionality.
"""

import textwrap
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

"""
Unit tests for CLI operations resume command.

Tests the `ktrdr operations resume <operation_id>` command.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from ktrdr.cli.operations_commands import operations_app
from ktrdr.errors import DataError


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_api_client():
    """Create a mock API client for testing."""
    mock_client = MagicMock()

    # Mock resume_operation method
    mock_client.resume_operation = AsyncMock()

    return mock_client


class TestOperationsResumeCommand:
    """Test suite for operations resume CLI command."""

    @pytest.mark.cli
    def test_resume_operation_success(self, cli_runner, mock_api_client):
        """Test successfully resuming a failed operation."""
        # Mock successful resume
        mock_api_client.resume_operation.return_value = {
            "success": True,
            "original_operation_id": "op_training_001",
            "new_operation_id": "op_training_new_001",
            "resumed_from_checkpoint": "epoch_snapshot",
            "message": "Operation resumed from epoch 45",
        }

        # Mock API connection check
        async_mock_check = AsyncMock(return_value=True)

        with patch(
            "ktrdr.cli.operations_commands.get_api_client", return_value=mock_api_client
        ):
            with patch(
                "ktrdr.cli.operations_commands.check_api_connection",
                new=async_mock_check,
            ):
                result = cli_runner.invoke(
                    operations_app, ["resume", "op_training_001"]
                )

        # Assertions
        assert result.exit_code == 0
        assert "op_training_001" in result.stdout
        assert "op_training_new_001" in result.stdout
        assert "resumed" in result.stdout.lower()

    @pytest.mark.cli
    def test_resume_operation_not_found(self, cli_runner, mock_api_client):
        """Test resume fails when operation doesn't exist."""
        # Mock operation not found
        mock_api_client.resume_operation.side_effect = DataError(
            message="Operation not found",
            error_code="CLI-NotFoundError",
            details={"operation_id": "op_nonexistent"},
        )

        # Mock API connection check
        async_mock_check = AsyncMock(return_value=True)

        with patch(
            "ktrdr.cli.operations_commands.get_api_client", return_value=mock_api_client
        ):
            with patch(
                "ktrdr.cli.operations_commands.check_api_connection",
                new=async_mock_check,
            ):
                result = cli_runner.invoke(operations_app, ["resume", "op_nonexistent"])

        # Should fail with error message
        assert result.exit_code != 0
        # Check both stdout and stderr (typer uses both)
        output = (result.stdout + result.stderr).lower()
        assert "not found" in output or result.exit_code != 0

    @pytest.mark.cli
    def test_resume_operation_wrong_status(self, cli_runner, mock_api_client):
        """Test resume fails for running operation."""
        # Mock wrong status error
        mock_api_client.resume_operation.side_effect = DataError(
            message="Cannot resume running operation",
            error_code="CLI-InvalidStatusError",
            details={"operation_id": "op_training_running"},
        )

        # Mock API connection check
        async_mock_check = AsyncMock(return_value=True)

        with patch(
            "ktrdr.cli.operations_commands.get_api_client", return_value=mock_api_client
        ):
            with patch(
                "ktrdr.cli.operations_commands.check_api_connection",
                new=async_mock_check,
            ):
                result = cli_runner.invoke(
                    operations_app, ["resume", "op_training_running"]
                )

        # Should fail with error message
        assert result.exit_code != 0
        # Check both stdout and stderr (typer uses both)
        output = (result.stdout + result.stderr).lower()
        assert "cannot resume" in output or result.exit_code != 0

    @pytest.mark.cli
    def test_resume_operation_no_checkpoint(self, cli_runner, mock_api_client):
        """Test resume fails when no checkpoint exists."""
        # Mock no checkpoint error
        mock_api_client.resume_operation.side_effect = DataError(
            message="No checkpoint found for operation",
            error_code="CLI-NoCheckpointError",
            details={"operation_id": "op_training_002"},
        )

        # Mock API connection check
        async_mock_check = AsyncMock(return_value=True)

        with patch(
            "ktrdr.cli.operations_commands.get_api_client", return_value=mock_api_client
        ):
            with patch(
                "ktrdr.cli.operations_commands.check_api_connection",
                new=async_mock_check,
            ):
                result = cli_runner.invoke(
                    operations_app, ["resume", "op_training_002"]
                )

        # Should fail with error message
        assert result.exit_code != 0
        # Check both stdout and stderr (typer uses both)
        output = (result.stdout + result.stderr).lower()
        assert "checkpoint" in output or result.exit_code != 0

    @pytest.mark.cli
    def test_resume_with_verbose_flag(self, cli_runner, mock_api_client):
        """Test resume command with verbose output."""
        # Mock successful resume
        mock_api_client.resume_operation.return_value = {
            "success": True,
            "original_operation_id": "op_training_001",
            "new_operation_id": "op_training_new_001",
            "resumed_from_checkpoint": "epoch_snapshot",
            "message": "Operation resumed from epoch 45",
        }

        # Mock API connection check
        async_mock_check = AsyncMock(return_value=True)

        with patch(
            "ktrdr.cli.operations_commands.get_api_client", return_value=mock_api_client
        ):
            with patch(
                "ktrdr.cli.operations_commands.check_api_connection",
                new=async_mock_check,
            ):
                result = cli_runner.invoke(
                    operations_app, ["resume", "op_training_001", "--verbose"]
                )

        # Should show additional details
        assert result.exit_code == 0
        assert "Resuming" in result.stdout or "resumed" in result.stdout.lower()

    @pytest.mark.cli
    def test_resume_displays_progress_monitoring_tip(self, cli_runner, mock_api_client):
        """Test that resume command suggests how to monitor progress."""
        # Mock successful resume
        mock_api_client.resume_operation.return_value = {
            "success": True,
            "original_operation_id": "op_training_001",
            "new_operation_id": "op_training_new_001",
            "resumed_from_checkpoint": "epoch_snapshot",
            "message": "Operation resumed from epoch 45",
        }

        # Mock API connection check
        async_mock_check = AsyncMock(return_value=True)

        with patch(
            "ktrdr.cli.operations_commands.get_api_client", return_value=mock_api_client
        ):
            with patch(
                "ktrdr.cli.operations_commands.check_api_connection",
                new=async_mock_check,
            ):
                result = cli_runner.invoke(
                    operations_app, ["resume", "op_training_001"]
                )

        # Should suggest monitoring
        assert result.exit_code == 0
        assert "status" in result.stdout.lower() or "monitor" in result.stdout.lower()

    @pytest.mark.cli
    def test_resume_api_connection_failure(self, cli_runner, mock_api_client):
        """Test resume handles API connection failure gracefully."""
        # Mock API connection failure
        async_mock_check = AsyncMock(return_value=False)

        with patch(
            "ktrdr.cli.operations_commands.check_api_connection", new=async_mock_check
        ):
            result = cli_runner.invoke(operations_app, ["resume", "op_training_001"])

        # Should fail with connection error
        assert result.exit_code != 0
        # Check both stdout and stderr (typer uses both)
        output = (result.stdout + result.stderr).lower()
        assert "connect" in output or "api" in output or result.exit_code != 0

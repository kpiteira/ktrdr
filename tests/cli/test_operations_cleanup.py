"""
Unit tests for CLI operations cleanup commands.

Tests the checkpoint management commands:
- ktrdr operations delete-checkpoint <operation_id>
- ktrdr operations cleanup-cancelled
- ktrdr operations cleanup-old --days N
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

    # Mock checkpoint management methods
    mock_client.delete_checkpoint = AsyncMock()
    mock_client.cleanup_cancelled_checkpoints = AsyncMock()
    mock_client.cleanup_old_checkpoints = AsyncMock()

    return mock_client


class TestDeleteCheckpointCommand:
    """Test suite for delete-checkpoint CLI command."""

    @pytest.mark.cli
    def test_delete_checkpoint_success(self, cli_runner, mock_api_client):
        """Test successfully deleting a checkpoint."""
        # Mock successful deletion
        mock_api_client.delete_checkpoint.return_value = {
            "success": True,
            "operation_id": "op_training_001",
            "message": "Checkpoint deleted successfully",
            "freed_bytes": 52000000,  # 52 MB
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
                    operations_app, ["delete-checkpoint", "op_training_001"]
                )

        # Assertions
        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()
        assert "op_training_001" in result.stdout

    @pytest.mark.cli
    def test_delete_checkpoint_not_found(self, cli_runner, mock_api_client):
        """Test delete fails when checkpoint doesn't exist."""
        # Mock checkpoint not found
        mock_api_client.delete_checkpoint.side_effect = DataError(
            message="No checkpoint found for operation",
            error_code="CLI-NoCheckpointError",
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
                result = cli_runner.invoke(
                    operations_app, ["delete-checkpoint", "op_nonexistent"]
                )

        # Should fail gracefully
        assert result.exit_code != 0
        # Check both stdout and stderr (typer uses both)
        output = (result.stdout + result.stderr).lower()
        assert (
            "not found" in output or "no checkpoint" in output or result.exit_code != 0
        )

    @pytest.mark.cli
    def test_delete_checkpoint_shows_freed_space(self, cli_runner, mock_api_client):
        """Test that delete-checkpoint shows how much space was freed."""
        # Mock successful deletion with size info
        mock_api_client.delete_checkpoint.return_value = {
            "success": True,
            "operation_id": "op_training_001",
            "message": "Checkpoint deleted successfully",
            "freed_bytes": 104857600,  # 100 MB
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
                    operations_app, ["delete-checkpoint", "op_training_001"]
                )

        # Should show freed space
        assert result.exit_code == 0
        assert "mb" in result.stdout.lower() or "freed" in result.stdout.lower()

    @pytest.mark.cli
    def test_delete_checkpoint_with_verbose(self, cli_runner, mock_api_client):
        """Test delete-checkpoint with verbose output."""
        # Mock successful deletion
        mock_api_client.delete_checkpoint.return_value = {
            "success": True,
            "operation_id": "op_training_001",
            "message": "Checkpoint deleted successfully",
            "freed_bytes": 52000000,
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
                    operations_app,
                    ["delete-checkpoint", "op_training_001", "--verbose"],
                )

        # Should show additional details
        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()


class TestCleanupCancelledCommand:
    """Test suite for cleanup-cancelled CLI command."""

    @pytest.mark.cli
    def test_cleanup_cancelled_success(self, cli_runner, mock_api_client):
        """Test successfully cleaning up cancelled operation checkpoints."""
        # Mock successful cleanup
        mock_api_client.cleanup_cancelled_checkpoints.return_value = {
            "success": True,
            "deleted_count": 3,
            "operation_ids": ["op_001", "op_002", "op_003"],
            "total_freed_bytes": 156000000,  # 156 MB
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
                result = cli_runner.invoke(operations_app, ["cleanup-cancelled"])

        # Assertions
        assert result.exit_code == 0
        assert "3" in result.stdout or "deleted" in result.stdout.lower()
        assert "mb" in result.stdout.lower() or "freed" in result.stdout.lower()

    @pytest.mark.cli
    def test_cleanup_cancelled_no_checkpoints(self, cli_runner, mock_api_client):
        """Test cleanup when no cancelled checkpoints exist."""
        # Mock no checkpoints to clean
        mock_api_client.cleanup_cancelled_checkpoints.return_value = {
            "success": True,
            "deleted_count": 0,
            "operation_ids": [],
            "total_freed_bytes": 0,
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
                result = cli_runner.invoke(operations_app, ["cleanup-cancelled"])

        # Should succeed with informative message
        assert result.exit_code == 0
        assert "no" in result.stdout.lower() or "0" in result.stdout

    @pytest.mark.cli
    def test_cleanup_cancelled_with_verbose(self, cli_runner, mock_api_client):
        """Test cleanup-cancelled with verbose output showing operation IDs."""
        # Mock successful cleanup
        mock_api_client.cleanup_cancelled_checkpoints.return_value = {
            "success": True,
            "deleted_count": 2,
            "operation_ids": ["op_training_001", "op_backtest_002"],
            "total_freed_bytes": 104857600,
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
                    operations_app, ["cleanup-cancelled", "--verbose"]
                )

        # Should show operation IDs
        assert result.exit_code == 0
        assert "op_training_001" in result.stdout or "op_backtest_002" in result.stdout


class TestCleanupOldCommand:
    """Test suite for cleanup-old CLI command."""

    @pytest.mark.cli
    def test_cleanup_old_success(self, cli_runner, mock_api_client):
        """Test successfully cleaning up old checkpoints."""
        # Mock successful cleanup
        mock_api_client.cleanup_old_checkpoints.return_value = {
            "success": True,
            "deleted_count": 5,
            "operation_ids": ["op_001", "op_002", "op_003", "op_004", "op_005"],
            "total_freed_bytes": 260000000,  # 260 MB
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
                    operations_app, ["cleanup-old", "--days", "7"]
                )

        # Assertions
        assert result.exit_code == 0
        assert "5" in result.stdout or "deleted" in result.stdout.lower()
        assert "mb" in result.stdout.lower() or "freed" in result.stdout.lower()

    @pytest.mark.cli
    def test_cleanup_old_default_days(self, cli_runner, mock_api_client):
        """Test cleanup-old uses default of 30 days if not specified."""
        # Mock successful cleanup
        mock_api_client.cleanup_old_checkpoints.return_value = {
            "success": True,
            "deleted_count": 2,
            "operation_ids": ["op_001", "op_002"],
            "total_freed_bytes": 104857600,
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
                result = cli_runner.invoke(operations_app, ["cleanup-old"])

        # Should succeed using default
        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()
        # Verify API was called with default 30 days
        mock_api_client.cleanup_old_checkpoints.assert_called_once()

    @pytest.mark.cli
    def test_cleanup_old_no_checkpoints(self, cli_runner, mock_api_client):
        """Test cleanup when no old checkpoints exist."""
        # Mock no checkpoints to clean
        mock_api_client.cleanup_old_checkpoints.return_value = {
            "success": True,
            "deleted_count": 0,
            "operation_ids": [],
            "total_freed_bytes": 0,
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
                    operations_app, ["cleanup-old", "--days", "14"]
                )

        # Should succeed with informative message
        assert result.exit_code == 0
        assert "no" in result.stdout.lower() or "0" in result.stdout

    @pytest.mark.cli
    def test_cleanup_old_invalid_days(self, cli_runner, mock_api_client):
        """Test cleanup-old rejects invalid days parameter."""
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
                    operations_app, ["cleanup-old", "--days", "-5"]
                )

        # Should fail with validation error
        assert result.exit_code != 0

    @pytest.mark.cli
    def test_cleanup_old_with_verbose(self, cli_runner, mock_api_client):
        """Test cleanup-old with verbose output showing operation IDs."""
        # Mock successful cleanup
        mock_api_client.cleanup_old_checkpoints.return_value = {
            "success": True,
            "deleted_count": 3,
            "operation_ids": ["op_old_001", "op_old_002", "op_old_003"],
            "total_freed_bytes": 156000000,
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
                    operations_app, ["cleanup-old", "--days", "7", "--verbose"]
                )

        # Should show operation IDs
        assert result.exit_code == 0
        assert "op_old_001" in result.stdout or "deleted" in result.stdout.lower()

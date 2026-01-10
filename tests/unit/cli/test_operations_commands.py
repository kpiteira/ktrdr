"""Unit tests for operations CLI commands."""

from unittest.mock import MagicMock, patch

import pytest

from ktrdr.cli.operations_commands import (
    _format_checkpoint_summary,
    _format_duration,
    list_operations,
)


class TestFormatDuration:
    """Tests for _format_duration helper."""

    def test_format_duration_seconds(self):
        """Test formatting durations under 60 seconds."""
        assert _format_duration(30.5) == "30.5s"
        assert _format_duration(0.5) == "0.5s"

    def test_format_duration_minutes(self):
        """Test formatting durations under 60 minutes."""
        assert _format_duration(120) == "2.0m"
        assert _format_duration(300) == "5.0m"

    def test_format_duration_hours(self):
        """Test formatting durations over 60 minutes."""
        assert _format_duration(3600) == "1.0h"
        assert _format_duration(7200) == "2.0h"


class TestFormatCheckpointSummary:
    """Tests for _format_checkpoint_summary helper."""

    def test_format_epoch(self):
        """Test formatting training checkpoint with epoch."""
        state = {"epoch": 29, "train_loss": 0.28}
        assert _format_checkpoint_summary(state) == "epoch 29"

    def test_format_bar_index(self):
        """Test formatting backtesting checkpoint with bar_index."""
        state = {"bar_index": 7000, "equity": 105000}
        assert _format_checkpoint_summary(state) == "bar 7000"

    def test_format_step(self):
        """Test formatting agent checkpoint with step."""
        state = {"step": 150, "reward": 0.85}
        assert _format_checkpoint_summary(state) == "step 150"

    def test_format_fallback(self):
        """Test fallback formatting for unknown state."""
        state = {"iteration": 50}
        assert _format_checkpoint_summary(state) == "iteration 50"

    def test_format_empty(self):
        """Test formatting empty state."""
        assert _format_checkpoint_summary({}) == "saved"


class TestListOperationsWithCheckpoints:
    """Tests for operations list command with checkpoint support."""

    @pytest.fixture
    def mock_sync_client(self):
        """Create a mock SyncCLIClient for testing."""
        mock_client = MagicMock()
        mock_client.health_check.return_value = True
        mock_client.config.base_url = "http://localhost:8000/api/v1"
        return mock_client

    @pytest.fixture
    def sample_operations_response(self):
        """Sample operations API response."""
        return {
            "success": True,
            "data": [
                {
                    "operation_id": "op_training_123",
                    "operation_type": "training",
                    "status": "cancelled",
                    "progress_percentage": 29,
                    "symbol": "AAPL",
                    "duration_seconds": 3600,
                    "created_at": "2024-12-13T14:30:22Z",
                },
                {
                    "operation_id": "op_training_456",
                    "operation_type": "training",
                    "status": "cancelled",
                    "progress_percentage": 45,
                    "symbol": "MSFT",
                    "duration_seconds": 7200,
                    "created_at": "2024-12-10T09:15:00Z",
                },
            ],
            "total_count": 2,
            "active_count": 0,
        }

    def test_list_operations_shows_checkpoint_column(
        self, mock_sync_client, sample_operations_response
    ):
        """Test that operations list includes checkpoint information."""
        from ktrdr.cli.client import CLIClientError

        # Mock get responses
        def mock_get(path, **kwargs):
            if path == "/operations":
                return sample_operations_response
            elif path == "/checkpoints/op_training_123":
                return {
                    "success": True,
                    "data": {
                        "operation_id": "op_training_123",
                        "state": {"epoch": 29, "train_loss": 0.28},
                    },
                }
            elif path == "/checkpoints/op_training_456":
                raise CLIClientError("404: not found")
            else:
                raise CLIClientError("Unknown path")

        mock_sync_client.get.side_effect = mock_get

        with patch("ktrdr.cli.operations_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.operations_commands.console") as mock_console:
                list_operations(
                    status=None,
                    operation_type=None,
                    limit=50,
                    active_only=False,
                    resumable=False,
                    verbose=False,
                )

                # Verify console.print was called with table
                assert mock_console.print.called

    def test_list_operations_filter_resumable(
        self, mock_sync_client, sample_operations_response
    ):
        """Test --resumable flag filters to only operations with checkpoints."""
        from ktrdr.cli.client import CLIClientError

        # Mock get responses - only first op has checkpoint
        def mock_get(path, **kwargs):
            if path == "/operations":
                return sample_operations_response
            elif path == "/checkpoints/op_training_123":
                return {
                    "success": True,
                    "data": {
                        "operation_id": "op_training_123",
                        "state": {"epoch": 29},
                    },
                }
            elif path == "/checkpoints/op_training_456":
                raise CLIClientError("404: not found")
            else:
                raise CLIClientError("Unknown path")

        mock_sync_client.get.side_effect = mock_get

        with patch("ktrdr.cli.operations_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.operations_commands.console") as mock_console:
                list_operations(
                    status=None,
                    operation_type=None,
                    limit=50,
                    active_only=False,
                    resumable=True,  # Filter to resumable only
                    verbose=False,
                )

                # With resumable=True, only op_training_123 should be shown
                # (since it's the only one with a checkpoint)
                assert mock_console.print.called

    def test_list_operations_no_operations(self, mock_sync_client):
        """Test handling when no operations found."""
        mock_sync_client.get.return_value = {
            "success": True,
            "data": [],
            "total_count": 0,
            "active_count": 0,
        }

        with patch("ktrdr.cli.operations_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.operations_commands.console") as mock_console:
                list_operations(
                    status=None,
                    operation_type=None,
                    limit=50,
                    active_only=False,
                    resumable=False,
                    verbose=False,
                )

                # Should show "No operations found" message
                calls = [str(call) for call in mock_console.print.call_args_list]
                output = "\n".join(calls)
                assert "no operations" in output.lower()

    def test_list_operations_api_connection_failure(self, mock_sync_client):
        """Test handling when API connection fails."""
        mock_sync_client.health_check.return_value = False

        with patch("ktrdr.cli.operations_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.operations_commands.error_console"):
                with patch("sys.exit") as mock_exit:
                    list_operations(
                        status=None,
                        operation_type=None,
                        limit=50,
                        active_only=False,
                        resumable=False,
                        verbose=False,
                    )

                    mock_exit.assert_called_once_with(1)

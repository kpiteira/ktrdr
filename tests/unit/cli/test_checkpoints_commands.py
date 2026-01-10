"""Unit tests for checkpoints CLI commands."""

from unittest.mock import MagicMock, patch

import pytest

from ktrdr.cli.checkpoints_commands import delete_checkpoint, show_checkpoint


class TestShowCheckpointCommand:
    """Tests for checkpoints show command."""

    @pytest.fixture
    def mock_sync_client(self):
        """Create a mock SyncCLIClient for testing."""
        mock_client = MagicMock()
        mock_client.health_check.return_value = True
        mock_client.config.base_url = "http://localhost:8000/api/v1"
        return mock_client

    def test_show_checkpoint_calls_api_correctly(self, mock_sync_client):
        """Test that show command calls the API with correct operation ID."""
        mock_sync_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
                "artifacts_path": "/app/data/checkpoints/op_training_123",
            },
        }

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console"):
                show_checkpoint("op_training_123", verbose=False)

                # Verify API was called correctly
                mock_sync_client.get.assert_called_once_with(
                    "/checkpoints/op_training_123"
                )

    def test_show_checkpoint_not_found_exits(self, mock_sync_client):
        """Test handling when checkpoint doesn't exist."""
        from ktrdr.cli.client import CLIClientError

        mock_sync_client.get.side_effect = CLIClientError("404: not found")

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console"):
                with patch("ktrdr.cli.checkpoints_commands.error_console"):
                    with patch("sys.exit") as mock_exit:
                        show_checkpoint("nonexistent_op", verbose=False)

                        # Should have exited with error code 1
                        mock_exit.assert_called_once_with(1)

    def test_show_checkpoint_displays_resume_hint(self, mock_sync_client):
        """Test that show command shows how to resume."""
        mock_sync_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_abc123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
                "artifacts_path": "/app/data/checkpoints/op_training_abc123",
            },
        }

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console") as mock_console:
                show_checkpoint("op_training_abc123", verbose=False)

                # Check that print was called with resume hint
                calls = [str(call) for call in mock_console.print.call_args_list]
                output = "\n".join(calls)
                assert "resume" in output.lower()
                assert "op_training_abc123" in output

    def test_show_checkpoint_handles_success_false(self, mock_sync_client):
        """Test handling when API returns success=False."""
        mock_sync_client.get.return_value = {
            "success": False,
            "data": None,
        }

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console"):
                with patch("ktrdr.cli.checkpoints_commands.error_console"):
                    with patch("sys.exit") as mock_exit:
                        show_checkpoint("op_training_123", verbose=False)

                        mock_exit.assert_called_once_with(1)


class TestDeleteCheckpointCommand:
    """Tests for checkpoints delete command."""

    @pytest.fixture
    def mock_sync_client(self):
        """Create a mock SyncCLIClient for testing."""
        mock_client = MagicMock()
        mock_client.health_check.return_value = True
        mock_client.config.base_url = "http://localhost:8000/api/v1"
        return mock_client

    def test_delete_checkpoint_calls_api_correctly(self, mock_sync_client):
        """Test that delete command calls the DELETE API endpoint."""
        # Mock checkpoint exists
        mock_sync_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
            },
        }
        # Mock successful deletion
        mock_sync_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console"):
                delete_checkpoint("op_training_123", force=True, verbose=False)

                # Verify DELETE API was called correctly
                mock_sync_client.delete.assert_called_once_with(
                    "/checkpoints/op_training_123"
                )

    def test_delete_checkpoint_shows_confirmation_prompt(self, mock_sync_client):
        """Test that delete command shows confirmation prompt when force=False."""
        # Mock checkpoint exists
        mock_sync_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
            },
        }
        mock_sync_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console"):
                with patch(
                    "ktrdr.cli.checkpoints_commands.typer.confirm",
                    return_value=True,
                ) as mock_confirm:
                    delete_checkpoint("op_training_123", force=False, verbose=False)

                    # Verify confirmation was requested
                    mock_confirm.assert_called_once()

    def test_delete_checkpoint_aborted_on_no_confirmation(self, mock_sync_client):
        """Test that delete is aborted when user says no to confirmation."""
        # Mock checkpoint exists
        mock_sync_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
            },
        }

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console") as mock_console:
                with patch(
                    "ktrdr.cli.checkpoints_commands.typer.confirm",
                    return_value=False,
                ):
                    delete_checkpoint("op_training_123", force=False, verbose=False)

                    # Delete should NOT have been called
                    mock_sync_client.delete.assert_not_called()

                    # Should show aborted message
                    calls = [str(call) for call in mock_console.print.call_args_list]
                    output = "\n".join(calls)
                    assert "aborted" in output.lower() or "cancelled" in output.lower()

    def test_delete_checkpoint_force_skips_confirmation(self, mock_sync_client):
        """Test that force flag skips confirmation prompt."""
        # Mock checkpoint exists
        mock_sync_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "state": {"epoch": 29},
            },
        }
        mock_sync_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console"):
                with patch(
                    "ktrdr.cli.checkpoints_commands.typer.confirm"
                ) as mock_confirm:
                    delete_checkpoint("op_training_123", force=True, verbose=False)

                    # Confirmation should NOT be called with force=True
                    mock_confirm.assert_not_called()

                    # Delete should still be called
                    mock_sync_client.delete.assert_called_once()

    def test_delete_checkpoint_not_found_exits(self, mock_sync_client):
        """Test handling when checkpoint doesn't exist."""
        from ktrdr.cli.client import CLIClientError

        mock_sync_client.get.side_effect = CLIClientError("404: not found")

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console"):
                with patch("ktrdr.cli.checkpoints_commands.error_console"):
                    with patch("sys.exit") as mock_exit:
                        delete_checkpoint("nonexistent_op", force=True, verbose=False)

                        # Should have exited with error code 1
                        mock_exit.assert_called_once_with(1)

    def test_delete_checkpoint_shows_success_message(self, mock_sync_client):
        """Test that success message is displayed after deletion."""
        mock_sync_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "state": {"epoch": 29},
            },
        }
        mock_sync_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console") as mock_console:
                delete_checkpoint("op_training_123", force=True, verbose=False)

                # Check success message was printed
                calls = [str(call) for call in mock_console.print.call_args_list]
                output = "\n".join(calls)
                assert "deleted" in output.lower()

    def test_delete_checkpoint_shows_warning_for_resumable(self, mock_sync_client):
        """Test that warning is shown when deleting checkpoint for resumable op."""
        # Checkpoint type indicates it's from a cancellation (resumable)
        mock_sync_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
            },
        }
        mock_sync_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.console") as mock_console:
                with patch(
                    "ktrdr.cli.checkpoints_commands.typer.confirm",
                    return_value=True,
                ):
                    delete_checkpoint("op_training_123", force=False, verbose=False)

                    # Check warning message contains "resumable" or "not be resumable"
                    calls = [str(call) for call in mock_console.print.call_args_list]
                    output = "\n".join(calls)
                    assert "resumable" in output.lower() or "resume" in output.lower()

    def test_delete_checkpoint_api_connection_failure(self, mock_sync_client):
        """Test handling when API connection fails."""
        mock_sync_client.health_check.return_value = False

        with patch("ktrdr.cli.checkpoints_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.checkpoints_commands.error_console"):
                with patch("sys.exit") as mock_exit:
                    delete_checkpoint("op_training_123", force=True, verbose=False)

                    # Should have exited with error code 1
                    mock_exit.assert_called_once_with(1)

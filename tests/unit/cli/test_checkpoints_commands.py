"""Unit tests for checkpoints CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.cli.checkpoints_commands import _show_checkpoint_async


class TestShowCheckpointCommand:
    """Tests for checkpoints show command."""

    @pytest.fixture
    def mock_api_client(self):
        """Create a mock API client for testing."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock()
        return mock_client

    @pytest.mark.asyncio
    async def test_show_checkpoint_calls_api_correctly(self, mock_api_client):
        """Test that show command calls the API with correct operation ID."""
        mock_api_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
                "artifacts_path": "/app/data/checkpoints/op_training_123",
            },
        }

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console"):
                    await _show_checkpoint_async("op_training_123", verbose=False)

                    # Verify API was called correctly
                    mock_api_client.get.assert_called_once_with(
                        "/checkpoints/op_training_123"
                    )

    @pytest.mark.asyncio
    async def test_show_checkpoint_not_found_exits(self, mock_api_client):
        """Test handling when checkpoint doesn't exist."""
        mock_api_client.get.side_effect = Exception("404: not found")

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console"):
                    with patch("ktrdr.cli.checkpoints_commands.error_console"):
                        with patch("sys.exit") as mock_exit:
                            await _show_checkpoint_async(
                                "nonexistent_op", verbose=False
                            )

                            # Should have exited with error code 1
                            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_show_checkpoint_displays_resume_hint(self, mock_api_client):
        """Test that show command shows how to resume."""
        mock_api_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_abc123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
                "artifacts_path": "/app/data/checkpoints/op_training_abc123",
            },
        }

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console") as mock_console:
                    await _show_checkpoint_async("op_training_abc123", verbose=False)

                    # Check that print was called with resume hint
                    calls = [str(call) for call in mock_console.print.call_args_list]
                    output = "\n".join(calls)
                    assert "resume" in output.lower()
                    assert "op_training_abc123" in output

    @pytest.mark.asyncio
    async def test_show_checkpoint_handles_success_false(self, mock_api_client):
        """Test handling when API returns success=False."""
        mock_api_client.get.return_value = {
            "success": False,
            "data": None,
        }

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console"):
                    with patch("ktrdr.cli.checkpoints_commands.error_console"):
                        with patch("sys.exit") as mock_exit:
                            await _show_checkpoint_async(
                                "op_training_123", verbose=False
                            )

                            mock_exit.assert_called_once_with(1)


class TestDeleteCheckpointCommand:
    """Tests for checkpoints delete command."""

    @pytest.fixture
    def mock_api_client(self):
        """Create a mock API client for testing."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock()
        mock_client.delete = AsyncMock()
        return mock_client

    @pytest.mark.asyncio
    async def test_delete_checkpoint_calls_api_correctly(self, mock_api_client):
        """Test that delete command calls the DELETE API endpoint."""
        from ktrdr.cli.checkpoints_commands import _delete_checkpoint_async

        # Mock checkpoint exists
        mock_api_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
            },
        }
        # Mock successful deletion
        mock_api_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console"):
                    await _delete_checkpoint_async(
                        "op_training_123", force=True, verbose=False
                    )

                    # Verify DELETE API was called correctly
                    mock_api_client.delete.assert_called_once_with(
                        "/checkpoints/op_training_123"
                    )

    @pytest.mark.asyncio
    async def test_delete_checkpoint_shows_confirmation_prompt(self, mock_api_client):
        """Test that delete command shows confirmation prompt when force=False."""
        from ktrdr.cli.checkpoints_commands import _delete_checkpoint_async

        # Mock checkpoint exists
        mock_api_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
            },
        }
        mock_api_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console"):
                    with patch(
                        "ktrdr.cli.checkpoints_commands.typer.confirm",
                        return_value=True,
                    ) as mock_confirm:
                        await _delete_checkpoint_async(
                            "op_training_123", force=False, verbose=False
                        )

                        # Verify confirmation was requested
                        mock_confirm.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_checkpoint_aborted_on_no_confirmation(self, mock_api_client):
        """Test that delete is aborted when user says no to confirmation."""
        from ktrdr.cli.checkpoints_commands import _delete_checkpoint_async

        # Mock checkpoint exists
        mock_api_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
            },
        }

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console") as mock_console:
                    with patch(
                        "ktrdr.cli.checkpoints_commands.typer.confirm",
                        return_value=False,
                    ):
                        await _delete_checkpoint_async(
                            "op_training_123", force=False, verbose=False
                        )

                        # Delete should NOT have been called
                        mock_api_client.delete.assert_not_called()

                        # Should show aborted message
                        calls = [
                            str(call) for call in mock_console.print.call_args_list
                        ]
                        output = "\n".join(calls)
                        assert (
                            "aborted" in output.lower() or "cancelled" in output.lower()
                        )

    @pytest.mark.asyncio
    async def test_delete_checkpoint_force_skips_confirmation(self, mock_api_client):
        """Test that force flag skips confirmation prompt."""
        from ktrdr.cli.checkpoints_commands import _delete_checkpoint_async

        # Mock checkpoint exists
        mock_api_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "state": {"epoch": 29},
            },
        }
        mock_api_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console"):
                    with patch(
                        "ktrdr.cli.checkpoints_commands.typer.confirm"
                    ) as mock_confirm:
                        await _delete_checkpoint_async(
                            "op_training_123", force=True, verbose=False
                        )

                        # Confirmation should NOT be called with force=True
                        mock_confirm.assert_not_called()

                        # Delete should still be called
                        mock_api_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_checkpoint_not_found_exits(self, mock_api_client):
        """Test handling when checkpoint doesn't exist."""
        from ktrdr.cli.checkpoints_commands import _delete_checkpoint_async

        mock_api_client.get.side_effect = Exception("404: not found")

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console"):
                    with patch("ktrdr.cli.checkpoints_commands.error_console"):
                        with patch("sys.exit") as mock_exit:
                            await _delete_checkpoint_async(
                                "nonexistent_op", force=True, verbose=False
                            )

                            # Should have exited with error code 1
                            mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_delete_checkpoint_shows_success_message(self, mock_api_client):
        """Test that success message is displayed after deletion."""
        from ktrdr.cli.checkpoints_commands import _delete_checkpoint_async

        mock_api_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "state": {"epoch": 29},
            },
        }
        mock_api_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console") as mock_console:
                    await _delete_checkpoint_async(
                        "op_training_123", force=True, verbose=False
                    )

                    # Check success message was printed
                    calls = [str(call) for call in mock_console.print.call_args_list]
                    output = "\n".join(calls)
                    assert "deleted" in output.lower()

    @pytest.mark.asyncio
    async def test_delete_checkpoint_shows_warning_for_resumable(self, mock_api_client):
        """Test that warning is shown when deleting checkpoint for resumable operation."""
        from ktrdr.cli.checkpoints_commands import _delete_checkpoint_async

        # Checkpoint type indicates it's from a cancellation (resumable)
        mock_api_client.get.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_training_123",
                "checkpoint_type": "cancellation",
                "created_at": "2024-12-13T14:35:00Z",
                "state": {"epoch": 29},
            },
        }
        mock_api_client.delete.return_value = {
            "success": True,
            "message": "Checkpoint deleted",
        }

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.checkpoints_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.checkpoints_commands.console") as mock_console:
                    with patch(
                        "ktrdr.cli.checkpoints_commands.typer.confirm",
                        return_value=True,
                    ):
                        await _delete_checkpoint_async(
                            "op_training_123", force=False, verbose=False
                        )

                        # Check warning message contains "resumable" or "not be resumable"
                        calls = [
                            str(call) for call in mock_console.print.call_args_list
                        ]
                        output = "\n".join(calls)
                        assert (
                            "resumable" in output.lower() or "resume" in output.lower()
                        )

    @pytest.mark.asyncio
    async def test_delete_checkpoint_api_connection_failure(self, mock_api_client):
        """Test handling when API connection fails."""
        from ktrdr.cli.checkpoints_commands import _delete_checkpoint_async

        with patch(
            "ktrdr.cli.checkpoints_commands.check_api_connection",
            return_value=False,
        ):
            with patch("ktrdr.cli.checkpoints_commands.error_console"):
                with patch("sys.exit") as mock_exit:
                    await _delete_checkpoint_async(
                        "op_training_123", force=True, verbose=False
                    )

                    # Should have exited with error code 1
                    mock_exit.assert_called_once_with(1)

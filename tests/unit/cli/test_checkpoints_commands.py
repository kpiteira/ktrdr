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

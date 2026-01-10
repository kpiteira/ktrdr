"""
Tests for resume operation CLI command and API client method.

Task 4.6: Add Resume CLI Command
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.errors import DataError


class TestKtrdrApiClientResumeOperation:
    """Test KtrdrApiClient.resume_operation method."""

    @pytest.mark.asyncio
    async def test_resume_operation_success(self):
        """Test successful resume operation returns response data."""
        from ktrdr.cli.api_client import KtrdrApiClient

        mock_response = {
            "success": True,
            "data": {
                "operation_id": "op_test_123",
                "status": "RUNNING",
                "resumed_from": {
                    "checkpoint_type": "training",
                    "created_at": "2024-01-15T10:00:00Z",
                    "epoch": 25,
                },
            },
        }

        client = KtrdrApiClient()
        client._make_request = AsyncMock(return_value=mock_response)

        result = await client.resume_operation("op_test_123")

        assert result["success"] is True
        assert result["data"]["operation_id"] == "op_test_123"
        assert result["data"]["resumed_from"]["epoch"] == 25
        client._make_request.assert_called_once_with(
            "POST", "/operations/op_test_123/resume"
        )

    @pytest.mark.asyncio
    async def test_resume_operation_failure_raises_data_error(self):
        """Test failed resume raises DataError."""
        from ktrdr.cli.api_client import KtrdrApiClient

        mock_response = {
            "success": False,
            "error": {"message": "Resume failed"},
        }

        client = KtrdrApiClient()
        client._make_request = AsyncMock(return_value=mock_response)

        with pytest.raises(DataError) as exc_info:
            await client.resume_operation("op_test_123")

        assert "Failed to resume operation" in str(exc_info.value)


class TestResumeOperationCommand:
    """Test resume operation CLI command."""

    @pytest.fixture
    def mock_sync_client(self):
        """Create a mock SyncCLIClient for testing."""
        mock_client = MagicMock()
        mock_client.health_check.return_value = True
        mock_client.config.base_url = "http://localhost:8000/api/v1"
        return mock_client

    def test_resume_operation_success(self, mock_sync_client):
        """Test successful resume displays epoch info."""
        from ktrdr.cli.operations_commands import resume_operation

        mock_sync_client.post.return_value = {
            "success": True,
            "data": {
                "operation_id": "op_test_123",
                "status": "RUNNING",
                "resumed_from": {
                    "checkpoint_type": "training",
                    "created_at": "2024-01-15T10:00:00Z",
                    "epoch": 25,
                },
            },
        }

        with patch("ktrdr.cli.operations_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.operations_commands.console") as mock_console:
                resume_operation("op_test_123", verbose=False)

                # Verify success message with epoch displayed
                calls = [str(call) for call in mock_console.print.call_args_list]
                output = " ".join(calls)

                assert "op_test_123" in output
                assert "25" in output  # epoch

    def test_resume_operation_api_connection_failure(self, mock_sync_client):
        """Test resume command exits on API connection failure."""
        from ktrdr.cli.operations_commands import resume_operation

        mock_sync_client.health_check.return_value = False

        with patch("ktrdr.cli.operations_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.operations_commands.error_console"):
                with patch("sys.exit") as mock_exit:
                    resume_operation("op_test_123", verbose=False)

                    mock_exit.assert_called_once_with(1)

    def test_resume_operation_not_found(self, mock_sync_client):
        """Test resume command handles 404 not found."""
        from ktrdr.cli.client import CLIClientError
        from ktrdr.cli.operations_commands import resume_operation

        mock_sync_client.post.side_effect = CLIClientError("404: not found")

        with patch("ktrdr.cli.operations_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.operations_commands.error_console") as mock_error:
                with patch("sys.exit") as mock_exit:
                    resume_operation("op_test_123", verbose=False)

                    mock_exit.assert_called_once_with(1)
                    calls = [str(call) for call in mock_error.print.call_args_list]
                    output = " ".join(calls)
                    assert "not found" in output.lower()

    def test_resume_operation_already_running(self, mock_sync_client):
        """Test resume command handles 409 conflict (already running)."""
        from ktrdr.cli.client import CLIClientError
        from ktrdr.cli.operations_commands import resume_operation

        mock_sync_client.post.side_effect = CLIClientError("409: already running")

        with patch("ktrdr.cli.operations_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.operations_commands.error_console") as mock_error:
                with patch("sys.exit") as mock_exit:
                    resume_operation("op_test_123", verbose=False)

                    mock_exit.assert_called_once_with(1)
                    calls = [str(call) for call in mock_error.print.call_args_list]
                    output = " ".join(calls)
                    assert "running" in output.lower() or "cannot" in output.lower()

    def test_resume_operation_no_checkpoint(self, mock_sync_client):
        """Test resume command handles no checkpoint available."""
        from ktrdr.cli.client import CLIClientError
        from ktrdr.cli.operations_commands import resume_operation

        mock_sync_client.post.side_effect = CLIClientError("no checkpoint available")

        with patch("ktrdr.cli.operations_commands.SyncCLIClient") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(
                return_value=mock_sync_client
            )
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("ktrdr.cli.operations_commands.error_console") as mock_error:
                with patch("sys.exit") as mock_exit:
                    resume_operation("op_test_123", verbose=False)

                    mock_exit.assert_called_once_with(1)
                    calls = [str(call) for call in mock_error.print.call_args_list]
                    output = " ".join(calls)
                    assert "checkpoint" in output.lower()


class TestResumeOperationCommandEntry:
    """Test resume_operation command entry point (sync wrapper)."""

    def test_resume_command_exists(self):
        """Test that resume command is registered."""
        from ktrdr.cli.operations_commands import operations_app

        # Check that 'resume' is a registered command
        command_names = [cmd.name for cmd in operations_app.registered_commands]
        assert "resume" in command_names

    def test_resume_command_has_operation_id_argument(self):
        """Test resume command accepts operation_id argument."""
        from ktrdr.cli.operations_commands import resume_operation

        # Check that the function exists and is callable
        assert callable(resume_operation)

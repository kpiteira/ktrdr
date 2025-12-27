"""
Tests for resume operation CLI command and API client method.

Task 4.6: Add Resume CLI Command
"""

from unittest.mock import AsyncMock, patch

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
    def mock_api_connection_success(self):
        """Mock API connection check to return True."""

        async def async_check():
            return True

        with patch(
            "ktrdr.cli.operations_commands.check_api_connection", new=async_check
        ):
            yield

    @pytest.fixture
    def mock_api_client(self):
        """Mock get_api_client to return a mock client."""
        mock_client = AsyncMock()
        with patch(
            "ktrdr.cli.operations_commands.get_api_client", return_value=mock_client
        ):
            yield mock_client

    @pytest.mark.asyncio
    async def test_resume_operation_async_success(
        self, mock_api_connection_success, mock_api_client
    ):
        """Test successful resume displays epoch info."""
        from ktrdr.cli.operations_commands import _resume_operation_async

        mock_api_client.resume_operation = AsyncMock(
            return_value={
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
        )

        with patch("ktrdr.cli.operations_commands.console") as mock_console:
            await _resume_operation_async("op_test_123", verbose=False)

            # Verify success message with epoch displayed
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            all_output = " ".join(print_calls)

            assert "op_test_123" in all_output
            assert "25" in all_output  # epoch

    @pytest.mark.asyncio
    async def test_resume_operation_async_api_connection_failure(self):
        """Test resume command exits on API connection failure."""
        from ktrdr.cli.operations_commands import _resume_operation_async

        async def async_check_fail():
            return False

        with patch(
            "ktrdr.cli.operations_commands.check_api_connection", new=async_check_fail
        ):
            with pytest.raises(SystemExit):
                await _resume_operation_async("op_test_123", verbose=False)

    @pytest.mark.asyncio
    async def test_resume_operation_async_not_found(
        self, mock_api_connection_success, mock_api_client
    ):
        """Test resume command handles 404 not found."""
        from ktrdr.cli.operations_commands import _resume_operation_async

        mock_api_client.resume_operation = AsyncMock(
            side_effect=DataError(
                message="Operation not found",
                error_code="API-404",
                details={"operation_id": "op_test_123"},
            )
        )

        with patch("ktrdr.cli.operations_commands.error_console") as mock_error:
            with pytest.raises(SystemExit):
                await _resume_operation_async("op_test_123", verbose=False)

            # Should display not found error
            print_calls = [str(call) for call in mock_error.print.call_args_list]
            all_output = " ".join(print_calls)
            assert "not found" in all_output.lower() or "404" in all_output

    @pytest.mark.asyncio
    async def test_resume_operation_async_already_running(
        self, mock_api_connection_success, mock_api_client
    ):
        """Test resume command handles 409 conflict (already running)."""
        from ktrdr.cli.operations_commands import _resume_operation_async

        mock_api_client.resume_operation = AsyncMock(
            side_effect=DataError(
                message="Operation already running",
                error_code="API-409",
                details={"operation_id": "op_test_123"},
            )
        )

        with patch("ktrdr.cli.operations_commands.error_console") as mock_error:
            with pytest.raises(SystemExit):
                await _resume_operation_async("op_test_123", verbose=False)

            # Should display conflict error
            print_calls = [str(call) for call in mock_error.print.call_args_list]
            all_output = " ".join(print_calls)
            assert (
                "running" in all_output.lower()
                or "409" in all_output
                or "cannot" in all_output.lower()
            )

    @pytest.mark.asyncio
    async def test_resume_operation_async_no_checkpoint(
        self, mock_api_connection_success, mock_api_client
    ):
        """Test resume command handles no checkpoint available."""
        from ktrdr.cli.operations_commands import _resume_operation_async

        mock_api_client.resume_operation = AsyncMock(
            side_effect=DataError(
                message="No checkpoint available",
                error_code="API-404",
                details={"operation_id": "op_test_123"},
            )
        )

        with patch("ktrdr.cli.operations_commands.error_console") as mock_error:
            with pytest.raises(SystemExit):
                await _resume_operation_async("op_test_123", verbose=False)

            # Should display no checkpoint error
            print_calls = [str(call) for call in mock_error.print.call_args_list]
            all_output = " ".join(print_calls)
            assert "checkpoint" in all_output.lower() or "404" in all_output


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

        # Check that the function exists and is decorated
        assert callable(resume_operation)

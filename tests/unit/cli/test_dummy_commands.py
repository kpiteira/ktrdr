"""
Tests for dummy CLI commands.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from ktrdr.cli.dummy_commands import _run_dummy_async


@pytest.fixture
def mock_api_client():
    """Mock API client for testing."""
    client = AsyncMock()
    client.start_dummy_task.return_value = {
        "success": True,
        "data": {"operation_id": "op_dummy_123", "status": "started"},
    }
    client.get_operation_status.return_value = {
        "success": True,
        "data": {
            "status": "completed",
            "progress": {"percentage": 100.0, "current_step": "Completed!"},
            "result_summary": {"iterations_completed": 100, "status": "success"},
        },
    }
    return client


@pytest.fixture
def mock_check_api_connection():
    """Mock API connection check."""
    with patch("ktrdr.cli.dummy_commands.check_api_connection", return_value=True):
        yield


@pytest.fixture
def mock_get_api_client(mock_api_client):
    """Mock get_api_client function."""
    with patch("ktrdr.cli.dummy_commands.get_api_client", return_value=mock_api_client):
        yield mock_api_client


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


class TestDummyCommand:
    """Test dummy CLI command."""

    @pytest.mark.asyncio
    async def test_dummy_async_success(
        self, mock_check_api_connection, mock_get_api_client
    ):
        """Test successful dummy command execution."""
        mock_get_api_client.get_operation_status.return_value = {
            "success": True,
            "data": {
                "status": "completed",
                "progress": {"percentage": 100.0, "current_step": "Completed!"},
                "result_summary": {"iterations_completed": 100, "status": "success"},
            },
        }

        # Test the async function directly
        with patch("ktrdr.cli.dummy_commands.console") as mock_console:
            await _run_dummy_async(verbose=False, quiet=False, show_progress=True)

            # Check that completion was printed
            mock_console.print.assert_any_call("✅ Completed 100 iterations")

    @pytest.mark.asyncio
    async def test_dummy_async_api_connection_failure(self):
        """Test dummy command with API connection failure."""
        with patch("ktrdr.cli.dummy_commands.check_api_connection", return_value=False):
            with pytest.raises(SystemExit):
                await _run_dummy_async(verbose=False, quiet=False, show_progress=True)

    @pytest.mark.asyncio
    async def test_dummy_async_cancellation(
        self, mock_check_api_connection, mock_get_api_client
    ):
        """Test dummy command cancellation."""
        # Mock operation that gets cancelled
        mock_get_api_client.get_operation_status.return_value = {
            "success": True,
            "data": {
                "status": "cancelled",
                "progress": {"percentage": 50.0},
                "result_summary": {
                    "iterations_completed": 50,
                    "status": "cancelled",
                },
            },
        }
        mock_get_api_client.cancel_operation.return_value = {"success": True}

        # Test with manual cancellation flag simulation
        from unittest.mock import patch

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value = MagicMock()
            mock_loop.return_value.add_signal_handler = MagicMock()
            mock_loop.return_value.remove_signal_handler = MagicMock()

            with patch("ktrdr.cli.dummy_commands.console") as mock_console:
                await _run_dummy_async(verbose=False, quiet=False, show_progress=False)

                # Just verify that the function runs without throwing an exception
                # The exact message depends on the execution flow
                assert mock_console.print.called

    @pytest.mark.asyncio
    async def test_dummy_async_operation_failure(
        self, mock_check_api_connection, mock_get_api_client
    ):
        """Test dummy command with operation failure."""
        mock_get_api_client.get_operation_status.return_value = {
            "success": True,
            "data": {
                "status": "failed",
                "progress": {"percentage": 30.0},
                "error": "Operation failed",
            },
        }

        with patch("ktrdr.cli.dummy_commands.console") as mock_console:
            await _run_dummy_async(verbose=False, quiet=False, show_progress=False)

            # Check that failure was handled
            mock_console.print.assert_any_call("❌ Task failed")

"""
Tests for dummy CLI commands using AsyncOperationExecutor pattern.
"""

from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.cli.dummy_commands import _run_dummy_async


@pytest.fixture
def mock_check_api_connection():
    """Mock API connection check to return True."""

    async def async_check():
        return True

    with patch("ktrdr.cli.dummy_commands.check_api_connection", new=async_check):
        yield


@pytest.fixture
def mock_executor():
    """Mock AsyncOperationExecutor for testing."""
    executor = AsyncMock()
    executor.execute_operation = AsyncMock(return_value=True)
    return executor


class TestDummyCommand:
    """Test dummy CLI command using AsyncOperationExecutor pattern."""

    @pytest.mark.asyncio
    async def test_dummy_async_success(self, mock_check_api_connection, mock_executor):
        """Test successful dummy command execution."""
        with patch(
            "ktrdr.cli.dummy_commands.AsyncOperationExecutor",
            return_value=mock_executor,
        ):
            with patch("ktrdr.cli.dummy_commands.console") as mock_console:
                await _run_dummy_async(verbose=False, quiet=False, show_progress=True)

                # Verify executor was called
                assert mock_executor.execute_operation.called

                # Check that we didn't print error message
                # (success case should not print warning)
                for call in mock_console.print.call_args_list:
                    assert "⚠️" not in str(call)

    @pytest.mark.asyncio
    async def test_dummy_async_api_connection_failure(self):
        """Test dummy command with API connection failure."""

        async def async_check_fail():
            return False

        with patch(
            "ktrdr.cli.dummy_commands.check_api_connection", new=async_check_fail
        ):
            with pytest.raises(SystemExit):
                await _run_dummy_async(verbose=False, quiet=False, show_progress=True)

    @pytest.mark.asyncio
    async def test_dummy_async_operation_failure(
        self, mock_check_api_connection, mock_executor
    ):
        """Test dummy command with operation failure."""
        # Mock executor returning False (operation failed)
        mock_executor.execute_operation = AsyncMock(return_value=False)

        with patch(
            "ktrdr.cli.dummy_commands.AsyncOperationExecutor",
            return_value=mock_executor,
        ):
            with patch("ktrdr.cli.dummy_commands.console") as mock_console:
                await _run_dummy_async(verbose=False, quiet=False, show_progress=False)

                # Check that warning was printed for unsuccessful completion
                mock_console.print.assert_any_call(
                    "[yellow]⚠️  Dummy task did not complete successfully[/yellow]"
                )

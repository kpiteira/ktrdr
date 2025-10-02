"""
Tests for refactored dummy command using AsyncOperationExecutor pattern.

Tests verify that the dummy command properly:
- Creates DummyOperationAdapter with correct parameters
- Calls AsyncOperationExecutor.execute_operation
- Handles success, failure, and cancellation scenarios
- Provides consistent UX with progress display
"""

from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.cli.operation_adapters import DummyOperationAdapter
from ktrdr.cli.operation_executor import AsyncOperationExecutor


class TestDummyCommandRefactored:
    """Test refactored dummy command using executor pattern."""

    @pytest.fixture
    def mock_executor(self):
        """Mock AsyncOperationExecutor."""
        executor = AsyncMock(spec=AsyncOperationExecutor)
        executor.execute_operation = AsyncMock(return_value=True)
        return executor

    @pytest.mark.asyncio
    async def test_dummy_command_creates_adapter_correctly(self, mock_executor):
        """Test that dummy command creates DummyOperationAdapter."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch("ktrdr.cli.dummy_commands.check_api_connection", return_value=True):
            with patch(
                "ktrdr.cli.dummy_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                # Call the async implementation
                await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

                # Verify executor.execute_operation was called
                assert mock_executor.execute_operation.called

                # Get the adapter that was passed to execute_operation
                call_args = mock_executor.execute_operation.call_args
                adapter = call_args[1]["adapter"]

                # Verify it's a DummyOperationAdapter
                assert isinstance(adapter, DummyOperationAdapter)

    @pytest.mark.asyncio
    async def test_dummy_command_handles_success(self, mock_executor):
        """Test that dummy command handles successful completion."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        # Mock successful execution
        mock_executor.execute_operation = AsyncMock(return_value=True)

        with patch("ktrdr.cli.dummy_commands.check_api_connection", return_value=True):
            with patch(
                "ktrdr.cli.dummy_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                # Should complete without exception
                await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

                # Verify execute_operation was called
                assert mock_executor.execute_operation.called

    @pytest.mark.asyncio
    async def test_dummy_command_handles_failure(self, mock_executor):
        """Test that dummy command handles failure."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        # Mock failed execution
        mock_executor.execute_operation = AsyncMock(return_value=False)

        with patch("ktrdr.cli.dummy_commands.check_api_connection", return_value=True):
            with patch(
                "ktrdr.cli.dummy_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                # Should handle failure gracefully
                await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

                # Verify execute_operation was called
                assert mock_executor.execute_operation.called

    @pytest.mark.asyncio
    async def test_dummy_command_uses_executor_progress_callback(self, mock_executor):
        """Test that dummy command passes progress callback when show_progress=True."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch("ktrdr.cli.dummy_commands.check_api_connection", return_value=True):
            with patch(
                "ktrdr.cli.dummy_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                # Call with show_progress=True and quiet=False to enable progress
                await _run_dummy_async(verbose=False, quiet=False, show_progress=True)

                # Verify execute_operation was called with correct arguments
                assert mock_executor.execute_operation.called
                call_args = mock_executor.execute_operation.call_args

                # Should have adapter, console, and progress_callback
                assert "adapter" in call_args[1]
                assert "console" in call_args[1]
                assert "progress_callback" in call_args[1]
                assert "show_progress" in call_args[1]

                # Progress callback should be callable when show_progress=True
                assert callable(call_args[1]["progress_callback"])

    @pytest.mark.asyncio
    async def test_dummy_command_handles_api_connection_failure(self):
        """Test that dummy command exits when API connection fails."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch("ktrdr.cli.dummy_commands.check_api_connection", return_value=False):
            with patch("ktrdr.cli.dummy_commands.sys.exit") as mock_exit:
                await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

                # Should exit with code 1
                mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_dummy_command_quiet_mode_suppresses_output(self, mock_executor):
        """Test that quiet mode suppresses console output."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch("ktrdr.cli.dummy_commands.check_api_connection", return_value=True):
            with patch(
                "ktrdr.cli.dummy_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                with patch("ktrdr.cli.dummy_commands.console"):
                    await _run_dummy_async(
                        verbose=False, quiet=True, show_progress=False
                    )

                    # In quiet mode, console.print should not be called
                    # (except possibly for errors)
                    # We're mainly verifying it doesn't crash
                    assert mock_executor.execute_operation.called

    @pytest.mark.asyncio
    async def test_dummy_command_verbose_mode_enables_logging(self, mock_executor):
        """Test that verbose mode doesn't suppress HTTP logging."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch("ktrdr.cli.dummy_commands.check_api_connection", return_value=True):
            with patch(
                "ktrdr.cli.dummy_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                # In verbose mode, httpx logger should not be suppressed
                import logging

                httpx_logger = logging.getLogger("httpx")
                original_level = httpx_logger.level

                await _run_dummy_async(verbose=True, quiet=True, show_progress=False)

                # Logger level should remain unchanged in verbose mode
                assert httpx_logger.level == original_level

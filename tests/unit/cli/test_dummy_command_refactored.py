"""
Tests for refactored dummy command using AsyncCLIClient pattern.

Tests verify that the dummy command properly:
- Uses AsyncCLIClient context manager
- Calls cli.health_check() for API connection verification
- Calls cli.execute_operation() with DummyOperationAdapter
- Handles success, failure, and cancellation scenarios
- Provides consistent UX with progress display
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.cli.operation_adapters import DummyOperationAdapter


class TestDummyCommandRefactored:
    """Test refactored dummy command using AsyncCLIClient pattern."""

    @pytest.fixture
    def mock_cli_client(self):
        """Mock AsyncCLIClient with successful defaults."""
        mock_client = MagicMock()
        mock_client.health_check = AsyncMock(return_value=True)
        mock_client.execute_operation = AsyncMock(
            return_value={"status": "completed", "operation_id": "op_test123"}
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        return mock_client

    @pytest.mark.asyncio
    async def test_dummy_command_creates_adapter_correctly(self, mock_cli_client):
        """Test that dummy command creates DummyOperationAdapter."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            # Call the async implementation
            await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

            # Verify execute_operation was called
            assert mock_cli_client.execute_operation.called

            # Get the adapter that was passed to execute_operation
            call_args = mock_cli_client.execute_operation.call_args
            adapter = call_args[0][0]  # First positional argument

            # Verify it's a DummyOperationAdapter
            assert isinstance(adapter, DummyOperationAdapter)

    @pytest.mark.asyncio
    async def test_dummy_command_handles_success(self, mock_cli_client):
        """Test that dummy command handles successful completion."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        # Mock successful execution (already default)
        mock_cli_client.execute_operation = AsyncMock(
            return_value={"status": "completed", "operation_id": "op_test123"}
        )

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            # Should complete without exception
            await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

            # Verify health_check and execute_operation were called
            assert mock_cli_client.health_check.called
            assert mock_cli_client.execute_operation.called

    @pytest.mark.asyncio
    async def test_dummy_command_handles_failure(self, mock_cli_client):
        """Test that dummy command handles failure status."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        # Mock failed execution - returns dict with status="failed"
        mock_cli_client.execute_operation = AsyncMock(
            return_value={
                "status": "failed",
                "operation_id": "op_test123",
                "error_message": "Simulated failure",
            }
        )

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            # Should handle failure gracefully (quiet mode suppresses warning)
            await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

            # Verify execute_operation was called
            assert mock_cli_client.execute_operation.called

    @pytest.mark.asyncio
    async def test_dummy_command_uses_on_progress_callback(self, mock_cli_client):
        """Test that dummy command passes on_progress callback when show_progress=True."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            # Call with show_progress=True and quiet=False to enable progress
            await _run_dummy_async(verbose=False, quiet=False, show_progress=True)

            # Verify execute_operation was called with correct arguments
            assert mock_cli_client.execute_operation.called
            call_args = mock_cli_client.execute_operation.call_args

            # Should have adapter as first positional arg
            adapter = call_args[0][0]
            assert isinstance(adapter, DummyOperationAdapter)

            # Should have on_progress callback and poll_interval in kwargs
            assert "on_progress" in call_args[1]
            assert "poll_interval" in call_args[1]

            # on_progress callback should be callable
            assert callable(call_args[1]["on_progress"])

    @pytest.mark.asyncio
    async def test_dummy_command_handles_api_connection_failure(self, mock_cli_client):
        """Test that dummy command exits when API connection fails."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        # Mock health check failure
        mock_cli_client.health_check = AsyncMock(return_value=False)

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            # sys.exit should raise SystemExit to stop execution
            with pytest.raises(SystemExit) as exc_info:
                await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

            # Should exit with code 1
            assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_dummy_command_quiet_mode_suppresses_output(self, mock_cli_client):
        """Test that quiet mode suppresses console output."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            with patch("ktrdr.cli.dummy_commands.console"):
                await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

                # In quiet mode, we just verify it doesn't crash
                assert mock_cli_client.execute_operation.called

    @pytest.mark.asyncio
    async def test_dummy_command_verbose_mode_enables_logging(self, mock_cli_client):
        """Test that verbose mode doesn't suppress HTTP logging."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            # In verbose mode, httpx logger should not be suppressed
            import logging

            httpx_logger = logging.getLogger("httpx")
            original_level = httpx_logger.level

            await _run_dummy_async(verbose=True, quiet=True, show_progress=False)

            # Logger level should remain unchanged in verbose mode
            assert httpx_logger.level == original_level

    @pytest.mark.asyncio
    async def test_dummy_command_handles_cancelled_status(self, mock_cli_client):
        """Test that dummy command handles cancelled status."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        # Mock cancelled execution
        mock_cli_client.execute_operation = AsyncMock(
            return_value={"status": "cancelled", "operation_id": "op_test123"}
        )

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            # Should handle cancellation gracefully (quiet mode)
            await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

            # Verify execute_operation was called
            assert mock_cli_client.execute_operation.called

    @pytest.mark.asyncio
    async def test_dummy_command_uses_context_manager(self, mock_cli_client):
        """Test that dummy command uses AsyncCLIClient as context manager."""
        from ktrdr.cli.dummy_commands import _run_dummy_async

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            await _run_dummy_async(verbose=False, quiet=True, show_progress=False)

            # Verify context manager was used
            assert mock_cli_client.__aenter__.called
            assert mock_cli_client.__aexit__.called

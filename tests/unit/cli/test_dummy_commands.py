"""
Tests for dummy CLI commands using AsyncCLIClient pattern.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.cli.dummy_commands import _run_dummy_async


@pytest.fixture
def mock_cli_client():
    """Mock AsyncCLIClient with successful defaults."""
    mock_client = MagicMock()
    mock_client.health_check = AsyncMock(return_value=True)
    mock_client.execute_operation = AsyncMock(
        return_value={"status": "completed", "operation_id": "op_test123"}
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class TestDummyCommand:
    """Test dummy CLI command using AsyncCLIClient pattern."""

    @pytest.mark.asyncio
    async def test_dummy_async_success(self, mock_cli_client):
        """Test successful dummy command execution."""
        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            with patch("ktrdr.cli.dummy_commands.console") as mock_console:
                await _run_dummy_async(verbose=False, quiet=False, show_progress=True)

                # Verify health_check and execute_operation were called
                assert mock_cli_client.health_check.called
                assert mock_cli_client.execute_operation.called

                # Check that success message was printed
                mock_console.print.assert_any_call(
                    "[green]Dummy task completed successfully![/green]"
                )

    @pytest.mark.asyncio
    async def test_dummy_async_api_connection_failure(self, mock_cli_client):
        """Test dummy command with API connection failure."""
        # Mock health check failure
        mock_cli_client.health_check = AsyncMock(return_value=False)

        with patch(
            "ktrdr.cli.dummy_commands.AsyncCLIClient",
            return_value=mock_cli_client,
        ):
            with pytest.raises(SystemExit):
                await _run_dummy_async(verbose=False, quiet=False, show_progress=True)

    @pytest.mark.asyncio
    async def test_dummy_async_operation_failure(self, mock_cli_client):
        """Test dummy command with operation failure."""
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
            with patch("ktrdr.cli.dummy_commands.console") as mock_console:
                await _run_dummy_async(verbose=False, quiet=False, show_progress=False)

                # Check that failure message was printed
                mock_console.print.assert_any_call(
                    "[red]Dummy task failed: Simulated failure[/red]"
                )

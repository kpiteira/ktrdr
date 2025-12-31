"""Unit tests for operations CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.cli.operations_commands import _list_operations_async


class TestListOperationsWithCheckpoints:
    """Tests for operations list command with checkpoint support."""

    @pytest.fixture
    def mock_api_client(self):
        """Create a mock API client for testing."""
        mock_client = MagicMock()
        mock_client.list_operations = AsyncMock()
        mock_client.get = AsyncMock()
        mock_client.format_duration = MagicMock(side_effect=lambda x: f"{x}s")
        return mock_client

    @pytest.fixture
    def sample_operations(self):
        """Sample operations data."""
        return {
            "data": [
                {
                    "operation_id": "op_training_123",
                    "operation_type": "training",
                    "status": "cancelled",
                    "progress_percentage": 29,
                    "symbol": "AAPL",
                    "duration_seconds": 3600,
                    "created_at": "2024-12-13T14:30:22Z",
                },
                {
                    "operation_id": "op_training_456",
                    "operation_type": "training",
                    "status": "cancelled",
                    "progress_percentage": 45,
                    "symbol": "MSFT",
                    "duration_seconds": 7200,
                    "created_at": "2024-12-10T09:15:00Z",
                },
                {
                    "operation_id": "op_backtesting_789",
                    "operation_type": "backtesting",
                    "status": "completed",
                    "progress_percentage": 100,
                    "symbol": "GOOGL",
                    "duration_seconds": 1800,
                    "created_at": "2024-12-12T10:00:00Z",
                },
            ],
            "total_count": 3,
            "active_count": 0,
        }

    @pytest.mark.asyncio
    async def test_list_operations_shows_checkpoint_column(
        self, mock_api_client, sample_operations
    ):
        """Test that operations list includes checkpoint information."""
        mock_api_client.list_operations.return_value = sample_operations

        # Mock checkpoint responses - first two have checkpoints, third doesn't
        async def mock_get(path):
            if path == "/checkpoints/op_training_123":
                return {
                    "success": True,
                    "data": {
                        "operation_id": "op_training_123",
                        "state": {"epoch": 29, "train_loss": 0.28},
                    },
                }
            elif path == "/checkpoints/op_training_456":
                return {
                    "success": True,
                    "data": {
                        "operation_id": "op_training_456",
                        "state": {"epoch": 45, "train_loss": 0.31},
                    },
                }
            else:
                # No checkpoint for backtesting_789
                raise Exception("404: not found")

        mock_api_client.get.side_effect = mock_get

        with patch(
            "ktrdr.cli.operations_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.operations_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.operations_commands.console"):
                    # Call the function
                    await _list_operations_async(
                        status="cancelled",
                        operation_type=None,
                        limit=50,
                        active_only=False,
                        verbose=False,
                        resumable=False,
                    )

                    # Verify checkpoint info was fetched
                    assert mock_api_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_list_operations_resumable_flag_filters(
        self, mock_api_client, sample_operations
    ):
        """Test that --resumable flag filters to only resumable operations."""
        mock_api_client.list_operations.return_value = sample_operations

        # Mock checkpoint responses
        async def mock_get(path):
            if "op_training_123" in path:
                return {
                    "success": True,
                    "data": {"state": {"epoch": 29}},
                }
            elif "op_training_456" in path:
                return {
                    "success": True,
                    "data": {"state": {"epoch": 45}},
                }
            else:
                raise Exception("404: not found")

        mock_api_client.get.side_effect = mock_get

        with patch(
            "ktrdr.cli.operations_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.operations_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.operations_commands.console") as mock_console:
                    # Track table rows
                    tables_printed = []

                    def capture_print(*args, **kwargs):
                        from rich.table import Table

                        if args and isinstance(args[0], Table):
                            tables_printed.append(args[0])

                    mock_console.print = MagicMock(side_effect=capture_print)

                    await _list_operations_async(
                        status=None,
                        operation_type=None,
                        limit=50,
                        active_only=False,
                        verbose=False,
                        resumable=True,  # Only show resumable
                    )

                    # Verify filtering: only 2 operations should be shown
                    # (op_training_123 and op_training_456 have checkpoints)
                    assert len(tables_printed) == 1
                    table = tables_printed[0]
                    assert len(table.rows) == 2

    @pytest.mark.asyncio
    async def test_list_operations_shows_resumable_count_in_summary(
        self, mock_api_client, sample_operations
    ):
        """Test that summary shows resumable count."""
        mock_api_client.list_operations.return_value = sample_operations

        async def mock_get(path):
            if "op_training_123" in path or "op_training_456" in path:
                return {
                    "success": True,
                    "data": {"state": {"epoch": 29}},
                }
            else:
                raise Exception("404: not found")

        mock_api_client.get.side_effect = mock_get

        with patch(
            "ktrdr.cli.operations_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.operations_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.operations_commands.console") as mock_console:
                    printed_texts = []

                    def capture_print(*args, **kwargs):
                        if args:
                            printed_texts.append(str(args[0]))

                    mock_console.print = MagicMock(side_effect=capture_print)

                    await _list_operations_async(
                        status=None,
                        operation_type=None,
                        limit=50,
                        active_only=False,
                        verbose=False,
                        resumable=False,
                    )

                    # Check that resumable count is shown
                    summary_found = any(
                        "resumable" in text.lower() for text in printed_texts
                    )
                    assert (
                        summary_found
                    ), f"Expected 'resumable' in output, got: {printed_texts}"

    @pytest.mark.asyncio
    async def test_list_operations_handles_checkpoint_fetch_errors(
        self, mock_api_client, sample_operations
    ):
        """Test graceful handling of checkpoint fetch errors."""
        mock_api_client.list_operations.return_value = sample_operations

        # All checkpoint fetches fail
        mock_api_client.get.side_effect = Exception("Connection error")

        with patch(
            "ktrdr.cli.operations_commands.check_api_connection",
            return_value=True,
        ):
            with patch(
                "ktrdr.cli.operations_commands.get_api_client",
                return_value=mock_api_client,
            ):
                with patch("ktrdr.cli.operations_commands.console"):
                    # Should not raise - errors should be handled gracefully
                    await _list_operations_async(
                        status=None,
                        operation_type=None,
                        limit=50,
                        active_only=False,
                        verbose=False,
                        resumable=False,
                    )

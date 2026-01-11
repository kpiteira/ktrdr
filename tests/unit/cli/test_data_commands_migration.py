"""Tests for data_commands.py migration to AsyncCLIClient.

These tests verify that the data commands use the new AsyncCLIClient instead
of the old api_client.py module.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestLoadDataMigration:
    """Tests for _load_data_async migration to AsyncCLIClient."""

    @pytest.mark.asyncio
    async def test_load_data_uses_async_cli_client(self):
        """Test that _load_data_async uses AsyncCLIClient not api_client."""
        from ktrdr.cli.data_commands import _load_data_async

        # Arrange
        mock_cli = AsyncMock()
        mock_cli.health_check = AsyncMock(return_value=True)
        mock_cli.post = AsyncMock(
            return_value={
                "success": True,
                "operation_id": "op_123",
            }
        )
        # Return completed status on first poll
        mock_cli.get = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "status": "completed",
                    "progress": {"percentage": 100},
                },
            }
        )

        with (
            patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class,
            patch("ktrdr.cli.data_commands.console"),
            patch("ktrdr.cli.data_commands.error_console"),
        ):
            # Setup context manager
            mock_cli_class.return_value.__aenter__ = AsyncMock(return_value=mock_cli)
            mock_cli_class.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act - run with minimal progress (no progress bars)
            await _load_data_async(
                symbol="AAPL",
                timeframe="1d",
                mode="tail",
                start_date=None,
                end_date=None,
                trading_hours_only=False,
                include_extended=False,
                show_progress=False,
                output_format="table",
                verbose=False,
                quiet=True,
            )

            # Assert - verify AsyncCLIClient was used
            mock_cli_class.assert_called_once()
            mock_cli.health_check.assert_called_once()
            # Should use post to start the load operation
            mock_cli.post.assert_called()

    @pytest.mark.asyncio
    async def test_load_data_uses_health_check_not_check_api_connection(self):
        """Test that _load_data_async uses cli.health_check() not check_api_connection()."""
        from ktrdr.cli.data_commands import _load_data_async

        mock_cli = AsyncMock()
        mock_cli.health_check = AsyncMock(return_value=False)

        with (
            patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class,
            patch("ktrdr.cli.data_commands.display_ib_connection_required_message"),
            patch("ktrdr.cli.data_commands.console"),
            patch("ktrdr.cli.data_commands.error_console"),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_cli_class.return_value.__aenter__ = AsyncMock(return_value=mock_cli)
            mock_cli_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await _load_data_async(
                symbol="AAPL",
                timeframe="1d",
                mode="tail",
                start_date=None,
                end_date=None,
                trading_hours_only=False,
                include_extended=False,
                show_progress=False,
                output_format="table",
                verbose=False,
                quiet=True,
            )

        # Assert health_check was called (not check_api_connection)
        mock_cli.health_check.assert_called_once()
        assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_load_data_posts_to_correct_endpoint(self):
        """Test that _load_data_async posts to /data/acquire/download."""
        from ktrdr.cli.data_commands import _load_data_async

        mock_cli = AsyncMock()
        mock_cli.health_check = AsyncMock(return_value=True)
        mock_cli.post = AsyncMock(
            return_value={
                "success": True,
                "operation_id": "op_123",
            }
        )
        mock_cli.get = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "status": "completed",
                    "progress": {"percentage": 100},
                },
            }
        )

        with (
            patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class,
            patch("ktrdr.cli.data_commands.console"),
            patch("ktrdr.cli.data_commands.error_console"),
        ):
            mock_cli_class.return_value.__aenter__ = AsyncMock(return_value=mock_cli)
            mock_cli_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await _load_data_async(
                symbol="AAPL",
                timeframe="1h",
                mode="tail",
                start_date="2024-01-01",
                end_date="2024-03-31",
                trading_hours_only=True,
                include_extended=False,
                show_progress=False,
                output_format="table",
                verbose=False,
                quiet=True,
            )

            # Assert - verify correct endpoint and payload
            mock_cli.post.assert_called_once()
            call_args = mock_cli.post.call_args
            endpoint = call_args[0][0]
            assert endpoint == "/data/acquire/download"

            # Check payload
            json_payload = call_args[1]["json"]
            assert json_payload["symbol"] == "AAPL"
            assert json_payload["timeframe"] == "1h"
            assert json_payload["mode"] == "tail"
            assert json_payload["start_date"] == "2024-01-01"
            assert json_payload["end_date"] == "2024-03-31"
            assert json_payload["filters"]["trading_hours_only"] is True


class TestGetDataRangeMigration:
    """Tests for _get_data_range_async migration to AsyncCLIClient."""

    @pytest.mark.asyncio
    async def test_get_data_range_uses_async_cli_client(self):
        """Test that _get_data_range_async uses AsyncCLIClient not api_client."""
        from ktrdr.cli.data_commands import _get_data_range_async

        mock_cli = AsyncMock()
        mock_cli.health_check = AsyncMock(return_value=True)
        mock_cli.post = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "symbol": "AAPL",
                    "timeframe": "1d",
                    "start_date": "2024-01-01",
                    "end_date": "2024-03-31",
                    "point_count": 100,
                },
            }
        )

        with (
            patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class,
            patch("ktrdr.cli.data_commands.console"),
            patch("ktrdr.cli.data_commands.error_console"),
        ):
            mock_cli_class.return_value.__aenter__ = AsyncMock(return_value=mock_cli)
            mock_cli_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await _get_data_range_async(
                symbol="AAPL",
                timeframe="1d",
                output_format="table",
                verbose=False,
            )

            # Assert - verify AsyncCLIClient was used
            mock_cli_class.assert_called_once()
            mock_cli.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_data_range_posts_to_correct_endpoint(self):
        """Test that _get_data_range_async posts to /data/range."""
        from ktrdr.cli.data_commands import _get_data_range_async

        mock_cli = AsyncMock()
        mock_cli.health_check = AsyncMock(return_value=True)
        mock_cli.post = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "symbol": "AAPL",
                    "timeframe": "1d",
                    "start_date": "2024-01-01",
                    "end_date": "2024-03-31",
                    "point_count": 100,
                },
            }
        )

        with (
            patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class,
            patch("ktrdr.cli.data_commands.console"),
            patch("ktrdr.cli.data_commands.error_console"),
        ):
            mock_cli_class.return_value.__aenter__ = AsyncMock(return_value=mock_cli)
            mock_cli_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await _get_data_range_async(
                symbol="MSFT",
                timeframe="1h",
                output_format="json",
                verbose=False,
            )

            # Assert - verify correct endpoint
            mock_cli.post.assert_called_once()
            call_args = mock_cli.post.call_args
            endpoint = call_args[0][0]
            assert endpoint == "/data/range"

            # Check payload
            json_payload = call_args[1]["json"]
            assert json_payload["symbol"] == "MSFT"
            assert json_payload["timeframe"] == "1h"


class TestNoOldClientImports:
    """Test that old client imports are not used."""

    def test_no_check_api_connection_import(self):
        """Verify check_api_connection is not imported from api_client."""
        import ast

        with open("ktrdr/cli/data_commands.py") as f:
            source = f.read()

        tree = ast.parse(source)

        # Find all imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "api_client" in node.module:
                    for alias in node.names:
                        imports.append(alias.name)

        # Assert no api_client imports remain
        assert (
            "check_api_connection" not in imports
        ), "check_api_connection should not be imported from api_client"
        assert (
            "get_api_client" not in imports
        ), "get_api_client should not be imported from api_client"

"""Tests for CLI data commands endpoint fix.

Tests that verify the CLI data show command calls the correct API endpoint
after fixing the critical bug where it was calling non-existent /data/cached.
"""

from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.cli.data_commands import _show_data_async


class TestDataCommandsEndpointFix:
    """Test suite for data commands endpoint fix."""

    @pytest.mark.asyncio
    async def test_show_data_calls_correct_endpoint(self):
        """Test that show_data calls /data/{symbol}/{timeframe} not /data/cached."""
        # Arrange
        mock_cli = AsyncMock()
        mock_cli.get = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "dates": [],
                    "ohlcv": [],
                    "metadata": {"symbol": "AAPL", "timeframe": "1d", "points": 0},
                },
            }
        )

        # Mock the CLI creation and console
        with (
            patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class,
            patch("ktrdr.cli.data_commands.console"),
        ):
            # Setup the context manager behavior
            mock_cli_class.return_value.__aenter__ = AsyncMock(return_value=mock_cli)
            mock_cli_class.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            await _show_data_async(
                "AAPL", "1d", 10, None, None, False, False, "table", False
            )

            # Assert - verify correct endpoint is called
            mock_cli.get.assert_called_once()
            call_args = mock_cli.get.call_args

            # Should call GET with /data/{symbol}/{timeframe} endpoint
            endpoint = call_args[0][0]
            assert endpoint == "/data/AAPL/1d"

            # Should NOT call the old /data/cached endpoint
            assert "/data/cached" not in str(call_args)

    @pytest.mark.asyncio
    async def test_show_data_endpoint_format_with_different_symbols(self):
        """Test endpoint format with different symbols and timeframes."""
        test_cases = [
            ("MSFT", "1h", "/data/MSFT/1h"),
            ("GOOGL", "5m", "/data/GOOGL/5m"),
            ("TSLA", "1d", "/data/TSLA/1d"),
        ]

        for symbol, timeframe, expected_endpoint in test_cases:
            # Arrange
            mock_cli = AsyncMock()
            mock_cli.get = AsyncMock(
                return_value={
                    "success": True,
                    "data": {
                        "dates": [],
                        "ohlcv": [],
                        "metadata": {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "points": 0,
                        },
                    },
                }
            )

            with (
                patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class,
                patch("ktrdr.cli.data_commands.console"),
            ):
                # Setup the context manager behavior
                mock_cli_class.return_value.__aenter__ = AsyncMock(
                    return_value=mock_cli
                )
                mock_cli_class.return_value.__aexit__ = AsyncMock(return_value=None)

                # Act
                await _show_data_async(
                    symbol, timeframe, 10, None, None, False, False, "table", False
                )

                # Assert
                call_args = mock_cli.get.call_args
                endpoint = call_args[0][0]
                assert endpoint == expected_endpoint

    @pytest.mark.asyncio
    async def test_show_data_passes_query_parameters(self):
        """Test that query parameters are still passed correctly."""
        # Arrange
        mock_cli = AsyncMock()
        mock_cli.get = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "dates": [],
                    "ohlcv": [],
                    "metadata": {"symbol": "AAPL", "timeframe": "1d", "points": 0},
                },
            }
        )

        with (
            patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class,
            patch("ktrdr.cli.data_commands.console"),
        ):
            # Setup the context manager behavior
            mock_cli_class.return_value.__aenter__ = AsyncMock(return_value=mock_cli)
            mock_cli_class.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act - with trading hours and extended hours options
            await _show_data_async(
                "AAPL", "1d", 20, "2024-01-01", "2024-01-31", True, True, "table", False
            )

            # Assert
            call_args = mock_cli.get.call_args
            params = call_args[1]["params"]  # Keyword arguments

            # Verify query parameters are passed
            assert params["symbol"] == "AAPL"
            assert params["timeframe"] == "1d"
            assert params["start_date"] == "2024-01-01"
            assert params["end_date"] == "2024-01-31"
            assert params["trading_hours_only"] == "true"
            assert params["include_extended"] == "true"

"""Tests for show CLI command.

Tests the `ktrdr show` command for displaying market data and strategy features.
"""

import json
from unittest.mock import AsyncMock, patch


class TestShowDataCommand:
    """Tests for `ktrdr show data <symbol>` command."""

    def test_show_command_exists(self, runner) -> None:
        """Show command is registered."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            result = runner.invoke(app, ["show", "--help"])

            assert result.exit_code == 0
            assert "data" in result.output.lower()
            assert "features" in result.output.lower()

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_data_fetches_from_api(self, runner) -> None:
        """Show data fetches from /data/{symbol}/{timeframe} endpoint."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "success": True,
                    "data": {
                        "dates": ["2024-01-15T10:00:00"],
                        "ohlcv": [[150.0, 151.0, 149.0, 150.5, 1000000]],
                    },
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["show", "data", "AAPL"])

                mock_client.get.assert_called_once()
                call_args = mock_client.get.call_args
                assert "/data/AAPL" in call_args[0][0]

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_data_with_timeframe(self, runner) -> None:
        """Show data accepts timeframe argument."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "success": True,
                    "data": {
                        "dates": ["2024-01-15"],
                        "ohlcv": [[150.0, 151.0, 149.0, 150.5, 1000000]],
                    },
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["show", "data", "AAPL", "1d"])

                mock_client.get.assert_called_once()
                call_args = mock_client.get.call_args
                assert "/data/AAPL/1d" in call_args[0][0]

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_data_displays_table(self, runner) -> None:
        """Show data displays OHLCV table."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "success": True,
                    "data": {
                        "dates": ["2024-01-15T10:00:00", "2024-01-15T11:00:00"],
                        "ohlcv": [
                            [150.0, 151.0, 149.0, 150.5, 1000000],
                            [150.5, 152.0, 150.0, 151.5, 1200000],
                        ],
                    },
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["show", "data", "AAPL", "1h"])

                assert result.exit_code == 0
                # Should show OHLCV values
                assert "150" in result.output or "151" in result.output

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_data_json_output(self, runner) -> None:
        """Show data with --json outputs JSON."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "success": True,
                    "data": {
                        "dates": ["2024-01-15T10:00:00"],
                        "ohlcv": [[150.0, 151.0, 149.0, 150.5, 1000000]],
                    },
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "show", "data", "AAPL"])

                assert result.exit_code == 0
                data = json.loads(result.output)
                assert "dates" in data
                assert "ohlcv" in data

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]


class TestShowFeaturesCommand:
    """Tests for `ktrdr show features <strategy>` command."""

    def test_show_features_command_exists(self, runner) -> None:
        """Show features subcommand is registered."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            result = runner.invoke(app, ["show", "--help"])

            assert result.exit_code == 0
            assert "features" in result.output.lower()

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_features_requires_strategy(self, runner) -> None:
        """Show features requires strategy argument."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            result = runner.invoke(app, ["show", "features"])

            # Should fail - missing required argument
            assert result.exit_code != 0

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_features_fetches_from_api(self, runner) -> None:
        """Show features fetches from /strategies/{name}/features endpoint."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "success": True,
                    "strategy_name": "momentum",
                    "features": [
                        {
                            "feature_id": "1h_rsi_momentum_oversold",
                            "timeframe": "1h",
                            "fuzzy_set": "rsi_momentum",
                            "membership": "oversold",
                            "indicator_id": "rsi_14",
                            "indicator_output": None,
                        }
                    ],
                    "count": 1,
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["show", "features", "momentum"])

                assert result.exit_code == 0
                mock_client.get.assert_called_once()
                call_args = mock_client.get.call_args
                assert "/strategies/momentum/features" in call_args[0][0]
                # Should show strategy name
                assert "momentum" in result.output

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_features_displays_table(self, runner) -> None:
        """Show features displays table with feature details."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "success": True,
                    "strategy_name": "test_strategy",
                    "features": [
                        {
                            "feature_id": "1h_rsi_momentum_oversold",
                            "timeframe": "1h",
                            "fuzzy_set": "rsi_momentum",
                            "membership": "oversold",
                            "indicator_id": "rsi_14",
                            "indicator_output": None,
                        },
                        {
                            "feature_id": "1h_rsi_momentum_overbought",
                            "timeframe": "1h",
                            "fuzzy_set": "rsi_momentum",
                            "membership": "overbought",
                            "indicator_id": "rsi_14",
                            "indicator_output": None,
                        },
                    ],
                    "count": 2,
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["show", "features", "test_strategy"])

                assert result.exit_code == 0
                # Should show strategy name and features
                assert "test_strategy" in result.output
                assert "2" in result.output  # count

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_features_json_output(self, runner) -> None:
        """Show features with --json outputs JSON."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "success": True,
                    "strategy_name": "test_strategy",
                    "features": [
                        {
                            "feature_id": "1h_rsi_momentum_oversold",
                            "timeframe": "1h",
                            "fuzzy_set": "rsi_momentum",
                            "membership": "oversold",
                            "indicator_id": "rsi_14",
                            "indicator_output": None,
                        }
                    ],
                    "count": 1,
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(
                    app, ["--json", "show", "features", "test_strategy"]
                )

                assert result.exit_code == 0
                data = json.loads(result.output)
                assert "strategy_name" in data
                assert "features" in data
                assert data["count"] == 1

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]


class TestShowCommandErrors:
    """Tests for error handling in show commands."""

    def test_show_data_exits_on_error(self, runner) -> None:
        """Show data exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["show", "data", "AAPL"])

                assert result.exit_code == 1

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_features_handles_api_error(self, runner) -> None:
        """Show features handles API errors."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("Strategy not found")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["show", "features", "nonexistent"])

                assert result.exit_code == 1

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

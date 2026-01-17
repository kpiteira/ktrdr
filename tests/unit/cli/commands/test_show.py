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
            with patch("ktrdr.cli.commands.show.AsyncCLIClient") as mock_client_class:
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
            with patch("ktrdr.cli.commands.show.AsyncCLIClient") as mock_client_class:
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
            with patch("ktrdr.cli.commands.show.AsyncCLIClient") as mock_client_class:
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
            with patch("ktrdr.cli.commands.show.AsyncCLIClient") as mock_client_class:
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

    def test_show_features_loads_strategy(self, runner, tmp_path) -> None:
        """Show features loads and resolves strategy features."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        # Create a minimal v3 strategy file (v3 format uses indicators as dict)
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text(
            """
name: test_strategy
version: "3.0"
description: Test strategy

indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold: [0, 25, 40]
    overbought: [60, 75, 100]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: ["1h"]

model:
  type: mlp
  architecture:
    hidden_layers: [32, 16]
    dropout: 0.2

decisions:
  output_format: classification

training:
  epochs: 10
  batch_size: 32
  learning_rate: 0.001

training_data:
  symbols:
    mode: single
    symbol: AAPL
  timeframes:
    mode: single
    timeframe: "1h"
  history_required: 100
"""
        )

        try:
            result = runner.invoke(app, ["show", "features", str(strategy_file)])

            assert result.exit_code == 0
            # Should show strategy name and features
            assert "test_strategy" in result.output

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_features_json_output(self, runner, tmp_path) -> None:
        """Show features with --json outputs JSON."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        # Create a minimal v3 strategy file (v3 format uses indicators as dict)
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text(
            """
name: test_strategy
version: "3.0"
description: Test strategy

indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold: [0, 25, 40]
    overbought: [60, 75, 100]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: ["1h"]

model:
  type: mlp
  architecture:
    hidden_layers: [32, 16]
    dropout: 0.2

decisions:
  output_format: classification

training:
  epochs: 10
  batch_size: 32
  learning_rate: 0.001

training_data:
  symbols:
    mode: single
    symbol: AAPL
  timeframes:
    mode: single
    timeframe: "1h"
  history_required: 100
"""
        )

        try:
            result = runner.invoke(
                app, ["--json", "show", "features", str(strategy_file)]
            )

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "strategy" in data
            assert "features" in data

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
            with patch("ktrdr.cli.commands.show.AsyncCLIClient") as mock_client_class:
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

    def test_show_features_handles_missing_file(self, runner) -> None:
        """Show features handles missing strategy file."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        try:
            result = runner.invoke(
                app, ["show", "features", "/nonexistent/strategy.yaml"]
            )

            assert result.exit_code == 1

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

    def test_show_features_handles_invalid_strategy(self, runner, tmp_path) -> None:
        """Show features handles invalid strategy format."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.show import show_app

        app.add_typer(show_app)

        # Create an invalid strategy file
        strategy_file = tmp_path / "invalid_strategy.yaml"
        strategy_file.write_text("not: valid: yaml: strategy")

        try:
            result = runner.invoke(app, ["show", "features", str(strategy_file)])

            assert result.exit_code == 1

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != show_app
            ]

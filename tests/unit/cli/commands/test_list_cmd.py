"""Tests for list CLI command.

Tests the `ktrdr list` command that lists strategies, models, and checkpoints.
"""

import json
from unittest.mock import AsyncMock, patch


class TestListStrategiesCommand:
    """Tests for `ktrdr list strategies` command."""

    def test_list_strategies_command_exists(self, runner) -> None:
        """List strategies subcommand is registered."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            result = runner.invoke(app, ["list", "--help"])

            assert result.exit_code == 0
            assert "strategies" in result.output.lower()

        finally:
            # Clean up registered typer
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_strategies_fetches_from_api(self, runner) -> None:
        """List strategies fetches from /strategies endpoint."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"strategies": []}
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["list", "strategies"])

                # Verify API was called
                mock_client.get.assert_called_once()
                call_args = mock_client.get.call_args
                assert "/strategies" in call_args[0][0]

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_strategies_displays_table(self, runner) -> None:
        """List strategies displays table with name, version, symbols, timeframes."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "strategies": [
                        {
                            "name": "momentum",
                            "training_status": "trained",
                            "symbol": "AAPL",
                            "timeframe": "1h",
                        },
                        {
                            "name": "trend_follower",
                            "training_status": "untrained",
                            "symbol": "MSFT",
                            "timeframe": "4h",
                        },
                    ]
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["list", "strategies"])

                assert result.exit_code == 0
                # Should show strategy names
                assert "momentum" in result.output
                assert "trend_follower" in result.output

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_strategies_json_output(self, runner) -> None:
        """List strategies with --json outputs JSON."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "strategies": [
                        {
                            "name": "momentum",
                            "training_status": "trained",
                            "symbol": "AAPL",
                            "timeframe": "1h",
                        }
                    ]
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "list", "strategies"])

                assert result.exit_code == 0
                data = json.loads(result.output)
                assert isinstance(data, list)
                assert len(data) == 1
                assert data[0]["name"] == "momentum"

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_strategies_handles_v3_format(self, runner) -> None:
        """List strategies handles v3 format with training_data."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                # V3 format uses training_data with symbols/timeframes arrays
                mock_client.get.return_value = {
                    "strategies": [
                        {
                            "name": "v3_strategy",
                            "training_status": "trained",
                            "training_data": {
                                "symbols": ["AAPL", "MSFT"],
                                "timeframes": ["1h", "4h"],
                            },
                        }
                    ]
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["list", "strategies"])

                assert result.exit_code == 0
                # Should show symbols and timeframes
                assert "AAPL" in result.output or "v3_strategy" in result.output

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]


class TestListModelsCommand:
    """Tests for `ktrdr list models` command."""

    def test_list_models_command_exists(self, runner) -> None:
        """List models subcommand is registered."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            result = runner.invoke(app, ["list", "--help"])

            assert result.exit_code == 0
            assert "models" in result.output.lower()

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_models_fetches_from_api(self, runner) -> None:
        """List models fetches from /models endpoint."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"models": []}
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["list", "models"])

                mock_client.get.assert_called_once()
                call_args = mock_client.get.call_args
                assert "/models" in call_args[0][0]

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_models_displays_table(self, runner) -> None:
        """List models displays table with name, strategy, created, performance."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "models": [
                        {
                            "model_name": "momentum_v1",
                            "symbol": "AAPL",
                            "timeframe": "1h",
                            "created_at": "2024-01-15T10:30:00",
                            "training_accuracy": 0.85,
                        }
                    ]
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["list", "models"])

                assert result.exit_code == 0
                assert "momentum_v1" in result.output

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_models_json_output(self, runner) -> None:
        """List models with --json outputs JSON."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "models": [
                        {
                            "model_name": "momentum_v1",
                            "symbol": "AAPL",
                            "timeframe": "1h",
                            "created_at": "2024-01-15T10:30:00",
                        }
                    ]
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "list", "models"])

                assert result.exit_code == 0
                data = json.loads(result.output)
                assert isinstance(data, list)
                assert len(data) == 1
                assert data[0]["model_name"] == "momentum_v1"

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]


class TestListCheckpointsCommand:
    """Tests for `ktrdr list checkpoints` command."""

    def test_list_checkpoints_command_exists(self, runner) -> None:
        """List checkpoints subcommand is registered."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            result = runner.invoke(app, ["list", "--help"])

            assert result.exit_code == 0
            assert "checkpoints" in result.output.lower()

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_checkpoints_fetches_from_api(self, runner) -> None:
        """List checkpoints fetches from /checkpoints endpoint."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"data": [], "total_count": 0}
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["list", "checkpoints"])

                mock_client.get.assert_called_once()
                call_args = mock_client.get.call_args
                assert "/checkpoints" in call_args[0][0]

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_checkpoints_displays_table(self, runner) -> None:
        """List checkpoints displays table with ID, operation, created, size."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": [
                        {
                            "operation_id": "op_train_abc123",
                            "checkpoint_type": "periodic",
                            "created_at": "2024-01-15T10:30:00",
                            "state_summary": {"epoch": 29},
                            "artifacts_size_bytes": 1048576,
                        }
                    ],
                    "total_count": 1,
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["list", "checkpoints"])

                assert result.exit_code == 0
                # Should show operation ID (truncated)
                assert "op_train_abc" in result.output

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_checkpoints_json_output(self, runner) -> None:
        """List checkpoints with --json outputs JSON."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": [
                        {
                            "operation_id": "op_train_abc123",
                            "checkpoint_type": "periodic",
                            "created_at": "2024-01-15T10:30:00",
                        }
                    ],
                    "total_count": 1,
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "list", "checkpoints"])

                assert result.exit_code == 0
                data = json.loads(result.output)
                assert isinstance(data, list)
                assert len(data) == 1
                assert data[0]["operation_id"] == "op_train_abc123"

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]


class TestListCommandErrors:
    """Tests for error handling in list commands."""

    def test_list_strategies_exits_on_error(self, runner) -> None:
        """List strategies exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["list", "strategies"])

                assert result.exit_code == 1

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_models_exits_on_error(self, runner) -> None:
        """List models exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["list", "models"])

                assert result.exit_code == 1

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

    def test_list_checkpoints_exits_on_error(self, runner) -> None:
        """List checkpoints exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app

        app.add_typer(list_app)

        try:
            with patch(
                "ktrdr.cli.commands.list_cmd.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["list", "checkpoints"])

                assert result.exit_code == 1

        finally:
            app.registered_groups = [
                g for g in app.registered_groups if g.typer_instance != list_app
            ]

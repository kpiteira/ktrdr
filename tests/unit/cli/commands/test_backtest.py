"""Tests for backtest CLI command.

Tests the `ktrdr backtest <strategy>` command that starts backtest operations
using the OperationRunner wrapper.
"""

import inspect
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ktrdr.cli.state import CLIState


class TestBacktestCommandArguments:
    """Tests for backtest command required arguments."""

    def test_backtest_command_requires_strategy(self, runner) -> None:
        """Backtest command requires a strategy argument."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            # Invoke without strategy argument
            result = runner.invoke(
                app, ["backtest", "--start", "2024-01-01", "--end", "2024-06-01"]
            )
            # Should fail due to missing strategy
            assert result.exit_code != 0
            assert (
                "Missing argument" in result.output
                or "strategy" in result.output.lower()
            )
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]

    def test_backtest_command_requires_start_date(self, runner) -> None:
        """Backtest command requires --start option."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            result = runner.invoke(app, ["backtest", "momentum", "--end", "2024-06-01"])
            # Should fail due to missing --start
            assert result.exit_code != 0
            assert "start" in result.output.lower() or "Missing option" in result.output
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]

    def test_backtest_command_requires_end_date(self, runner) -> None:
        """Backtest command requires --end option."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            result = runner.invoke(
                app, ["backtest", "momentum", "--start", "2024-01-01"]
            )
            # Should fail due to missing --end
            assert result.exit_code != 0
            assert "end" in result.output.lower() or "Missing option" in result.output
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]


class TestBacktestCommandOptions:
    """Tests for backtest command optional arguments and defaults."""

    def test_backtest_command_capital_default(self) -> None:
        """Backtest command has capital default of 100000."""
        from ktrdr.cli.commands.backtest import backtest

        sig = inspect.signature(backtest)
        params = sig.parameters

        # Find capital parameter and check default
        assert "capital" in params
        param = params["capital"]
        # The default is a typer.Option, check its default attribute
        assert param.default.default == 100000.0

    def test_backtest_command_follow_default_false(self) -> None:
        """Backtest command has follow default of False."""
        from ktrdr.cli.commands.backtest import backtest

        sig = inspect.signature(backtest)
        params = sig.parameters

        assert "follow" in params
        param = params["follow"]
        assert param.default.default is False

    def test_backtest_command_capital_shorthand(self, runner) -> None:
        """Backtest command accepts -c as shorthand for --capital."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            with patch(
                "ktrdr.cli.commands.backtest.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                with patch(
                    "ktrdr.cli.commands.backtest.BacktestingOperationAdapter"
                ) as mock_adapter:
                    runner.invoke(
                        app,
                        [
                            "backtest",
                            "momentum",
                            "--start",
                            "2024-01-01",
                            "--end",
                            "2024-06-01",
                            "-c",
                            "50000",
                        ],
                    )

                    call_kwargs = mock_adapter.call_args[1]
                    assert call_kwargs["initial_capital"] == 50000.0
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]


class TestBacktestCommandRunner:
    """Tests for backtest command interaction with OperationRunner."""

    def test_backtest_command_calls_runner_start(self) -> None:
        """Backtest command creates OperationRunner and calls start()."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.commands.backtest.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                runner.invoke(
                    app,
                    [
                        "backtest",
                        "momentum",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-06-01",
                    ],
                )

                mock_runner_class.assert_called_once()
                mock_runner.start.assert_called_once()
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]

    def test_backtest_command_passes_follow_flag_to_runner(self) -> None:
        """Backtest command passes --follow flag to OperationRunner.start()."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.commands.backtest.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                runner.invoke(
                    app,
                    [
                        "backtest",
                        "momentum",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-06-01",
                        "--follow",
                    ],
                )

                call_args = mock_runner.start.call_args
                assert call_args[1]["follow"] is True
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]

    def test_backtest_command_passes_f_shorthand_to_runner(self) -> None:
        """Backtest command accepts -f as shorthand for --follow."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.commands.backtest.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                runner.invoke(
                    app,
                    [
                        "backtest",
                        "momentum",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-06-01",
                        "-f",
                    ],
                )

                call_args = mock_runner.start.call_args
                assert call_args[1]["follow"] is True
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]

    def test_backtest_command_creates_adapter_with_strategy(self) -> None:
        """Backtest command creates BacktestingOperationAdapter with correct params."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.commands.backtest.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                with patch(
                    "ktrdr.cli.commands.backtest.BacktestingOperationAdapter"
                ) as mock_adapter_class:
                    runner.invoke(
                        app,
                        [
                            "backtest",
                            "momentum",
                            "--start",
                            "2024-01-01",
                            "--end",
                            "2024-06-01",
                            "--capital",
                            "50000",
                        ],
                    )

                    mock_adapter_class.assert_called_once()
                    call_kwargs = mock_adapter_class.call_args[1]
                    assert call_kwargs["strategy_name"] == "momentum"
                    assert call_kwargs["start_date"] == "2024-01-01"
                    assert call_kwargs["end_date"] == "2024-06-01"
                    assert call_kwargs["initial_capital"] == 50000.0
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]


class TestBacktestCommandState:
    """Tests for CLIState handling in backtest command."""

    def test_backtest_command_receives_state_from_context(self) -> None:
        """Backtest command receives CLIState from Typer context."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.commands.backtest.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                runner.invoke(
                    app,
                    [
                        "backtest",
                        "momentum",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-06-01",
                    ],
                )

                # OperationRunner should be initialized with CLIState
                call_args = mock_runner_class.call_args[0]
                state = call_args[0]
                assert isinstance(state, CLIState)
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]

    def test_backtest_command_uses_json_mode_from_global_flag(self) -> None:
        """Backtest command respects --json global flag from CLIState."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.commands.backtest.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                # Use global --json flag
                runner.invoke(
                    app,
                    [
                        "--json",
                        "backtest",
                        "momentum",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-06-01",
                    ],
                )

                call_args = mock_runner_class.call_args[0]
                state = call_args[0]
                assert state.json_mode is True
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]


class TestBacktestCommandErrors:
    """Tests for error handling in backtest command."""

    def test_backtest_command_exits_on_runner_error(self) -> None:
        """Backtest command exits with code 1 when OperationRunner raises."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.commands.backtest.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner.start.side_effect = Exception("Connection failed")
                mock_runner_class.return_value = mock_runner

                result = runner.invoke(
                    app,
                    [
                        "backtest",
                        "momentum",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-06-01",
                    ],
                )

                assert result.exit_code == 1
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]

    def test_backtest_command_prints_error_message(self, runner) -> None:
        """Backtest command prints error message when runner fails."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.backtest import backtest

        app.command()(backtest)

        try:
            with patch(
                "ktrdr.cli.commands.backtest.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner.start.side_effect = Exception("API unreachable")
                mock_runner_class.return_value = mock_runner

                result = runner.invoke(
                    app,
                    [
                        "backtest",
                        "momentum",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-06-01",
                    ],
                )

                # Error message should appear in output
                assert "API unreachable" in result.output or "Error" in result.output
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "backtest"
            ]

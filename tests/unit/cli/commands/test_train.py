"""Tests for train CLI command.

Tests the `ktrdr train <strategy>` command that starts training operations
using the OperationRunner wrapper.
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ktrdr.cli.state import CLIState


class TestTrainCommandArguments:
    """Tests for train command required arguments."""

    def test_train_command_requires_strategy(self) -> None:
        """Train command requires a strategy argument."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        # Register command for test
        app.command()(train)

        try:
            runner = CliRunner()
            # Invoke without strategy argument
            result = runner.invoke(
                app, ["train", "--start", "2024-01-01", "--end", "2024-06-01"]
            )
            # Should fail due to missing strategy
            assert result.exit_code != 0
            assert (
                "Missing argument" in result.output
                or "strategy" in result.output.lower()
            )
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

    def test_train_command_requires_start_date(self) -> None:
        """Train command requires --start option."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()
            result = runner.invoke(app, ["train", "momentum", "--end", "2024-06-01"])
            # Should fail due to missing --start
            assert result.exit_code != 0
            assert "start" in result.output.lower() or "Missing option" in result.output
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

    def test_train_command_requires_end_date(self) -> None:
        """Train command requires --end option."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()
            result = runner.invoke(app, ["train", "momentum", "--start", "2024-01-01"])
            # Should fail due to missing --end
            assert result.exit_code != 0
            assert "end" in result.output.lower() or "Missing option" in result.output
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]


class TestTrainCommandOptions:
    """Tests for train command optional arguments and defaults."""

    def test_train_command_validation_split_default(self) -> None:
        """Train command has validation_split default of 0.2."""
        from ktrdr.cli.commands.train import train

        sig = inspect.signature(train)
        params = sig.parameters

        # Find validation_split parameter and check default
        assert "validation_split" in params
        # Typer wraps defaults, so check the default value from the Option
        param = params["validation_split"]
        # The default is a typer.Option, we need to check its default attribute
        assert param.default.default == 0.2

    def test_train_command_follow_default_false(self) -> None:
        """Train command has follow default of False."""
        from ktrdr.cli.commands.train import train

        sig = inspect.signature(train)
        params = sig.parameters

        assert "follow" in params
        param = params["follow"]
        assert param.default.default is False


class TestTrainCommandRunner:
    """Tests for train command interaction with OperationRunner."""

    def test_train_command_calls_runner_start(self) -> None:
        """Train command creates OperationRunner and calls start()."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch("ktrdr.cli.commands.train.OperationRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                runner.invoke(
                    app,
                    [
                        "train",
                        "momentum",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-06-01",
                    ],
                )

                # Should succeed (exit code 0) or fail at runner level
                mock_runner_class.assert_called_once()
                mock_runner.start.assert_called_once()
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

    def test_train_command_passes_follow_flag_to_runner(self) -> None:
        """Train command passes --follow flag to OperationRunner.start()."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch("ktrdr.cli.commands.train.OperationRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                # Test with --follow
                runner.invoke(
                    app,
                    [
                        "train",
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
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

    def test_train_command_passes_f_shorthand_to_runner(self) -> None:
        """Train command accepts -f as shorthand for --follow."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch("ktrdr.cli.commands.train.OperationRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                # Test with -f
                runner.invoke(
                    app,
                    [
                        "train",
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
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

    def test_train_command_creates_training_adapter(self) -> None:
        """Train command creates TrainingOperationAdapter with correct params."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch("ktrdr.cli.commands.train.OperationRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                with patch(
                    "ktrdr.cli.commands.train.TrainingOperationAdapter"
                ) as mock_adapter_class:
                    runner.invoke(
                        app,
                        [
                            "train",
                            "momentum",
                            "--start",
                            "2024-01-01",
                            "--end",
                            "2024-06-01",
                            "--validation-split",
                            "0.3",
                        ],
                    )

                    mock_adapter_class.assert_called_once()
                    call_kwargs = mock_adapter_class.call_args[1]
                    assert call_kwargs["strategy_name"] == "momentum"
                    assert call_kwargs["start_date"] == "2024-01-01"
                    assert call_kwargs["end_date"] == "2024-06-01"
                    assert call_kwargs["validation_split"] == 0.3
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]


class TestTrainCommandState:
    """Tests for CLIState handling in train command."""

    def test_train_command_receives_state_from_context(self) -> None:
        """Train command receives CLIState from Typer context."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch("ktrdr.cli.commands.train.OperationRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                runner.invoke(
                    app,
                    [
                        "train",
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
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

    def test_train_command_uses_json_mode_from_global_flag(self) -> None:
        """Train command respects --json global flag from CLIState."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch("ktrdr.cli.commands.train.OperationRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                # Use global --json flag
                runner.invoke(
                    app,
                    [
                        "--json",
                        "train",
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
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]


class TestTrainCommandErrors:
    """Tests for error handling in train command."""

    def test_train_command_exits_on_runner_error(self) -> None:
        """Train command exits with code 1 when OperationRunner raises."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch("ktrdr.cli.commands.train.OperationRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner.start.side_effect = Exception("Connection failed")
                mock_runner_class.return_value = mock_runner

                result = runner.invoke(
                    app,
                    [
                        "train",
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
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

    def test_train_command_prints_error_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Train command prints error message when runner fails."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch("ktrdr.cli.commands.train.OperationRunner") as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner.start.side_effect = Exception("API unreachable")
                mock_runner_class.return_value = mock_runner

                result = runner.invoke(
                    app,
                    [
                        "train",
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
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

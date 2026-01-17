"""Tests for follow CLI command.

Tests the `ktrdr follow <op-id>` command that attaches to a running
operation and shows progress until completion.
"""

import inspect
from unittest.mock import AsyncMock, patch


class TestFollowCommandArguments:
    """Tests for follow command arguments."""

    def test_follow_command_requires_operation_id(self) -> None:
        """Follow command requires operation_id argument."""
        from ktrdr.cli.commands.follow import follow

        sig = inspect.signature(follow)
        params = sig.parameters

        assert "operation_id" in params
        param = params["operation_id"]
        # Required argument (Ellipsis default means required in typer)
        assert param.default.default is ...


class TestFollowProgress:
    """Tests for follow command progress display."""

    def test_follow_shows_progress(self, runner) -> None:
        """Follow command shows progress for running operation."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.follow import follow

        app.command()(follow)

        try:
            with patch("ktrdr.cli.commands.follow.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                # Return running state then completed
                mock_client.get.side_effect = [
                    {
                        "data": {
                            "operation_id": "op_test123",
                            "status": "running",
                            "progress": {"percentage": 50},
                        }
                    },
                    {
                        "data": {
                            "operation_id": "op_test123",
                            "status": "completed",
                            "progress": {"percentage": 100},
                        }
                    },
                ]
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["follow", "op_test123"])

                assert result.exit_code == 0
                # Should have polled the operation
                assert mock_client.get.call_count >= 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "follow"
            ]

    def test_follow_polls_until_completed(self, runner) -> None:
        """Follow polls operation until it reaches completed state."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.follow import follow

        app.command()(follow)

        try:
            with patch("ktrdr.cli.commands.follow.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                # Return running multiple times, then completed
                mock_client.get.side_effect = [
                    {
                        "data": {
                            "status": "running",
                            "progress": {"percentage": 25},
                        }
                    },
                    {
                        "data": {
                            "status": "running",
                            "progress": {"percentage": 50},
                        }
                    },
                    {
                        "data": {
                            "status": "running",
                            "progress": {"percentage": 75},
                        }
                    },
                    {
                        "data": {
                            "status": "completed",
                            "progress": {"percentage": 100},
                        }
                    },
                ]
                mock_client_class.return_value = mock_client

                # Patch asyncio.sleep to avoid real delays
                with patch(
                    "ktrdr.cli.commands.follow.asyncio.sleep", new_callable=AsyncMock
                ):
                    result = runner.invoke(app, ["follow", "op_abc"])

                assert result.exit_code == 0
                # Should have polled 4 times
                assert mock_client.get.call_count == 4

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "follow"
            ]

    def test_follow_fetches_correct_operation(self, runner) -> None:
        """Follow fetches the specified operation by ID."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.follow import follow

        app.command()(follow)

        try:
            with patch("ktrdr.cli.commands.follow.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": {
                        "operation_id": "op_specific",
                        "status": "completed",
                        "progress": {"percentage": 100},
                    }
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["follow", "op_specific"])

                # Should have fetched the specific operation
                mock_client.get.assert_called_with("/operations/op_specific")

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "follow"
            ]


class TestFollowTerminalStates:
    """Tests for follow command handling terminal states."""

    def test_follow_handles_completed_operation(self, runner) -> None:
        """Follow shows success message for completed operation."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.follow import follow

        app.command()(follow)

        try:
            with patch("ktrdr.cli.commands.follow.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": {
                        "operation_id": "op_done",
                        "status": "completed",
                        "progress": {"percentage": 100},
                    }
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["follow", "op_done"])

                assert result.exit_code == 0
                assert "completed" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "follow"
            ]

    def test_follow_handles_failed_operation(self, runner) -> None:
        """Follow shows error message for failed operation."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.follow import follow

        app.command()(follow)

        try:
            with patch("ktrdr.cli.commands.follow.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": {
                        "operation_id": "op_failed",
                        "status": "failed",
                        "error_message": "Training diverged",
                        "progress": {"percentage": 45},
                    }
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["follow", "op_failed"])

                assert result.exit_code == 0
                assert "failed" in result.output.lower()
                assert "diverged" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "follow"
            ]

    def test_follow_handles_cancelled_operation(self, runner) -> None:
        """Follow shows cancellation message for cancelled operation."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.follow import follow

        app.command()(follow)

        try:
            with patch("ktrdr.cli.commands.follow.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": {
                        "operation_id": "op_cancelled",
                        "status": "cancelled",
                        "progress": {"percentage": 30},
                    }
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["follow", "op_cancelled"])

                assert result.exit_code == 0
                assert "cancelled" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "follow"
            ]


class TestFollowErrors:
    """Tests for error handling in follow command."""

    def test_follow_exits_on_exception(self, runner) -> None:
        """Follow command exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.follow import follow

        app.command()(follow)

        try:
            with patch("ktrdr.cli.commands.follow.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["follow", "op_error"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "follow"
            ]

    def test_follow_operation_not_found(self, runner) -> None:
        """Follow command handles operation not found gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.follow import follow

        app.command()(follow)

        try:
            with patch("ktrdr.cli.commands.follow.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("404 Not Found")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["follow", "op_nonexistent"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "follow"
            ]

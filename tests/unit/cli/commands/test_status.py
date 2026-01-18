"""Tests for status CLI command.

Tests the `ktrdr status [op-id]` command that shows system dashboard
or specific operation status.
"""

import inspect
from unittest.mock import AsyncMock, patch


class TestStatusCommandArguments:
    """Tests for status command arguments."""

    def test_status_command_operation_id_optional(self) -> None:
        """Status command has optional operation_id argument."""
        from ktrdr.cli.commands.status import status

        sig = inspect.signature(status)
        params = sig.parameters

        assert "operation_id" in params
        param = params["operation_id"]
        # Default is None for optional argument
        assert param.default.default is None


class TestStatusDashboard:
    """Tests for status command dashboard mode (no argument)."""

    def test_status_no_arg_shows_dashboard(self, runner) -> None:
        """Status command without argument shows system dashboard."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.status import status

        app.command()(status)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                # Dashboard fetches operations and workers
                mock_client.get.side_effect = [
                    {
                        "data": [
                            {"status": "running"},
                            {"status": "completed"},
                            {"status": "completed"},
                        ]
                    },
                    [{"id": "w1"}, {"id": "w2"}],
                ]
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["status"])

                assert result.exit_code == 0
                # Should show operations summary
                assert "running" in result.output.lower()
                assert "completed" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "status"
            ]

    def test_status_dashboard_fetches_operations_and_workers(self, runner) -> None:
        """Status dashboard fetches both operations and workers."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.status import status

        app.command()(status)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = [
                    {"data": []},
                    [],  # workers endpoint returns list directly
                ]
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["status"])

                # Should have made two API calls
                assert mock_client.get.call_count == 2
                calls = mock_client.get.call_args_list
                assert calls[0][0] == ("/operations",)
                assert calls[1][0] == ("/workers",)

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "status"
            ]

    def test_status_dashboard_json_output(self, runner) -> None:
        """Status dashboard with --json outputs JSON format."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.status import status

        app.command()(status)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = [
                    {"data": [{"status": "running"}]},
                    [{"id": "w1"}],  # workers endpoint returns list directly
                ]
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "status"])

                assert result.exit_code == 0
                # Output should be valid JSON with operations and workers
                import json

                data = json.loads(result.output)
                assert "operations" in data
                assert "workers" in data

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "status"
            ]


class TestStatusOperation:
    """Tests for status command operation mode (with argument)."""

    def test_status_with_arg_shows_operation(self, runner) -> None:
        """Status command with operation ID shows operation details."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.status import status

        app.command()(status)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": {
                        "operation_id": "op_test123",
                        "operation_type": "training",
                        "status": "running",
                        "progress": {"percentage": 50},
                    }
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["status", "op_test123"])

                assert result.exit_code == 0
                assert "op_test123" in result.output
                assert "training" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "status"
            ]

    def test_status_operation_fetches_specific_operation(self, runner) -> None:
        """Status with op-id fetches that specific operation."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.status import status

        app.command()(status)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": {
                        "operation_id": "op_abc",
                        "operation_type": "backtest",
                        "status": "completed",
                    }
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["status", "op_abc"])

                # Should have fetched the specific operation
                mock_client.get.assert_called_once_with("/operations/op_abc")

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "status"
            ]

    def test_status_operation_json_output(self, runner) -> None:
        """Status operation with --json outputs JSON format."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.status import status

        app.command()(status)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": {
                        "operation_id": "op_json_test",
                        "operation_type": "training",
                        "status": "running",
                        "progress": {"percentage": 75},
                    }
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "status", "op_json_test"])

                assert result.exit_code == 0
                import json

                data = json.loads(result.output)
                assert data["operation_id"] == "op_json_test"
                assert data["status"] == "running"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "status"
            ]

    def test_status_operation_shows_progress(self, runner) -> None:
        """Status operation shows progress percentage when available."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.status import status

        app.command()(status)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {
                    "data": {
                        "operation_id": "op_progress",
                        "operation_type": "training",
                        "status": "running",
                        "progress": {"percentage": 42},
                    }
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["status", "op_progress"])

                assert result.exit_code == 0
                assert "42" in result.output

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "status"
            ]


class TestStatusErrors:
    """Tests for error handling in status command."""

    def test_status_exits_on_exception(self, runner) -> None:
        """Status command exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.status import status

        app.command()(status)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["status"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "status"
            ]

    def test_status_operation_not_found(self, runner) -> None:
        """Status command handles operation not found gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.status import status

        app.command()(status)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("404 Not Found")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["status", "op_nonexistent"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "status"
            ]

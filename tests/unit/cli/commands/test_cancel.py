"""Tests for cancel CLI command.

Tests the `ktrdr cancel` command that cancels running operations.
Replaces the old `ktrdr operations cancel` command with a simpler path.
"""

import json
from unittest.mock import AsyncMock, patch

from ktrdr.cli.client import APIError


class TestCancelCommandArguments:
    """Tests for cancel command arguments."""

    def test_cancel_requires_operation_id(self, runner) -> None:
        """Cancel command requires operation_id argument."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            result = runner.invoke(app, ["cancel"])

            # Should fail with missing argument error
            assert result.exit_code != 0
            # Typer shows "Missing argument" for required positional args
            assert (
                "missing" in result.output.lower()
                or "required" in result.output.lower()
            )

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]

    def test_cancel_accepts_operation_id(self, runner) -> None:
        """Cancel command accepts operation_id argument."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.return_value = {
                    "success": True,
                    "data": {"operation_id": "op_test123", "status": "cancelled"},
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["cancel", "op_test123"])

                assert result.exit_code == 0

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]


class TestCancelOperation:
    """Tests for cancel command operation."""

    def test_cancel_calls_delete_endpoint(self, runner) -> None:
        """Cancel command calls DELETE on /operations/{id}."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.return_value = {
                    "success": True,
                    "data": {"operation_id": "op_abc123", "status": "cancelled"},
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["cancel", "op_abc123"])

                # Verify delete was called with correct endpoint
                mock_client.delete.assert_called_once()
                call_args = mock_client.delete.call_args
                assert call_args[0][0] == "/operations/op_abc123"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]

    def test_cancel_shows_success_message(self, runner) -> None:
        """Cancel command shows success message on successful cancellation."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.return_value = {
                    "success": True,
                    "data": {
                        "operation_id": "op_success123",
                        "status": "cancelled",
                        "cancelled_at": "2024-12-01T12:00:00Z",
                    },
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["cancel", "op_success123"])

                assert result.exit_code == 0
                # Should show cancelled message
                assert "cancelled" in result.output.lower()
                assert "op_success123" in result.output

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]


class TestCancelOptions:
    """Tests for cancel command options."""

    def test_cancel_reason_option(self, runner) -> None:
        """Cancel command passes reason to API."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.return_value = {
                    "success": True,
                    "data": {"operation_id": "op_123", "status": "cancelled"},
                }
                mock_client_class.return_value = mock_client

                runner.invoke(
                    app, ["cancel", "op_123", "--reason", "User requested stop"]
                )

                # Verify reason was passed in JSON body
                call_args = mock_client.delete.call_args
                assert (
                    call_args[1].get("json", {}).get("reason") == "User requested stop"
                )

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]

    def test_cancel_reason_shorthand(self, runner) -> None:
        """Cancel command accepts -r shorthand for --reason."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.return_value = {
                    "success": True,
                    "data": {"operation_id": "op_123", "status": "cancelled"},
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["cancel", "op_123", "-r", "Quick cancel"])

                call_args = mock_client.delete.call_args
                assert call_args[1].get("json", {}).get("reason") == "Quick cancel"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]

    def test_cancel_force_option(self, runner) -> None:
        """Cancel command passes force flag to API."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.return_value = {
                    "success": True,
                    "data": {"operation_id": "op_123", "status": "cancelled"},
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["cancel", "op_123", "--force"])

                call_args = mock_client.delete.call_args
                assert call_args[1].get("json", {}).get("force") is True

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]

    def test_cancel_force_shorthand(self, runner) -> None:
        """Cancel command accepts -f shorthand for --force."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.return_value = {
                    "success": True,
                    "data": {"operation_id": "op_123", "status": "cancelled"},
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["cancel", "op_123", "-f"])

                call_args = mock_client.delete.call_args
                assert call_args[1].get("json", {}).get("force") is True

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]


class TestCancelJsonOutput:
    """Tests for cancel command JSON output."""

    def test_cancel_json_output(self, runner) -> None:
        """Cancel command with --json outputs JSON."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.return_value = {
                    "success": True,
                    "data": {
                        "operation_id": "op_json123",
                        "status": "cancelled",
                        "cancelled_at": "2024-12-01T12:00:00Z",
                    },
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "cancel", "op_json123"])

                assert result.exit_code == 0
                # Output should be valid JSON
                data = json.loads(result.output)
                assert data["operation_id"] == "op_json123"
                assert data["status"] == "cancelled"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]


class TestCancelErrorHandling:
    """Tests for cancel command error handling."""

    def test_cancel_handles_not_found(self, runner) -> None:
        """Cancel command handles operation not found gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.side_effect = APIError(
                    message="Operation not found",
                    status_code=404,
                    details={"operation_id": "op_notfound"},
                )
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["cancel", "op_notfound"])

                # Should exit with error code
                assert result.exit_code == 1
                # Should show error message
                assert (
                    "not found" in result.output.lower()
                    or "error" in result.output.lower()
                )

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]

    def test_cancel_handles_already_completed(self, runner) -> None:
        """Cancel command handles already-completed operation gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.side_effect = APIError(
                    message="Operation cannot be cancelled",
                    status_code=400,
                    details={"operation_id": "op_done", "status": "completed"},
                )
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["cancel", "op_done"])

                # Should exit with error code
                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]

    def test_cancel_exits_on_exception(self, runner) -> None:
        """Cancel command exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.cancel import cancel

        app.command()(cancel)

        try:
            with patch("ktrdr.cli.commands.cancel.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.delete.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["cancel", "op_123"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "cancel"
            ]

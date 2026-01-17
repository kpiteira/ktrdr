"""Tests for ops CLI command.

Tests the `ktrdr ops` command that lists all operations in a table format.
Preserves behavior from operations_commands.py including checkpoint fetching.
"""

import json
from unittest.mock import AsyncMock, patch

from ktrdr.cli.client import CLIClientError


class TestOpsCommandArguments:
    """Tests for ops command arguments."""

    def test_ops_command_no_required_args(self, runner) -> None:
        """Ops command has no required arguments."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"data": []}
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["ops"])

                assert result.exit_code == 0

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]


class TestOpsListing:
    """Tests for ops command listing functionality."""

    def test_ops_fetches_operations(self, runner) -> None:
        """Ops command fetches operations from API."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"data": []}
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["ops"])

                # Should have fetched operations
                mock_client.get.assert_called()
                # First call should be to /operations
                first_call = mock_client.get.call_args_list[0]
                assert "/operations" in first_call[0][0]

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_displays_operations_table(self, runner) -> None:
        """Ops command displays operations in a table with all columns."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                # Mock responses: operations list, then checkpoint calls
                async def mock_get(endpoint, **kwargs):
                    if endpoint == "/operations":
                        return {
                            "data": [
                                {
                                    "operation_id": "op_test123",
                                    "operation_type": "training",
                                    "status": "running",
                                    "progress_percentage": 50,
                                    "symbol": "AAPL",
                                    "duration_seconds": 120,
                                },
                                {
                                    "operation_id": "op_test456",
                                    "operation_type": "backtest",
                                    "status": "completed",
                                    "progress_percentage": 100,
                                    "symbol": "MSFT",
                                    "duration_seconds": 3700,
                                },
                            ]
                        }
                    elif "/checkpoints/" in endpoint:
                        # Return no checkpoint for simplicity
                        return {"success": False}
                    return {}

                mock_client.get.side_effect = mock_get
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["ops"])

                assert result.exit_code == 0
                # Should show operation IDs
                assert "op_test123" in result.output
                assert "op_test456" in result.output
                # Should show types
                assert "training" in result.output.lower()
                assert "backtest" in result.output.lower()
                # Should show symbols
                assert "AAPL" in result.output
                assert "MSFT" in result.output

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_handles_empty_list(self, runner) -> None:
        """Ops command handles empty operations list gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"data": []}
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["ops"])

                assert result.exit_code == 0
                # Should show "no operations" message
                assert "no" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_fetches_checkpoints_for_each_operation(self, runner) -> None:
        """Ops command fetches checkpoint info for each operation."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                checkpoint_calls = []

                async def mock_get(endpoint, **kwargs):
                    if endpoint == "/operations":
                        return {
                            "data": [
                                {
                                    "operation_id": "op_1",
                                    "operation_type": "training",
                                    "status": "running",
                                },
                                {
                                    "operation_id": "op_2",
                                    "operation_type": "backtest",
                                    "status": "completed",
                                },
                            ]
                        }
                    elif "/checkpoints/" in endpoint:
                        checkpoint_calls.append(endpoint)
                        return {"success": False}
                    return {}

                mock_client.get.side_effect = mock_get
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["ops"])

                # Should have fetched checkpoints for each operation
                assert "/checkpoints/op_1" in checkpoint_calls
                assert "/checkpoints/op_2" in checkpoint_calls

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_displays_checkpoint_summary(self, runner) -> None:
        """Ops command displays checkpoint summary when available."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                async def mock_get(endpoint, **kwargs):
                    if endpoint == "/operations":
                        return {
                            "data": [
                                {
                                    "operation_id": "op_1",
                                    "operation_type": "training",
                                    "status": "running",
                                },
                            ]
                        }
                    elif "/checkpoints/op_1" in endpoint:
                        return {"success": True, "data": {"state": {"epoch": 29}}}
                    return {}

                mock_client.get.side_effect = mock_get
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["ops"])

                assert result.exit_code == 0
                # Should show checkpoint summary
                assert "epoch 29" in result.output

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]


class TestOpsJsonOutput:
    """Tests for ops command JSON output."""

    def test_ops_json_output(self, runner) -> None:
        """Ops command with --json outputs JSON array."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                async def mock_get(endpoint, **kwargs):
                    if endpoint == "/operations":
                        return {
                            "data": [
                                {
                                    "operation_id": "op_json1",
                                    "operation_type": "training",
                                    "status": "running",
                                }
                            ]
                        }
                    elif "/checkpoints/" in endpoint:
                        return {"success": False}
                    return {}

                mock_client.get.side_effect = mock_get
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "ops"])

                assert result.exit_code == 0
                # Output should be valid JSON array
                data = json.loads(result.output)
                assert isinstance(data, list)
                assert len(data) == 1
                assert data[0]["operation_id"] == "op_json1"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_json_empty_array(self, runner) -> None:
        """Ops command with --json outputs empty array when no operations."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"data": []}
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "ops"])

                assert result.exit_code == 0
                data = json.loads(result.output)
                assert data == []

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_json_includes_checkpoint_info(self, runner) -> None:
        """Ops command JSON output includes checkpoint info."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                async def mock_get(endpoint, **kwargs):
                    if endpoint == "/operations":
                        return {
                            "data": [
                                {
                                    "operation_id": "op_1",
                                    "operation_type": "training",
                                    "status": "running",
                                },
                            ]
                        }
                    elif "/checkpoints/op_1" in endpoint:
                        return {"success": True, "data": {"state": {"epoch": 15}}}
                    return {}

                mock_client.get.side_effect = mock_get
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "ops"])

                assert result.exit_code == 0
                data = json.loads(result.output)
                assert data[0]["has_checkpoint"] is True
                assert data[0]["checkpoint_summary"] == "epoch 15"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]


class TestOpsFiltering:
    """Tests for ops command filtering options."""

    def test_ops_status_filter(self, runner) -> None:
        """Ops command passes status filter to API."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"data": []}
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["ops", "--status", "running"])

                # Check that params include status filter (first call is /operations)
                call_args = mock_client.get.call_args_list[0]
                params = call_args[1].get("params", {})
                assert params.get("status") == "running"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_type_filter(self, runner) -> None:
        """Ops command passes type filter to API."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"data": []}
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["ops", "--type", "training"])

                call_args = mock_client.get.call_args_list[0]
                params = call_args[1].get("params", {})
                assert params.get("operation_type") == "training"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_active_filter(self, runner) -> None:
        """Ops command passes active filter to API."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"data": []}
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["ops", "--active"])

                call_args = mock_client.get.call_args_list[0]
                params = call_args[1].get("params", {})
                assert params.get("active_only") == "true"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_limit_option(self, runner) -> None:
        """Ops command passes limit to API."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = {"data": []}
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["ops", "--limit", "10"])

                call_args = mock_client.get.call_args_list[0]
                params = call_args[1].get("params", {})
                assert params.get("limit") == "10"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_resumable_filter(self, runner) -> None:
        """Ops command with --resumable shows only operations with checkpoints."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                async def mock_get(endpoint, **kwargs):
                    if endpoint == "/operations":
                        return {
                            "data": [
                                {
                                    "operation_id": "op_with_checkpoint",
                                    "operation_type": "training",
                                    "status": "failed",
                                },
                                {
                                    "operation_id": "op_no_checkpoint",
                                    "operation_type": "training",
                                    "status": "failed",
                                },
                            ]
                        }
                    elif "op_with_checkpoint" in endpoint:
                        return {"success": True, "data": {"state": {"epoch": 10}}}
                    elif "op_no_checkpoint" in endpoint:
                        return {"success": False}
                    return {}

                mock_client.get.side_effect = mock_get
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["ops", "--resumable"])

                assert result.exit_code == 0
                # Should only show operation with checkpoint
                assert "op_with_checkpoint" in result.output
                assert "op_no_checkpoint" not in result.output

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

    def test_ops_resumable_empty_message(self, runner) -> None:
        """Ops command with --resumable shows specific message when none found."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                async def mock_get(endpoint, **kwargs):
                    if endpoint == "/operations":
                        return {
                            "data": [
                                {
                                    "operation_id": "op_1",
                                    "operation_type": "training",
                                    "status": "failed",
                                },
                            ]
                        }
                    elif "/checkpoints/" in endpoint:
                        return {"success": False}
                    return {}

                mock_client.get.side_effect = mock_get
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["ops", "--resumable"])

                assert result.exit_code == 0
                assert "no resumable" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]


class TestOpsCheckpointErrors:
    """Tests for checkpoint fetching error handling."""

    def test_ops_handles_checkpoint_fetch_error(self, runner) -> None:
        """Ops command handles checkpoint fetch errors gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                async def mock_get(endpoint, **kwargs):
                    if endpoint == "/operations":
                        return {
                            "data": [
                                {
                                    "operation_id": "op_1",
                                    "operation_type": "training",
                                    "status": "running",
                                },
                            ]
                        }
                    elif "/checkpoints/" in endpoint:
                        raise CLIClientError("404 Not Found")
                    return {}

                mock_client.get.side_effect = mock_get
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["ops"])

                # Should not crash, just show no checkpoint
                assert result.exit_code == 0
                assert "op_1" in result.output

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]


class TestOpsErrors:
    """Tests for error handling in ops command."""

    def test_ops_exits_on_exception(self, runner) -> None:
        """Ops command exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.ops import ops

        app.command()(ops)

        try:
            with patch("ktrdr.cli.commands.ops.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["ops"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "ops"
            ]

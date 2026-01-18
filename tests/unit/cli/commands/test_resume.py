"""Tests for resume CLI command.

Tests the `ktrdr resume` command that resumes operations from checkpoint.
Replaces the old `ktrdr operations resume` command with a simpler path.

Note: The M2 design doc suggested using checkpoint IDs, but the actual backend
uses operation IDs for the resume endpoint. This implementation follows the
actual backend pattern per HANDOFF guidance.
"""

import json
from unittest.mock import AsyncMock, patch

from ktrdr.cli.client import APIError


class TestResumeCommandArguments:
    """Tests for resume command arguments."""

    def test_resume_requires_operation_id(self, runner) -> None:
        """Resume command requires operation_id argument."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            result = runner.invoke(app, ["resume"])

            # Should fail with missing argument error
            assert result.exit_code != 0
            assert (
                "missing" in result.output.lower()
                or "required" in result.output.lower()
            )

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]

    def test_resume_accepts_operation_id(self, runner) -> None:
        """Resume command accepts operation_id argument."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "success": True,
                    "data": {
                        "operation_id": "op_test123",
                        "status": "running",
                        "resumed_from": {"epoch": 10},
                    },
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["resume", "op_test123"])

                assert result.exit_code == 0

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]


class TestResumeOperation:
    """Tests for resume command operation."""

    def test_resume_calls_post_endpoint(self, runner) -> None:
        """Resume command calls POST on /operations/{id}/resume."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "success": True,
                    "data": {
                        "operation_id": "op_abc123",
                        "status": "running",
                        "resumed_from": {"epoch": 5},
                    },
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["resume", "op_abc123"])

                # Verify post was called with correct endpoint
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert call_args[0][0] == "/operations/op_abc123/resume"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]

    def test_resume_shows_success_message(self, runner) -> None:
        """Resume command shows success message with epoch info."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "success": True,
                    "data": {
                        "operation_id": "op_success123",
                        "status": "running",
                        "resumed_from": {"epoch": 29, "checkpoint_type": "periodic"},
                    },
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["resume", "op_success123"])

                assert result.exit_code == 0
                # Should show resumed message
                assert "resumed" in result.output.lower()
                assert "op_success123" in result.output
                # Should show epoch info
                assert "29" in result.output or "epoch" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]


class TestResumeFollowOption:
    """Tests for resume command --follow option."""

    def test_resume_follow_option(self, runner) -> None:
        """Resume command with --follow polls for progress."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                # First call: POST to resume
                # Subsequent calls: GET for status polling
                call_count = 0

                async def mock_request(endpoint, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if "/resume" in endpoint:
                        return {
                            "success": True,
                            "data": {
                                "operation_id": "op_follow123",
                                "status": "running",
                                "resumed_from": {"epoch": 10},
                            },
                        }
                    else:
                        # Status check - return completed after first poll
                        return {
                            "success": True,
                            "data": {
                                "operation_id": "op_follow123",
                                "status": "completed",
                                "progress": {"percentage": 100},
                            },
                        }

                mock_client.post.side_effect = mock_request
                mock_client.get.side_effect = mock_request
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["resume", "op_follow123", "--follow"])

                assert result.exit_code == 0
                # Should show completion message
                assert "completed" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]

    def test_resume_follow_shorthand(self, runner) -> None:
        """Resume command accepts -f shorthand for --follow."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None

                async def mock_request(endpoint, **kwargs):
                    if "/resume" in endpoint:
                        return {
                            "success": True,
                            "data": {
                                "operation_id": "op_123",
                                "status": "running",
                                "resumed_from": {"epoch": 1},
                            },
                        }
                    else:
                        return {
                            "success": True,
                            "data": {
                                "operation_id": "op_123",
                                "status": "completed",
                                "progress": {"percentage": 100},
                            },
                        }

                mock_client.post.side_effect = mock_request
                mock_client.get.side_effect = mock_request
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["resume", "op_123", "-f"])

                assert result.exit_code == 0
                # Should show completion (proves --follow was triggered)
                assert "completed" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]


class TestResumeJsonOutput:
    """Tests for resume command JSON output."""

    def test_resume_json_output(self, runner) -> None:
        """Resume command with --json outputs JSON."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "success": True,
                    "data": {
                        "operation_id": "op_json123",
                        "status": "running",
                        "resumed_from": {"epoch": 15, "checkpoint_type": "periodic"},
                    },
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "resume", "op_json123"])

                assert result.exit_code == 0
                # Output should be valid JSON
                data = json.loads(result.output)
                assert data["operation_id"] == "op_json123"
                assert data["status"] == "running"
                assert data["resumed_from"]["epoch"] == 15

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]


class TestResumeErrorHandling:
    """Tests for resume command error handling."""

    def test_resume_handles_not_found(self, runner) -> None:
        """Resume command handles operation not found gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.side_effect = APIError(
                    message="Operation not found",
                    status_code=404,
                    details={"operation_id": "op_notfound"},
                )
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["resume", "op_notfound"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]

    def test_resume_handles_no_checkpoint(self, runner) -> None:
        """Resume command handles no checkpoint available gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.side_effect = APIError(
                    message="No checkpoint available for operation",
                    status_code=404,
                    details={"operation_id": "op_nocheckpoint"},
                )
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["resume", "op_nocheckpoint"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]

    def test_resume_handles_already_running(self, runner) -> None:
        """Resume command handles already-running operation gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.side_effect = APIError(
                    message="Operation is already running",
                    status_code=409,
                    details={"operation_id": "op_running"},
                )
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["resume", "op_running"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]

    def test_resume_exits_on_exception(self, runner) -> None:
        """Resume command exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.resume import resume

        app.command()(resume)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["resume", "op_123"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "resume"
            ]

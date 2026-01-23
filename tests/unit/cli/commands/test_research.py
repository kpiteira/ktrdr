"""Tests for research CLI command.

Tests the `ktrdr research <goal>` command that triggers an AI research cycle
using the agent trigger API.
"""

import inspect
from unittest.mock import AsyncMock, patch


class TestResearchCommandArguments:
    """Tests for research command required arguments."""

    def test_research_command_requires_goal_or_strategy(self, runner) -> None:
        """Research command requires either goal argument or --strategy option."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            # Invoke without goal argument or --strategy
            result = runner.invoke(app, ["research"])
            # Should fail due to missing goal or strategy
            assert result.exit_code != 0
            # Error message should mention either goal or strategy is required
            assert (
                "either" in result.output.lower()
                or "required" in result.output.lower()
                or "goal" in result.output.lower()
            )
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]


class TestResearchCommandOptions:
    """Tests for research command optional arguments and defaults."""

    def test_research_command_model_default_none(self) -> None:
        """Research command has model default of None."""
        from ktrdr.cli.commands.research import research

        sig = inspect.signature(research)
        params = sig.parameters

        assert "model" in params
        param = params["model"]
        assert param.default.default is None

    def test_research_command_follow_default_false(self) -> None:
        """Research command has follow default of False."""
        from ktrdr.cli.commands.research import research

        sig = inspect.signature(research)
        params = sig.parameters

        assert "follow" in params
        param = params["follow"]
        assert param.default.default is False

    def test_research_command_has_model_shorthand(self) -> None:
        """Research command accepts -m as shorthand for --model."""
        from ktrdr.cli.commands.research import research

        sig = inspect.signature(research)
        params = sig.parameters

        # The model parameter should have -m option name
        model_param = params["model"]
        # Typer stores option names in the Option object
        # Check for existence of -m in the CLI
        assert model_param is not None  # Will verify via invocation test

    def test_research_command_has_follow_shorthand(self) -> None:
        """Research command accepts -f as shorthand for --follow."""
        from ktrdr.cli.commands.research import research

        sig = inspect.signature(research)
        params = sig.parameters

        follow_param = params["follow"]
        assert follow_param is not None  # Will verify via invocation test


class TestResearchCommandAPI:
    """Tests for research command API interactions."""

    def test_research_command_posts_to_agent_trigger(self, runner) -> None:
        """Research command posts goal to /agent/trigger endpoint."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_test123",
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["research", "build momentum strategy"])

                # Verify API was called
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert call_args[0][0] == "/agent/trigger"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_sends_goal_in_request(self, runner) -> None:
        """Research command sends goal as 'brief' in request body."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_test123",
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["research", "analyze volatility patterns"])

                call_args = mock_client.post.call_args
                json = call_args[1]["json"]
                assert json["brief"] == "analyze volatility patterns"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_passes_model_to_api(self, runner) -> None:
        """Research command passes --model to API."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_test123",
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["research", "test strategy", "--model", "haiku"])

                call_args = mock_client.post.call_args
                json = call_args[1]["json"]
                assert json["model"] == "haiku"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_model_shorthand_works(self, runner) -> None:
        """Research command accepts -m shorthand for model."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_test123",
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["research", "test strategy", "-m", "sonnet"])

                call_args = mock_client.post.call_args
                json = call_args[1]["json"]
                assert json["model"] == "sonnet"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]


class TestResearchCommandOutput:
    """Tests for research command output behavior."""

    def test_research_command_returns_operation_id(self, runner) -> None:
        """Research command outputs operation ID on success."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_research_abc123",
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["research", "test goal"])

                assert result.exit_code == 0
                assert "op_research_abc123" in result.output

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_fire_and_forget(self, runner) -> None:
        """Research command returns immediately without --follow."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_test",
                }
                mock_client_class.return_value = mock_client

                # Without follow, should not enter monitoring
                with patch(
                    "ktrdr.cli.helpers.agent_monitor.monitor_agent_cycle"
                ) as mock_monitor:
                    result = runner.invoke(app, ["research", "test goal"])

                    # Monitor should NOT be called
                    mock_monitor.assert_not_called()
                    assert result.exit_code == 0

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]


class TestResearchCommandFollow:
    """Tests for research command follow mode."""

    def test_research_command_follow_calls_monitor(self, runner) -> None:
        """Research command with --follow calls monitor function."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_follow_test",
                }
                mock_client_class.return_value = mock_client

                with patch(
                    "ktrdr.cli.helpers.agent_monitor.monitor_agent_cycle",
                    new_callable=AsyncMock,
                ) as mock_monitor:
                    runner.invoke(app, ["research", "test goal", "--follow"])

                    mock_monitor.assert_called_once_with("op_follow_test")

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_follow_shorthand_works(self, runner) -> None:
        """Research command accepts -f shorthand for follow."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_shorthand_test",
                }
                mock_client_class.return_value = mock_client

                with patch(
                    "ktrdr.cli.helpers.agent_monitor.monitor_agent_cycle",
                    new_callable=AsyncMock,
                ) as mock_monitor:
                    runner.invoke(app, ["research", "test goal", "-f"])

                    mock_monitor.assert_called_once_with("op_shorthand_test")

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]


class TestResearchCommandErrors:
    """Tests for error handling in research command."""

    def test_research_command_handles_trigger_failure(self, runner) -> None:
        """Research command handles trigger failure gracefully."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": False,
                    "reason": "active_cycle_exists",
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["research", "test goal"])

                # Should exit with error
                assert result.exit_code == 1
                assert (
                    "active" in result.output.lower()
                    or "could not start" in result.output.lower()
                )

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_exits_on_exception(self, runner) -> None:
        """Research command exits with code 1 on exception."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.side_effect = Exception("Connection failed")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["research", "test goal"])

                assert result.exit_code == 1

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]


class TestResearchCommandStrategy:
    """Tests for --strategy option to skip design phase."""

    def test_research_command_has_strategy_option(self) -> None:
        """Research command has --strategy option."""
        from ktrdr.cli.commands.research import research

        sig = inspect.signature(research)
        params = sig.parameters

        assert "strategy" in params
        param = params["strategy"]
        assert param.default.default is None

    def test_research_command_strategy_sends_to_api(self, runner) -> None:
        """Research command sends strategy in request body (not brief)."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_strategy_test",
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["research", "--strategy", "v3_minimal"])

                call_args = mock_client.post.call_args
                json = call_args[1]["json"]
                assert json["strategy"] == "v3_minimal"
                assert "brief" not in json

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_strategy_shorthand_works(self, runner) -> None:
        """Research command accepts -s shorthand for strategy."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_strategy_test",
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["research", "-s", "v3_minimal"])

                call_args = mock_client.post.call_args
                json = call_args[1]["json"]
                assert json["strategy"] == "v3_minimal"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_strategy_with_model(self, runner) -> None:
        """Research command accepts --strategy with --model."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_strategy_test",
                }
                mock_client_class.return_value = mock_client

                runner.invoke(
                    app, ["research", "--strategy", "v3_minimal", "--model", "haiku"]
                )

                call_args = mock_client.post.call_args
                json = call_args[1]["json"]
                assert json["strategy"] == "v3_minimal"
                assert json["model"] == "haiku"

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_rejects_both_goal_and_strategy(self, runner) -> None:
        """Research command rejects both goal and --strategy."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            result = runner.invoke(
                app, ["research", "build momentum strategy", "--strategy", "v3_minimal"]
            )

            # Should fail due to mutual exclusivity
            assert result.exit_code != 0
            assert "cannot" in result.output.lower() or "both" in result.output.lower()

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_requires_goal_or_strategy(self, runner) -> None:
        """Research command requires either goal or --strategy."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            result = runner.invoke(app, ["research"])

            # Should fail due to missing required argument
            assert result.exit_code != 0
            assert (
                "either" in result.output.lower()
                or "required" in result.output.lower()
                or "missing" in result.output.lower()
            )

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

    def test_research_command_goal_optional_with_strategy(self, runner) -> None:
        """Research command allows omitting goal when --strategy provided."""
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.research import research

        app.command()(research)

        try:
            with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "triggered": True,
                    "operation_id": "op_strategy_only",
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["research", "--strategy", "v3_minimal"])

                # Should succeed without goal argument
                assert result.exit_code == 0
                assert "op_strategy_only" in result.output

        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "research"
            ]

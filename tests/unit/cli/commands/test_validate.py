"""Tests for validate CLI command.

Tests the `ktrdr validate` command for validating strategies via API or locally.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch


def _register_validate_cmd(app):
    """Register validate command with explicit name."""
    from ktrdr.cli.commands.validate import validate_cmd

    app.command("validate")(validate_cmd)


def _cleanup_validate_cmd(app):
    """Clean up validate command from app."""
    app.registered_commands = [
        cmd for cmd in app.registered_commands if cmd.name != "validate"
    ]


class TestValidateCommandStructure:
    """Tests for validate command structure and registration."""

    def test_validate_command_exists(self, runner) -> None:
        """Validate command is registered."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            result = runner.invoke(app, ["validate", "--help"])

            assert result.exit_code == 0
            assert "validate" in result.output.lower()
            # Should mention strategy name or path
            assert (
                "strategy" in result.output.lower() or "target" in result.output.lower()
            )

        finally:
            _cleanup_validate_cmd(app)

    def test_validate_requires_target(self, runner) -> None:
        """Validate requires target argument (name or path)."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            result = runner.invoke(app, ["validate"])

            # Should fail - missing required argument
            assert result.exit_code != 0

        finally:
            _cleanup_validate_cmd(app)


class TestValidateAPIMode:
    """Tests for API-based validation (strategy by name)."""

    def test_validate_by_name_calls_api(self, runner) -> None:
        """Validate by name calls /strategies/validate/{name} endpoint."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            with patch(
                "ktrdr.cli.commands.validate.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "success": True,
                    "valid": True,
                    "strategy_name": "momentum",
                    "issues": [],
                    "message": "Strategy 'momentum' is valid",
                }
                mock_client_class.return_value = mock_client

                runner.invoke(app, ["validate", "momentum"])

                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert "/strategies/validate/momentum" in call_args[0][0]

        finally:
            _cleanup_validate_cmd(app)

    def test_validate_api_valid_shows_success(self, runner) -> None:
        """Valid strategy via API shows success message."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            with patch(
                "ktrdr.cli.commands.validate.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "success": True,
                    "valid": True,
                    "strategy_name": "momentum",
                    "issues": [],
                    "message": "Strategy 'momentum' is valid",
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["validate", "momentum"])

                assert result.exit_code == 0
                assert "valid" in result.output.lower()

        finally:
            _cleanup_validate_cmd(app)

    def test_validate_api_invalid_shows_errors(self, runner) -> None:
        """Invalid strategy via API shows errors and exits with code 1."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            with patch(
                "ktrdr.cli.commands.validate.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "success": True,
                    "valid": False,
                    "strategy_name": "broken",
                    "issues": [
                        {
                            "severity": "error",
                            "category": "indicator",
                            "message": "Unknown indicator type 'fake'",
                        }
                    ],
                    "message": "Strategy 'broken' has 1 error(s)",
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["validate", "broken"])

                assert result.exit_code == 1
                # Should show error info
                assert (
                    "invalid" in result.output.lower()
                    or "error" in result.output.lower()
                )

        finally:
            _cleanup_validate_cmd(app)

    def test_validate_api_json_output(self, runner) -> None:
        """Validate with --json outputs JSON."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            with patch(
                "ktrdr.cli.commands.validate.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.return_value = {
                    "success": True,
                    "valid": True,
                    "strategy_name": "momentum",
                    "issues": [],
                    "message": "Strategy 'momentum' is valid",
                }
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["--json", "validate", "momentum"])

                assert result.exit_code == 0
                data = json.loads(result.output)
                assert data["valid"] is True
                assert "strategy_name" in data or "name" in data

        finally:
            _cleanup_validate_cmd(app)


class TestValidateLocalMode:
    """Tests for local file validation (path mode)."""

    def test_validate_detects_relative_path(self, runner) -> None:
        """Validate detects ./path as local file mode (does not call API)."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            # Mock local validation to succeed
            with patch("ktrdr.cli.commands.validate._validate_local") as mock_local:
                mock_local.return_value = None  # No raise = success

                with patch(
                    "ktrdr.cli.commands.validate.AsyncCLIClient"
                ) as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client_class.return_value = mock_client

                    runner.invoke(app, ["validate", "./some/path/strategy.yaml"])

                    # Should call local validation, not API
                    mock_local.assert_called_once()
                    mock_client.post.assert_not_called()

        finally:
            _cleanup_validate_cmd(app)

    def test_validate_detects_absolute_path(self, runner) -> None:
        """Validate detects /path as local file mode."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            with patch("ktrdr.cli.commands.validate._validate_local") as mock_local:
                mock_local.return_value = None  # Simulate success

                with patch(
                    "ktrdr.cli.commands.validate.AsyncCLIClient"
                ) as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client_class.return_value = mock_client

                    runner.invoke(app, ["validate", "/absolute/path/strategy.yaml"])

                    # Should call local validation, not API
                    mock_local.assert_called_once()
                    mock_client.post.assert_not_called()

        finally:
            _cleanup_validate_cmd(app)

    def test_validate_local_file_not_found(self, runner) -> None:
        """Validate local mode shows error for missing file."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            result = runner.invoke(app, ["validate", "./nonexistent.yaml"])

            assert result.exit_code == 1
            assert (
                "not found" in result.output.lower() or "error" in result.output.lower()
            )

        finally:
            _cleanup_validate_cmd(app)

    def test_validate_local_valid_v3_strategy(self, runner, tmp_path) -> None:
        """Validate local v3 strategy shows success."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        # Create a v3-looking strategy file (indicators as dict, has nn_inputs)
        strategy_file = tmp_path / "v3_strategy.yaml"
        strategy_file.write_text(
            """
name: test_v3
indicators:
  rsi_14:
    type: RSI
nn_inputs:
  - fuzzy_set: rsi_levels
fuzzy_sets:
  rsi_levels:
    indicator: rsi_14
"""
        )

        try:
            # Patch the actual validation functions at their source
            with patch(
                "ktrdr.config.strategy_loader.StrategyConfigurationLoader"
            ) as mock_loader_class:
                mock_loader = MagicMock()
                mock_config = MagicMock()
                mock_config.name = "test_v3"
                mock_loader.load_v3_strategy.return_value = mock_config
                mock_loader_class.return_value = mock_loader

                with patch(
                    "ktrdr.config.feature_resolver.FeatureResolver"
                ) as mock_resolver_class:
                    mock_resolver = MagicMock()
                    mock_resolver.resolve.return_value = [MagicMock()]  # One feature
                    mock_resolver_class.return_value = mock_resolver

                    result = runner.invoke(app, ["validate", str(strategy_file)])

                    assert result.exit_code == 0
                    assert "valid" in result.output.lower()

        finally:
            _cleanup_validate_cmd(app)

    def test_validate_local_json_output(self, runner, tmp_path) -> None:
        """Validate local with --json outputs JSON."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        # Create a v3 strategy file
        strategy_file = tmp_path / "strategy.yaml"
        strategy_file.write_text(
            """
name: test
indicators:
  rsi_14:
    type: RSI
nn_inputs:
  - fuzzy_set: rsi_levels
fuzzy_sets:
  rsi_levels:
    indicator: rsi_14
"""
        )

        try:
            with patch(
                "ktrdr.config.strategy_loader.StrategyConfigurationLoader"
            ) as mock_loader_class:
                mock_loader = MagicMock()
                mock_config = MagicMock()
                mock_config.name = "test"
                mock_loader.load_v3_strategy.return_value = mock_config
                mock_loader_class.return_value = mock_loader

                with patch(
                    "ktrdr.config.feature_resolver.FeatureResolver"
                ) as mock_resolver_class:
                    mock_resolver = MagicMock()
                    mock_resolver.resolve.return_value = []
                    mock_resolver_class.return_value = mock_resolver

                    result = runner.invoke(
                        app, ["--json", "validate", str(strategy_file)]
                    )

                    assert result.exit_code == 0
                    data = json.loads(result.output)
                    assert data["valid"] is True

        finally:
            _cleanup_validate_cmd(app)


class TestValidateErrorHandling:
    """Tests for error handling in validate command."""

    def test_validate_api_connection_error(self, runner) -> None:
        """Validate handles API connection errors."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            with patch(
                "ktrdr.cli.commands.validate.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.side_effect = Exception("Connection refused")
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["validate", "momentum"])

                assert result.exit_code == 1

        finally:
            _cleanup_validate_cmd(app)

    def test_validate_api_strategy_not_found(self, runner) -> None:
        """Validate handles strategy not found from API."""
        from ktrdr.cli.app import app

        _register_validate_cmd(app)

        try:
            with patch(
                "ktrdr.cli.commands.validate.AsyncCLIClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.post.side_effect = Exception(
                    "Strategy not found: nonexistent"
                )
                mock_client_class.return_value = mock_client

                result = runner.invoke(app, ["validate", "nonexistent"])

                assert result.exit_code == 1
                assert (
                    "not found" in result.output.lower()
                    or "error" in result.output.lower()
                )

        finally:
            _cleanup_validate_cmd(app)

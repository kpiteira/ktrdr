"""Tests for the migrate command.

Tests the `ktrdr migrate` command for v2 to v3 strategy migration.

Uses the shared `runner` fixture from conftest.py which provides
ANSI-stripped output via CleanCliRunner.
"""

import pytest
import yaml

from ktrdr.cli.app import app

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def v2_strategy_yaml() -> str:
    """Fixture providing a v2 strategy YAML (list-based indicators)."""
    return """
name: "test_v2_strategy"
version: "2.0"

training_data:
  symbols:
    mode: single_symbol
    list: [EURUSD]
  timeframes:
    mode: multi_timeframe
    list: [5m, 1h]
    base_timeframe: 1h
  history_required: 100

indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
  - name: bbands
    feature_id: bbands_20
    period: 20
    multiplier: 2.0

fuzzy_sets:
  rsi_14:
    oversold:
      type: triangular
      parameters: [0, 20, 35]
    overbought:
      type: triangular
      parameters: [65, 80, 100]

model:
  type: mlp
  architecture:
    hidden_layers: [64, 32]

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
"""


@pytest.fixture
def v3_strategy_yaml() -> str:
    """Fixture providing an already-v3 strategy YAML."""
    return """
name: "test_v3_strategy"
version: "3.0"

training_data:
  symbols:
    mode: single
    list: [EURUSD]
  timeframes:
    mode: multi_timeframe
    list: [5m, 1h]
    base_timeframe: 1h
  history_required: 100

indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_fast:
    indicator: rsi_14
    oversold: [0, 25, 40]

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: all

model:
  type: mlp

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
"""


# ============================================================================
# Helper functions for command registration
# ============================================================================


def _register_migrate_cmd(target_app):
    """Register the migrate command on target app."""
    from ktrdr.cli.commands.migrate import migrate_cmd

    target_app.command("migrate")(migrate_cmd)


def _cleanup_migrate_cmd(target_app):
    """Remove the migrate command from target app."""
    target_app.registered_commands = [
        cmd for cmd in target_app.registered_commands if cmd.name != "migrate"
    ]


# ============================================================================
# Test Classes
# ============================================================================


class TestMigrateCommandExists:
    """Tests that the migrate command is properly registered."""

    def test_migrate_command_exists(self, runner) -> None:
        """Test that migrate command is available."""
        _register_migrate_cmd(app)
        try:
            result = runner.invoke(app, ["migrate", "--help"])
            assert result.exit_code == 0
            assert "migrate" in result.output.lower()
        finally:
            _cleanup_migrate_cmd(app)

    def test_migrate_requires_path_argument(self, runner) -> None:
        """Test that migrate command requires a path argument."""
        _register_migrate_cmd(app)
        try:
            result = runner.invoke(app, ["migrate", "--help"])
            assert "path" in result.output.lower()
        finally:
            _cleanup_migrate_cmd(app)

    def test_migrate_has_output_option(self, runner) -> None:
        """Test that migrate has --output/-o option."""
        _register_migrate_cmd(app)
        try:
            result = runner.invoke(app, ["migrate", "--help"])
            assert "--output" in result.output or "-o" in result.output
        finally:
            _cleanup_migrate_cmd(app)


class TestMigrateV2Strategy:
    """Tests for migrating v2 strategies to v3."""

    def test_migrate_creates_v3_output_file(
        self, runner, v2_strategy_yaml, tmp_path
    ) -> None:
        """Test that migrating a v2 file creates a v3 output file."""
        _register_migrate_cmd(app)
        try:
            # Create v2 input file
            input_file = tmp_path / "v2_strategy.yaml"
            input_file.write_text(v2_strategy_yaml)

            # Migrate with explicit output
            output_file = tmp_path / "v3_strategy.yaml"
            result = runner.invoke(
                app,
                ["migrate", str(input_file), "-o", str(output_file)],
            )

            # Should succeed
            assert result.exit_code == 0, f"Output: {result.output}"

            # Output file should exist
            assert output_file.exists()

            # Output should be v3 format
            with open(output_file) as f:
                migrated = yaml.safe_load(f)

            assert migrated["version"] == "3.0"
            assert isinstance(migrated["indicators"], dict)
            assert "nn_inputs" in migrated
        finally:
            _cleanup_migrate_cmd(app)

    def test_migrate_default_output_appends_v3(
        self, runner, v2_strategy_yaml, tmp_path
    ) -> None:
        """Test that default output creates {name}_v3.yaml."""
        _register_migrate_cmd(app)
        try:
            # Create v2 input file
            input_file = tmp_path / "strategy.yaml"
            input_file.write_text(v2_strategy_yaml)

            result = runner.invoke(app, ["migrate", str(input_file)])

            # Should succeed
            assert result.exit_code == 0, f"Output: {result.output}"

            # Default output file should be created
            default_output = tmp_path / "strategy_v3.yaml"
            assert default_output.exists()
        finally:
            _cleanup_migrate_cmd(app)

    def test_migrate_shows_success_message(
        self, runner, v2_strategy_yaml, tmp_path
    ) -> None:
        """Test that successful migration shows a confirmation message."""
        _register_migrate_cmd(app)
        try:
            input_file = tmp_path / "v2_strategy.yaml"
            input_file.write_text(v2_strategy_yaml)

            result = runner.invoke(app, ["migrate", str(input_file)])

            assert result.exit_code == 0
            # Should indicate migration completed
            assert "migrated" in result.output.lower()
        finally:
            _cleanup_migrate_cmd(app)


class TestMigrateAlreadyV3:
    """Tests for handling already-v3 strategies."""

    def test_already_v3_shows_skip_message(
        self, runner, v3_strategy_yaml, tmp_path
    ) -> None:
        """Test that already-v3 files show a skip message."""
        _register_migrate_cmd(app)
        try:
            input_file = tmp_path / "v3_strategy.yaml"
            input_file.write_text(v3_strategy_yaml)

            result = runner.invoke(app, ["migrate", str(input_file)])

            # Should succeed (skipping is not an error)
            assert result.exit_code == 0
            # Should indicate file was skipped
            assert "already" in result.output.lower() or "v3" in result.output.lower()
        finally:
            _cleanup_migrate_cmd(app)

    def test_already_v3_does_not_create_output(
        self, runner, v3_strategy_yaml, tmp_path
    ) -> None:
        """Test that already-v3 files don't create new output files."""
        _register_migrate_cmd(app)
        try:
            input_file = tmp_path / "v3_strategy.yaml"
            input_file.write_text(v3_strategy_yaml)

            result = runner.invoke(app, ["migrate", str(input_file)])

            assert result.exit_code == 0
            # No _v3.yaml output should be created
            possible_output = tmp_path / "v3_strategy_v3.yaml"
            assert not possible_output.exists()
        finally:
            _cleanup_migrate_cmd(app)


class TestMigrateJsonOutput:
    """Tests for JSON output mode."""

    def test_json_output_on_success(self, runner, v2_strategy_yaml, tmp_path) -> None:
        """Test that --json outputs structured JSON on success."""
        import json

        _register_migrate_cmd(app)
        try:
            input_file = tmp_path / "v2_strategy.yaml"
            input_file.write_text(v2_strategy_yaml)

            result = runner.invoke(app, ["--json", "migrate", str(input_file)])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["status"] == "migrated"
            assert "input" in data
            assert "output" in data
        finally:
            _cleanup_migrate_cmd(app)

    def test_json_output_on_skip(self, runner, v3_strategy_yaml, tmp_path) -> None:
        """Test that --json outputs structured JSON when skipping."""
        import json

        _register_migrate_cmd(app)
        try:
            input_file = tmp_path / "v3_strategy.yaml"
            input_file.write_text(v3_strategy_yaml)

            result = runner.invoke(app, ["--json", "migrate", str(input_file)])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["status"] == "skipped"
            assert "already" in data.get("reason", "").lower()
        finally:
            _cleanup_migrate_cmd(app)


class TestMigrateErrorHandling:
    """Tests for error handling."""

    def test_nonexistent_file_shows_error(self, runner) -> None:
        """Test that nonexistent file shows clear error."""
        _register_migrate_cmd(app)
        try:
            result = runner.invoke(app, ["migrate", "/tmp/does_not_exist.yaml"])

            assert result.exit_code != 0
            assert (
                "not found" in result.output.lower() or "error" in result.output.lower()
            )
        finally:
            _cleanup_migrate_cmd(app)

    def test_invalid_yaml_shows_error(self, runner, tmp_path) -> None:
        """Test that invalid YAML shows clear error."""
        _register_migrate_cmd(app)
        try:
            input_file = tmp_path / "invalid.yaml"
            input_file.write_text("invalid: [yaml: content")

            result = runner.invoke(app, ["migrate", str(input_file)])

            assert result.exit_code != 0
        finally:
            _cleanup_migrate_cmd(app)

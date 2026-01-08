"""
Tests for CLI strategy migrate command.

This module tests the `ktrdr strategies migrate` command for v2 to v3 migration.
"""

import pytest
import yaml
from typer.testing import CliRunner

from ktrdr.cli.strategy_commands import strategies_app


@pytest.fixture
def cli_runner():
    """Fixture providing a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def v2_strategy_yaml():
    """Fixture providing a v2 strategy YAML (list-based indicators)."""
    return """
name: "v2_test_strategy"
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
    feature_id: bbands_20_2
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
def v3_strategy_yaml():
    """Fixture providing an already-v3 strategy YAML."""
    return """
name: "v3_strategy"
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


class TestStrategyMigrateCommand:
    """Test suite for the `ktrdr strategies migrate` command."""

    def test_command_exists(self, cli_runner):
        """Test that the migrate command exists and shows help."""
        result = cli_runner.invoke(strategies_app, ["migrate", "--help"])
        assert result.exit_code == 0
        assert "migrate" in result.stdout.lower()
        assert "--dry-run" in result.stdout
        assert "--backup" in result.stdout
        assert "--output" in result.stdout

    def test_single_file_migration_works(self, cli_runner, v2_strategy_yaml, tmp_path):
        """Test that a single v2 file is migrated to v3."""
        # Create v2 strategy file
        input_file = tmp_path / "v2_strategy.yaml"
        input_file.write_text(v2_strategy_yaml)

        # Migrate with explicit output
        output_file = tmp_path / "v3_strategy.yaml"
        result = cli_runner.invoke(
            strategies_app,
            ["migrate", str(input_file), "--output", str(output_file)],
        )

        # Should succeed
        assert (
            result.exit_code == 0
        ), f"Exit code: {result.exit_code}, Output: {result.stdout}"
        assert "migrated" in result.stdout.lower()

        # Output file should exist
        assert output_file.exists()

        # Output should be v3 format
        with open(output_file) as f:
            migrated = yaml.safe_load(f)

        assert migrated["version"] == "3.0"
        assert isinstance(migrated["indicators"], dict)
        assert "nn_inputs" in migrated
        assert "rsi_14" in migrated["indicators"]
        assert migrated["indicators"]["rsi_14"]["type"] == "rsi"

    def test_dry_run_shows_changes_without_writing(
        self, cli_runner, v2_strategy_yaml, tmp_path
    ):
        """Test that dry-run shows what would change without writing."""
        input_file = tmp_path / "v2_strategy.yaml"
        input_file.write_text(v2_strategy_yaml)

        # Original modification time
        original_content = input_file.read_text()

        result = cli_runner.invoke(
            strategies_app,
            ["migrate", str(input_file), "--dry-run"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Should indicate dry run
        assert "dry run" in result.stdout.lower()

        # Should show migration preview
        assert "indicators" in result.stdout.lower()
        assert (
            "nn_inputs" in result.stdout.lower() or "nn inputs" in result.stdout.lower()
        )

        # Original file should be unchanged
        assert input_file.read_text() == original_content

    def test_backup_created_when_requested(
        self, cli_runner, v2_strategy_yaml, tmp_path
    ):
        """Test that backup is created when --backup flag is used."""
        input_file = tmp_path / "v2_strategy.yaml"
        input_file.write_text(v2_strategy_yaml)
        original_content = input_file.read_text()

        # Migrate in place with backup
        result = cli_runner.invoke(
            strategies_app,
            ["migrate", str(input_file), "--backup"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Backup file should exist
        backup_file = tmp_path / "v2_strategy.yaml.bak"
        assert backup_file.exists(), f"Backup file not found. Output: {result.stdout}"

        # Backup should have original content
        assert backup_file.read_text() == original_content

        # Original file should be migrated
        with open(input_file) as f:
            migrated = yaml.safe_load(f)
        assert migrated["version"] == "3.0"

    def test_output_path_option_works(self, cli_runner, v2_strategy_yaml, tmp_path):
        """Test that --output option writes to specified path."""
        input_file = tmp_path / "input.yaml"
        input_file.write_text(v2_strategy_yaml)

        output_file = tmp_path / "subdir" / "output.yaml"

        result = cli_runner.invoke(
            strategies_app,
            ["migrate", str(input_file), "--output", str(output_file)],
        )

        # Should succeed
        assert result.exit_code == 0

        # Output file should exist at specified path
        assert output_file.exists()

        # Original should be unchanged
        with open(input_file) as f:
            original = yaml.safe_load(f)
        assert isinstance(original["indicators"], list)  # Still v2

    def test_already_v3_files_skipped(self, cli_runner, v3_strategy_yaml, tmp_path):
        """Test that already-v3 files are skipped with a message."""
        input_file = tmp_path / "v3_strategy.yaml"
        input_file.write_text(v3_strategy_yaml)

        result = cli_runner.invoke(
            strategies_app,
            ["migrate", str(input_file)],
        )

        # Should succeed (skipping is not an error)
        assert result.exit_code == 0

        # Should indicate file was skipped
        assert "skip" in result.stdout.lower() or "already" in result.stdout.lower()

    def test_directory_migration_works(self, cli_runner, v2_strategy_yaml, tmp_path):
        """Test that migrating a directory processes all YAML files."""
        # Create multiple v2 strategy files
        (tmp_path / "strat1.yaml").write_text(v2_strategy_yaml)
        (tmp_path / "strat2.yml").write_text(v2_strategy_yaml)

        result = cli_runner.invoke(
            strategies_app,
            ["migrate", str(tmp_path), "--dry-run"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Should process both files
        assert "strat1.yaml" in result.stdout
        assert "strat2.yml" in result.stdout

    def test_nonexistent_path_shows_error(self, cli_runner):
        """Test that nonexistent path shows clear error."""
        result = cli_runner.invoke(
            strategies_app, ["migrate", "/tmp/does_not_exist.yaml"]
        )

        # Should fail
        assert result.exit_code != 0

        # Should mention file not found
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_validation_runs_after_migration(
        self, cli_runner, v2_strategy_yaml, tmp_path
    ):
        """Test that validation runs and reports result after migration."""
        input_file = tmp_path / "v2_strategy.yaml"
        input_file.write_text(v2_strategy_yaml)

        output_file = tmp_path / "v3_migrated.yaml"

        result = cli_runner.invoke(
            strategies_app,
            ["migrate", str(input_file), "--output", str(output_file)],
        )

        # Should succeed
        assert result.exit_code == 0

        # Should mention validation
        assert "validation" in result.stdout.lower() or "valid" in result.stdout.lower()

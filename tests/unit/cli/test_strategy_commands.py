"""
Tests for CLI strategy commands, focusing on v3 strategy validation.

This module tests the `ktrdr strategies validate` command with v3 strategies.
"""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ktrdr.cli.strategy_commands import strategies_app


@pytest.fixture
def cli_runner():
    """Fixture providing a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def valid_v3_strategy_yaml():
    """Fixture providing a valid v3 strategy YAML content."""
    return """
name: "test_strategy"
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
    overbought: [60, 75, 100]

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: [5m, 1h]

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
def v2_strategy_yaml():
    """Fixture providing a v2 strategy YAML (list-based indicators)."""
    return """
name: "v2_strategy"
version: "2.0"

training_data:
  symbols:
    mode: single
    list: [TEST]
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h

indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14

fuzzy_sets:
  rsi_14:
    oversold:
      type: triangular
      parameters: [0, 20, 35]

model:
  type: mlp

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
"""


@pytest.fixture
def invalid_ref_strategy_yaml():
    """Fixture providing v3 strategy with invalid indicator reference."""
    return """
name: "invalid_strategy"
version: "3.0"

training_data:
  symbols:
    mode: single
    list: [TEST]
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h
  history_required: 100

indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  bad_ref:
    indicator: nonexistent_indicator
    low: [0, 25, 50]

nn_inputs:
  - fuzzy_set: bad_ref
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


class TestStrategyValidateCommand:
    """Test suite for the `ktrdr strategies validate` command with v3 strategies."""

    def test_command_exists(self, cli_runner):
        """Test that the validate command exists and shows help."""
        result = cli_runner.invoke(strategies_app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "validate" in result.stdout.lower()

    def test_valid_v3_strategy_shows_features(self, cli_runner, valid_v3_strategy_yaml):
        """Test that a valid v3 strategy passes validation and displays features."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(valid_v3_strategy_yaml)
            tmp_path = tmp.name

        try:
            result = cli_runner.invoke(strategies_app, ["validate", tmp_path])

            # Should succeed
            assert result.exit_code == 0

            # Should mention strategy name
            assert "test_strategy" in result.stdout

            # Should show it's v3 format
            assert "v3" in result.stdout.lower()

            # Should show feature count
            assert "4" in result.stdout  # 2 timeframes × 2 memberships

            # Should list the actual features
            assert "5m_rsi_fast_oversold" in result.stdout
            assert "5m_rsi_fast_overbought" in result.stdout
            assert "1h_rsi_fast_oversold" in result.stdout
            assert "1h_rsi_fast_overbought" in result.stdout

        finally:
            Path(tmp_path).unlink()

    def test_v2_strategy_uses_v2_validator(self, cli_runner, v2_strategy_yaml):
        """Test that v2 strategies are validated via v2 validator (not v3)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(v2_strategy_yaml)
            tmp_path = tmp.name

        try:
            result = cli_runner.invoke(strategies_app, ["validate", tmp_path])

            # Should fail (missing scope/deployment fields required for v2)
            assert result.exit_code == 1

            # Should use v2 validation path (shows "Validating strategy:", not "v3 strategy:")
            assert "validating strategy:" in result.stdout.lower()
            assert "v3 strategy" not in result.stdout.lower()

        finally:
            Path(tmp_path).unlink()

    def test_invalid_strategy_shows_error_and_exits_1(
        self, cli_runner, invalid_ref_strategy_yaml
    ):
        """Test that invalid v3 strategy shows clear error message."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(invalid_ref_strategy_yaml)
            tmp_path = tmp.name

        try:
            result = cli_runner.invoke(strategies_app, ["validate", tmp_path])

            # Should fail
            assert result.exit_code == 1

            # Should mention the invalid reference
            assert "nonexistent" in result.stdout.lower()

        finally:
            Path(tmp_path).unlink()

    def test_nonexistent_file_shows_error(self, cli_runner):
        """Test that nonexistent file path shows clear error."""
        result = cli_runner.invoke(
            strategies_app, ["validate", "/tmp/does_not_exist.yaml"]
        )

        # Should fail
        assert result.exit_code == 1

        # Should mention file not found
        assert "not found" in result.stdout.lower()

    def test_invalid_yaml_shows_error(self, cli_runner):
        """Test that malformed YAML shows clear error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write("invalid: yaml: content: [[[")
            tmp_path = tmp.name

        try:
            result = cli_runner.invoke(strategies_app, ["validate", tmp_path])

            # Should fail
            assert result.exit_code == 1

        finally:
            Path(tmp_path).unlink()

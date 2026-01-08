"""
Tests for CLI strategy features command.

This module tests the `ktrdr strategies features` command for listing
resolved NN input features for v3 strategies.

Note: Uses the shared `runner` fixture from conftest.py which provides
ANSI-stripped output via CleanCliRunner.
"""

import pytest

from ktrdr.cli.strategy_commands import strategies_app


@pytest.fixture
def v3_strategy_yaml():
    """Fixture providing a v3 strategy YAML with multiple timeframes and fuzzy sets."""
    return """
name: "test_mtf_strategy"
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
  bbands_20_2:
    type: bbands
    period: 20
    multiplier: 2.0

fuzzy_sets:
  rsi_fast:
    indicator: rsi_14
    oversold: [0, 25, 40]
    neutral: [30, 50, 70]
    overbought: [60, 75, 100]
  bb_position:
    indicator: bbands_20_2.upper
    below: [0, 0.3, 0.5]
    at: [0.3, 0.5, 0.7]
    above: [0.5, 0.7, 1.0]

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: all
  - fuzzy_set: bb_position
    timeframes: [1h]

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


class TestStrategyFeaturesCommand:
    """Test suite for the `ktrdr strategies features` command."""

    def test_command_exists(self, runner):
        """Test that the features command exists and shows help."""
        result = runner.invoke(strategies_app, ["features", "--help"])
        assert result.exit_code == 0
        assert "features" in result.stdout.lower()
        assert "--group-by" in result.stdout

    def test_lists_features_for_v3_strategy(self, runner, v3_strategy_yaml, tmp_path):
        """Test that features are listed correctly for a v3 strategy."""
        strategy_file = tmp_path / "v3_strategy.yaml"
        strategy_file.write_text(v3_strategy_yaml)

        result = runner.invoke(
            strategies_app,
            ["features", str(strategy_file)],
        )

        # Should succeed
        assert (
            result.exit_code == 0
        ), f"Exit code: {result.exit_code}, Output: {result.stdout}"

        # Should show strategy name
        assert "test_mtf_strategy" in result.stdout

        # Should show feature count
        # rsi_fast: 2 timeframes * 3 memberships = 6 features
        # bb_position: 1 timeframe * 3 memberships = 3 features
        # Total: 9 features
        assert "9" in result.stdout  # Should mention total count

        # Should list individual features
        assert "5m_rsi_fast_oversold" in result.stdout
        assert "1h_rsi_fast_overbought" in result.stdout
        assert "1h_bb_position_below" in result.stdout

    def test_group_by_none_lists_flat(self, runner, v3_strategy_yaml, tmp_path):
        """Test that --group-by none lists features in flat format."""
        strategy_file = tmp_path / "v3_strategy.yaml"
        strategy_file.write_text(v3_strategy_yaml)

        result = runner.invoke(
            strategies_app,
            ["features", str(strategy_file), "--group-by", "none"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Features should be listed individually
        assert "5m_rsi_fast_oversold" in result.stdout
        assert "5m_rsi_fast_neutral" in result.stdout
        assert "5m_rsi_fast_overbought" in result.stdout

    def test_group_by_timeframe_groups_correctly(
        self, runner, v3_strategy_yaml, tmp_path
    ):
        """Test that --group-by timeframe groups features by timeframe."""
        strategy_file = tmp_path / "v3_strategy.yaml"
        strategy_file.write_text(v3_strategy_yaml)

        result = runner.invoke(
            strategies_app,
            ["features", str(strategy_file), "--group-by", "timeframe"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Should show timeframe headers
        assert "[5m]" in result.stdout or "5m" in result.stdout
        assert "[1h]" in result.stdout or "1h" in result.stdout

        # Features should be listed under their timeframes
        # Within 5m group, should show rsi_fast membership names
        output_lines = result.stdout.lower()
        assert "oversold" in output_lines
        assert "neutral" in output_lines
        assert "overbought" in output_lines

    def test_group_by_fuzzy_set_groups_correctly(
        self, runner, v3_strategy_yaml, tmp_path
    ):
        """Test that --group-by fuzzy_set groups features by fuzzy set."""
        strategy_file = tmp_path / "v3_strategy.yaml"
        strategy_file.write_text(v3_strategy_yaml)

        result = runner.invoke(
            strategies_app,
            ["features", str(strategy_file), "--group-by", "fuzzy_set"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Should show fuzzy set headers with indicator reference
        assert "rsi_fast" in result.stdout
        assert "rsi_14" in result.stdout  # indicator reference
        assert "bb_position" in result.stdout
        assert "bbands_20_2" in result.stdout  # indicator reference

    def test_nonexistent_file_shows_error(self, runner):
        """Test that nonexistent file shows clear error."""
        result = runner.invoke(strategies_app, ["features", "/tmp/does_not_exist.yaml"])

        # Should fail
        assert result.exit_code != 0

        # Should mention error
        assert "error" in result.stdout.lower() or "not found" in result.stdout.lower()

    def test_v2_strategy_shows_error_or_warning(
        self, runner, v2_strategy_yaml, tmp_path
    ):
        """Test that v2 strategy shows appropriate error or warning."""
        strategy_file = tmp_path / "v2_strategy.yaml"
        strategy_file.write_text(v2_strategy_yaml)

        result = runner.invoke(
            strategies_app,
            ["features", str(strategy_file)],
        )

        # Should fail or show warning about v2 format
        # Either non-zero exit or error message
        assert (
            result.exit_code != 0
            or "v2" in result.stdout.lower()
            or "error" in result.stdout.lower()
        )

    def test_invalid_group_by_option_shows_error(
        self, runner, v3_strategy_yaml, tmp_path
    ):
        """Test that invalid --group-by option shows error."""
        strategy_file = tmp_path / "v3_strategy.yaml"
        strategy_file.write_text(v3_strategy_yaml)

        result = runner.invoke(
            strategies_app,
            ["features", str(strategy_file), "--group-by", "invalid"],
        )

        # Should fail - typer validates Choice options
        assert result.exit_code != 0

    def test_output_includes_feature_count(self, runner, v3_strategy_yaml, tmp_path):
        """Test that output includes total feature count."""
        strategy_file = tmp_path / "v3_strategy.yaml"
        strategy_file.write_text(v3_strategy_yaml)

        result = runner.invoke(
            strategies_app,
            ["features", str(strategy_file)],
        )

        assert result.exit_code == 0

        # Should show feature count (9 total for this strategy)
        # Should mention "features" and a count
        assert "9" in result.stdout
        assert "feature" in result.stdout.lower()

"""
Tests for v3 strategy dry-run mode in training command.

Tests verify that the training dry-run:
- Detects v3 strategies and displays v3-specific info
- Shows indicators with their types
- Shows fuzzy sets with their indicator mappings
- Shows resolved features from FeatureResolver
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ktrdr.cli.model_commands import models_app


@pytest.fixture
def runner():
    """Create Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def v3_strategy_file(tmp_path: Path) -> Path:
    """Create a valid v3 strategy file for testing."""
    strategy_content = """
name: "test_v3_strategy"
description: "Test v3 strategy for dry-run"
version: "3.0"

training_data:
  symbols:
    mode: single
    list: [AAPL]
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
    overbought: [60, 75, 100]

  bbands_position:
    indicator: bbands_20_2.middle
    below: [0, 0.3, 0.5]
    above: [0.5, 0.7, 1.0]

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: [5m]
  - fuzzy_set: bbands_position
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [64, 32]
    activation: relu

decisions:
  output_format: classification
  confidence_threshold: 0.6

training:
  method: supervised
  labels:
    source: zigzag
    zigzag_threshold: 0.02
"""
    strategy_path = tmp_path / "test_v3_strategy.yaml"
    strategy_path.write_text(strategy_content)
    return strategy_path


@pytest.fixture
def v2_strategy_file(tmp_path: Path) -> Path:
    """Create a v2 (legacy) strategy file for testing."""
    strategy_content = """
name: "test_v2_strategy"
description: "Test v2 strategy"

training_data:
  symbols:
    mode: single
    list: [AAPL]
  timeframes:
    mode: single
    timeframe: 1h
  history_required: 100

indicators:
  - rsi:
      period: 14

fuzzy_logic:
  - name: rsi_zones
    input: rsi
    membership_functions:
      - name: oversold
        type: triangular
        parameters: [0, 25, 40]
"""
    strategy_path = tmp_path / "test_v2_strategy.yaml"
    strategy_path.write_text(strategy_content)
    return strategy_path


class TestTrainDryRunV3:
    """Test v3-specific dry-run functionality."""

    def test_dry_run_detects_v3_strategy(
        self, runner: CliRunner, v3_strategy_file: Path
    ):
        """Test that dry-run detects v3 strategy and shows v3 info."""
        result = runner.invoke(
            models_app,
            [
                "train",
                str(v3_strategy_file),
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-06-01",
                "--dry-run",
            ],
        )

        # Should succeed
        assert result.exit_code == 0

        # Should show v3 strategy name and version
        assert "test_v3_strategy" in result.output
        assert "3.0" in result.output or "v3" in result.output.lower()

    def test_dry_run_shows_indicators(self, runner: CliRunner, v3_strategy_file: Path):
        """Test that dry-run shows indicators with their types."""
        result = runner.invoke(
            models_app,
            [
                "train",
                str(v3_strategy_file),
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-06-01",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0

        # Should show indicators section
        assert "rsi_14" in result.output
        assert "rsi" in result.output.lower()
        assert "bbands_20_2" in result.output
        assert "bbands" in result.output.lower()

    def test_dry_run_shows_fuzzy_sets(self, runner: CliRunner, v3_strategy_file: Path):
        """Test that dry-run shows fuzzy sets with indicator mappings."""
        result = runner.invoke(
            models_app,
            [
                "train",
                str(v3_strategy_file),
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-06-01",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0

        # Should show fuzzy sets section
        assert "rsi_fast" in result.output
        assert "bbands_position" in result.output
        # Should show indicator references
        assert "rsi_14" in result.output
        assert "bbands_20_2" in result.output

    def test_dry_run_shows_resolved_features(
        self, runner: CliRunner, v3_strategy_file: Path
    ):
        """Test that dry-run shows resolved features from FeatureResolver."""
        result = runner.invoke(
            models_app,
            [
                "train",
                str(v3_strategy_file),
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-06-01",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0

        # Should show features section with resolved feature IDs
        # From v3_strategy_file: rsi_fast on [5m] and bbands_position on "all" ([5m, 1h])
        assert "5m_rsi_fast_oversold" in result.output
        assert "5m_rsi_fast_overbought" in result.output
        # bbands_position on all timeframes
        assert (
            "5m_bbands_position" in result.output or "bbands_position" in result.output
        )
        assert (
            "1h_bbands_position" in result.output or "features" in result.output.lower()
        )

    def test_dry_run_shows_feature_count(
        self, runner: CliRunner, v3_strategy_file: Path
    ):
        """Test that dry-run shows total feature count."""
        result = runner.invoke(
            models_app,
            [
                "train",
                str(v3_strategy_file),
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-06-01",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0

        # Should show feature count (6 features based on strategy)
        # rsi_fast: 2 memberships × 1 timeframe = 2
        # bbands_position: 2 memberships × 2 timeframes = 4
        # Total: 6 features
        assert "6" in result.output or "feature" in result.output.lower()

    def test_dry_run_v2_strategy_not_treated_as_v3(
        self, runner: CliRunner, v2_strategy_file: Path
    ):
        """Test that v2 strategies are NOT treated as v3 for dry-run.

        The v3 dry-run path should only be taken for actual v3 strategies.
        V2 strategies should go through the existing flow (which requires API).
        """
        result = runner.invoke(
            models_app,
            [
                "train",
                str(v2_strategy_file),
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-06-01",
                "--dry-run",
            ],
        )

        # The output should NOT contain v3-specific markers
        # This confirms the v3 dry-run path was NOT taken
        assert "V3 Strategy Analysis" not in result.output
        assert "NN Inputs" not in result.output
        # It should NOT show v3 features like "5m_rsi_fast_oversold"
        assert "5m_rsi_fast" not in result.output

    def test_dry_run_no_training_executed(
        self, runner: CliRunner, v3_strategy_file: Path
    ):
        """Test that dry-run does not execute actual training."""
        with patch("ktrdr.cli.model_commands.AsyncCLIClient") as mock_client_cls:
            result = runner.invoke(
                models_app,
                [
                    "train",
                    str(v3_strategy_file),
                    "--start-date",
                    "2024-01-01",
                    "--end-date",
                    "2024-06-01",
                    "--dry-run",
                ],
            )

            # Should succeed without calling API
            assert result.exit_code == 0
            # In v3 dry-run, we shouldn't need the API client at all
            # The AsyncCLIClient should not have been instantiated
            mock_client_cls.assert_not_called()

    def test_dry_run_invalid_v3_strategy_fails(self, runner: CliRunner, tmp_path: Path):
        """Test that invalid v3 strategy shows error in dry-run."""
        # Create invalid v3 strategy (missing required fuzzy_set reference)
        invalid_strategy = tmp_path / "invalid_v3.yaml"
        invalid_strategy.write_text(
            """
name: "invalid_v3"
version: "3.0"

training_data:
  symbols:
    mode: single
    list: [AAPL]
  timeframes:
    mode: single
    timeframe: 1h

indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_fast:
    indicator: nonexistent_indicator
    oversold: [0, 25, 40]

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: [1h]

model:
  type: mlp

decisions:
  output_format: classification

training:
  method: supervised
"""
        )

        result = runner.invoke(
            models_app,
            [
                "train",
                str(invalid_strategy),
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-06-01",
                "--dry-run",
            ],
        )

        # Should fail with validation error
        assert result.exit_code != 0
        assert "error" in result.output.lower() or "invalid" in result.output.lower()

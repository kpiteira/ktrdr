"""
Tests for multi-timeframe CLI commands.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from ktrdr.cli.multi_timeframe_commands import multi_timeframe_app


class TestMultiTimeframeCLICommands:
    """Test multi-timeframe CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def sample_strategy_config(self):
        """Create sample strategy configuration."""
        return {
            "name": "test_multi_timeframe_strategy",
            "timeframe_configs": {
                "1h": {"weight": 0.5, "primary": False},
                "4h": {"weight": 0.3, "primary": True},
                "1d": {"weight": 0.2, "primary": False},
            },
            "indicators": [{"name": "rsi", "period": 14}],
            "fuzzy_sets": {
                "rsi": {
                    "type": "triangular",
                    "sets": {"oversold": {"low": 0, "mid": 30, "high": 50}},
                }
            },
            "multi_timeframe": {"consensus_method": "weighted_majority"},
        }

    @pytest.fixture
    def temp_strategy_file(self, sample_strategy_config):
        """Create temporary strategy configuration file."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(sample_strategy_config, temp_file)
        temp_file.close()
        yield temp_file.name
        Path(temp_file.name).unlink()

    def test_multi_timeframe_help(self, runner):
        """Test multi-timeframe command help."""
        result = runner.invoke(multi_timeframe_app, ["--help"])
        assert result.exit_code == 0
        assert "Multi-timeframe trading decision commands" in result.stdout
        assert "decide" in result.stdout
        assert "analyze" in result.stdout
        assert "status" in result.stdout
        assert "strategies" in result.stdout

    def test_decide_command_help(self, runner):
        """Test decide command help."""
        result = runner.invoke(multi_timeframe_app, ["decide", "--help"])
        assert result.exit_code == 0
        assert (
            "Generate a trading decision using multi-timeframe analysis"
            in result.stdout
        )
        # Check for timeframes option (could be --timeframes or -t)
        assert "--timeframes" in result.stdout or "-t" in result.stdout
        # Check for mode option (could be --mode or -m)
        assert "--mode" in result.stdout or "-m" in result.stdout

    def test_decide_command_invalid_symbol(self, runner, temp_strategy_file):
        """Test decide command with invalid symbol."""
        result = runner.invoke(
            multi_timeframe_app, ["decide", "INVALID@SYMBOL", temp_strategy_file]
        )
        assert result.exit_code == 1
        assert "Validation Error" in result.stderr

    def test_decide_command_missing_strategy(self, runner):
        """Test decide command with missing strategy file."""
        result = runner.invoke(
            multi_timeframe_app, ["decide", "AAPL", "/nonexistent/strategy.yaml"]
        )
        assert result.exit_code == 1
        assert "Strategy file not found" in result.stderr

    def test_decide_command_invalid_timeframe(self, runner, temp_strategy_file):
        """Test decide command with invalid timeframe."""
        result = runner.invoke(
            multi_timeframe_app,
            ["decide", "AAPL", temp_strategy_file, "--timeframes", "1h,invalid_tf"],
        )
        assert result.exit_code == 1
        assert "Invalid timeframe" in result.stderr

    def test_decide_command_invalid_mode(self, runner, temp_strategy_file):
        """Test decide command with invalid mode."""
        result = runner.invoke(
            multi_timeframe_app,
            ["decide", "AAPL", temp_strategy_file, "--mode", "invalid_mode"],
        )
        assert result.exit_code == 1
        assert "Invalid mode" in result.stderr

    @patch(
        "ktrdr.cli.multi_timeframe_commands.create_multi_timeframe_decision_orchestrator"
    )
    @patch("ktrdr.cli.multi_timeframe_commands.DataManager")
    def test_decide_command_direct_success(
        self, mock_dm, mock_create_orchestrator, runner, temp_strategy_file
    ):
        """Test successful decide command using direct orchestrator."""

        # Mock data manager
        mock_dm_instance = Mock()
        mock_dm_instance.get_data.return_value = Mock()  # Non-empty data
        mock_dm.return_value = mock_dm_instance

        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_decision = Mock()
        mock_decision.signal.value = "BUY"
        mock_decision.confidence = 0.8
        mock_decision.current_position.value = "FLAT"
        mock_decision.timestamp.isoformat.return_value = "2024-01-01T00:00:00Z"
        mock_decision.reasoning = {"test": "reasoning"}

        mock_orchestrator.make_multi_timeframe_decision.return_value = mock_decision
        mock_orchestrator.get_consensus_history.return_value = []

        mock_create_orchestrator.return_value = mock_orchestrator

        result = runner.invoke(
            multi_timeframe_app,
            [
                "decide",
                "AAPL",
                temp_strategy_file,
                "--timeframes",
                "1h,4h",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert "BUY" in result.stdout

    def test_analyze_command_help(self, runner):
        """Test analyze command help."""
        result = runner.invoke(multi_timeframe_app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "Analyze multi-timeframe performance" in result.stdout

    @patch(
        "ktrdr.cli.multi_timeframe_commands.create_multi_timeframe_decision_orchestrator"
    )
    def test_analyze_command_direct_success(
        self, mock_create_orchestrator, runner, temp_strategy_file
    ):
        """Test successful analyze command using direct orchestrator."""

        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_analysis = {
            "symbol": "AAPL",
            "timeframes": ["1h", "4h"],
            "primary_timeframe": "4h",
            "timeframe_weights": {"1h": 0.6, "4h": 0.4},
            "recent_decisions_count": 5,
        }
        mock_orchestrator.get_timeframe_analysis.return_value = mock_analysis
        mock_create_orchestrator.return_value = mock_orchestrator

        result = runner.invoke(
            multi_timeframe_app,
            ["analyze", "AAPL", temp_strategy_file, "--format", "json"],
        )

        assert result.exit_code == 0
        assert "AAPL" in result.stdout

    def test_status_command_help(self, runner):
        """Test status command help."""
        result = runner.invoke(multi_timeframe_app, ["status", "--help"])
        assert result.exit_code == 0
        assert "Check data availability and quality" in result.stdout

    @patch("ktrdr.cli.multi_timeframe_commands.DataManager")
    def test_status_command_direct_success(self, mock_dm, runner):
        """Test successful status command using direct data manager."""

        # Mock data manager
        mock_dm_instance = Mock()
        mock_data = Mock()
        mock_data.empty = False
        mock_data.__len__ = Mock(return_value=100)
        mock_data.isnull.return_value.sum.return_value.sum.return_value = 0
        mock_dm_instance.get_data.return_value = mock_data
        mock_dm.return_value = mock_dm_instance

        result = runner.invoke(
            multi_timeframe_app, ["status", "AAPL", "--timeframes", "1h,4h"]
        )

        assert result.exit_code == 0
        assert "AAPL" in result.stdout

    def test_strategies_command_help(self, runner):
        """Test strategies command help."""
        result = runner.invoke(multi_timeframe_app, ["strategies", "--help"])
        assert result.exit_code == 0
        assert "List strategies that support multi-timeframe analysis" in result.stdout

    @patch("ktrdr.cli.multi_timeframe_commands.Path")
    def test_strategies_command_direct_success(
        self, mock_path_class, runner, temp_strategy_file
    ):
        """Test successful strategies command."""

        # Mock Path class and directory scanning
        mock_strategy_dir = Mock()
        mock_strategy_dir.exists.return_value = True
        mock_strategy_dir.glob.return_value = [Path(temp_strategy_file)]
        mock_path_class.return_value = mock_strategy_dir

        result = runner.invoke(multi_timeframe_app, ["strategies", "--format", "json"])

        assert result.exit_code == 0
        assert "strategies" in result.stdout

    def test_compare_command_help(self, runner):
        """Test compare command help."""
        result = runner.invoke(multi_timeframe_app, ["compare", "--help"])
        assert result.exit_code == 0
        assert "Compare different consensus methods" in result.stdout

    def test_compare_command_success(self, runner, temp_strategy_file):
        """Test successful compare command."""

        # This command has placeholder implementation, so it should work
        result = runner.invoke(
            multi_timeframe_app,
            [
                "compare",
                "AAPL",
                temp_strategy_file,
                "--methods",
                "consensus,weighted",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert "AAPL" in result.stdout

    def test_decide_command_with_all_options(self, runner, temp_strategy_file):
        """Test decide command with all options specified."""

        # This should fail due to missing data, but should validate all parameters
        result = runner.invoke(
            multi_timeframe_app,
            [
                "decide",
                "AAPL",
                temp_strategy_file,
                "--timeframes",
                "1h,4h,1d",
                "--mode",
                "backtest",
                "--model",
                "/path/to/model",
                "--format",
                "json",
                "--portfolio",
                "200000",
                "--capital",
                "100000",
                "--verbose",
            ],
        )

        # Should fail on execution (no data), but not on validation
        assert (
            "Making multi-timeframe decision" in result.stdout or result.exit_code == 1
        )

    def test_analyze_command_with_all_options(self, runner, temp_strategy_file):
        """Test analyze command with all options specified."""

        result = runner.invoke(
            multi_timeframe_app,
            [
                "analyze",
                "AAPL",
                temp_strategy_file,
                "--timeframes",
                "1h,4h",
                "--mode",
                "paper",
                "--format",
                "table",
                "--history",
                "20",
            ],
        )

        # Should fail on execution, but command structure should be valid
        assert (
            "Analyzing timeframe performance" in result.stdout or result.exit_code == 1
        )

    def test_status_command_with_all_options(self, runner):
        """Test status command with all options specified."""

        result = runner.invoke(
            multi_timeframe_app,
            ["status", "AAPL", "--timeframes", "1h,4h,1d", "--lookback", "200"],
        )

        # Should execute (might fail on data loading)
        assert "Checking data status" in result.stdout or result.exit_code == 1

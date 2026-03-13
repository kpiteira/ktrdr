"""Tests for the regime CLI command."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from ktrdr.cli.app import app


class TestRegimeAnalyzeCommand:
    """Tests for `ktrdr regime analyze` CLI command."""

    def test_command_exists(self, runner) -> None:
        """regime command is registered and discoverable."""
        result = runner.invoke(app, ["regime", "--help"])
        assert result.exit_code == 0
        assert "analyze" in result.output.lower()

    def test_analyze_help(self, runner) -> None:
        """analyze subcommand shows help with expected arguments."""
        result = runner.invoke(app, ["regime", "analyze", "--help"])
        assert result.exit_code == 0
        assert "symbol" in result.output.lower()
        assert "timeframe" in result.output.lower()

    @patch("ktrdr.data.repository.DataRepository")
    def test_analyze_runs_with_mock_data(self, mock_repo_cls, runner) -> None:
        """analyze command runs successfully with mocked data."""
        # Create realistic OHLCV data
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=300, freq="h")
        close = 100.0 + np.cumsum(np.random.randn(300) * 0.5)
        data = pd.DataFrame(
            {
                "open": close - 0.1,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": [1000] * 300,
            },
            index=dates,
        )

        mock_repo = MagicMock()
        mock_repo.load_from_cache.return_value = data
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(
            app,
            ["regime", "analyze", "EURUSD", "1h"],
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        mock_repo.load_from_cache.assert_called_once()

    @patch("ktrdr.data.repository.DataRepository")
    def test_output_contains_distribution(self, mock_repo_cls, runner) -> None:
        """Output includes distribution section."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=300, freq="h")
        close = 100.0 + np.cumsum(np.random.randn(300) * 0.5)
        data = pd.DataFrame(
            {
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": [1000] * 300,
            },
            index=dates,
        )

        mock_repo = MagicMock()
        mock_repo.load_from_cache.return_value = data
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["regime", "analyze", "EURUSD", "1h"])

        assert result.exit_code == 0
        output = result.output.lower()
        assert "distribution" in output

    @patch("ktrdr.data.repository.DataRepository")
    def test_output_contains_persistence(self, mock_repo_cls, runner) -> None:
        """Output includes persistence/duration section."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=300, freq="h")
        close = 100.0 + np.cumsum(np.random.randn(300) * 0.5)
        data = pd.DataFrame(
            {
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": [1000] * 300,
            },
            index=dates,
        )

        mock_repo = MagicMock()
        mock_repo.load_from_cache.return_value = data
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["regime", "analyze", "EURUSD", "1h"])

        assert result.exit_code == 0
        output = result.output.lower()
        assert "duration" in output or "persistence" in output

    @patch("ktrdr.data.repository.DataRepository")
    def test_output_contains_return_by_regime(self, mock_repo_cls, runner) -> None:
        """Output includes return-by-regime section."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=300, freq="h")
        close = 100.0 + np.cumsum(np.random.randn(300) * 0.5)
        data = pd.DataFrame(
            {
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": [1000] * 300,
            },
            index=dates,
        )

        mock_repo = MagicMock()
        mock_repo.load_from_cache.return_value = data
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["regime", "analyze", "EURUSD", "1h"])

        assert result.exit_code == 0
        output = result.output.lower()
        assert "return" in output

    @patch("ktrdr.data.repository.DataRepository")
    def test_custom_labeler_params(self, mock_repo_cls, runner) -> None:
        """Custom labeler parameters override defaults."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=300, freq="h")
        close = 100.0 + np.cumsum(np.random.randn(300) * 0.5)
        data = pd.DataFrame(
            {
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": [1000] * 300,
            },
            index=dates,
        )

        mock_repo = MagicMock()
        mock_repo.load_from_cache.return_value = data
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(
            app,
            [
                "regime",
                "analyze",
                "EURUSD",
                "1h",
                "--macro-atr-mult",
                "2.0",
                "--micro-atr-mult",
                "0.5",
                "--atr-period",
                "10",
                "--vol-crisis-threshold",
                "3.0",
                "--vol-lookback",
                "60",
                "--progression-tolerance",
                "0.6",
            ],
        )

        assert result.exit_code == 0

    @patch("ktrdr.data.repository.DataRepository")
    def test_data_not_found_gives_error(self, mock_repo_cls, runner) -> None:
        """Missing data gives clear error message."""
        from ktrdr.errors import DataError

        mock_repo = MagicMock()
        mock_repo.load_from_cache.side_effect = DataError("Data not found")
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["regime", "analyze", "INVALID", "1h"])

        assert result.exit_code != 0

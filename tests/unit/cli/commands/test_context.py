"""Tests for `ktrdr context analyze` CLI command."""

import sys
import types
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Pre-register ktrdr.training as a package stub if torch isn't available.
# This allows importing ktrdr.training.context_labeler without triggering
# ktrdr.training.__init__.py which imports torch via model_trainer.
_torch_available = True
try:
    import torch  # noqa: F401
except ImportError:
    _torch_available = False
    if "ktrdr.training" not in sys.modules:
        _stub = types.ModuleType("ktrdr.training")
        _stub.__path__ = [str(types)]  # type: ignore[attr-defined]
        sys.modules["ktrdr.training"] = _stub
    # Now import the actual context_labeler submodule (it only needs pandas)
    import importlib.util

    _spec = importlib.util.spec_from_file_location(
        "ktrdr.training.context_labeler",
        "ktrdr/training/context_labeler.py",
    )
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["ktrdr.training.context_labeler"] = _mod
        _spec.loader.exec_module(_mod)

from ktrdr.cli.app import app  # noqa: E402

# Label constants
BULLISH = 0
BEARISH = 1
NEUTRAL = 2


@pytest.fixture
def mock_daily_data() -> pd.DataFrame:
    """Mock daily OHLCV data."""
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    return pd.DataFrame(
        {
            "open": [100.0] * 30,
            "high": [105.0] * 30,
            "low": [95.0] * 30,
            "close": [100.0 + i * 0.5 for i in range(30)],
            "volume": [1000] * 30,
        },
        index=dates,
    )


def _make_mock_stats(
    hourly_returns: dict[int, float] | None = None,
    regime_corr: float | None = None,
) -> MagicMock:
    """Create a mock ContextLabelStats (avoids torch import)."""
    stats = MagicMock()
    stats.distribution = {BULLISH: 0.35, BEARISH: 0.36, NEUTRAL: 0.29}
    stats.mean_duration_days = {BULLISH: 8.3, BEARISH: 7.9, NEUTRAL: 4.1}
    stats.mean_hourly_return_by_context = hourly_returns
    stats.regime_correlation = regime_corr
    return stats


def _setup_mocks(mock_daily_data, mock_stats):
    """Create standard mock repo + labeler for analyze tests."""
    mock_repo = MagicMock()
    mock_repo.load_from_cache.return_value = mock_daily_data

    mock_labeler = MagicMock()
    mock_labeler.label.return_value = pd.Series(
        [0.0] * 25 + [float("nan")] * 5,
        index=mock_daily_data.index,
    )
    mock_labeler.analyze_labels.return_value = mock_stats
    mock_labeler_cls = MagicMock(return_value=mock_labeler)

    return mock_repo, mock_labeler_cls


class TestContextAnalyzeCommand:
    """Tests for ktrdr context analyze."""

    def test_context_help_discoverable(self, runner) -> None:
        """ktrdr context --help should show the analyze subcommand."""
        result = runner.invoke(app, ["context", "--help"])
        assert result.exit_code == 0
        assert "analyze" in result.output.lower()

    def test_analyze_prints_distribution(
        self, runner, mock_daily_data: pd.DataFrame
    ) -> None:
        """Output should include distribution percentages."""
        mock_repo, mock_labeler_cls = _setup_mocks(mock_daily_data, _make_mock_stats())

        with (
            patch("ktrdr.data.repository.DataRepository", return_value=mock_repo),
            patch("ktrdr.training.context_labeler.ContextLabeler", mock_labeler_cls),
        ):
            result = runner.invoke(
                app,
                [
                    "context",
                    "analyze",
                    "EURUSD",
                    "1d",
                    "--start-date",
                    "2024-01-01",
                    "--end-date",
                    "2024-12-31",
                ],
            )
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
        assert "distribution" in result.output.lower()
        assert "35" in result.output  # 35% bullish

    def test_analyze_prints_persistence(
        self, runner, mock_daily_data: pd.DataFrame
    ) -> None:
        """Output should include persistence/duration metrics."""
        mock_repo, mock_labeler_cls = _setup_mocks(mock_daily_data, _make_mock_stats())

        with (
            patch("ktrdr.data.repository.DataRepository", return_value=mock_repo),
            patch("ktrdr.training.context_labeler.ContextLabeler", mock_labeler_cls),
        ):
            result = runner.invoke(
                app,
                [
                    "context",
                    "analyze",
                    "EURUSD",
                    "1d",
                    "--start-date",
                    "2024-01-01",
                    "--end-date",
                    "2024-12-31",
                ],
            )
        assert result.exit_code == 0
        assert "Persistence" in result.output or "Duration" in result.output
        assert "8.3" in result.output

    def test_analyze_with_hourly_timeframe(
        self, runner, mock_daily_data: pd.DataFrame
    ) -> None:
        """--hourly-timeframe flag should trigger hourly return computation."""
        stats = _make_mock_stats(
            hourly_returns={BULLISH: 0.0012, BEARISH: -0.0010, NEUTRAL: -0.0001},
        )
        mock_repo, mock_labeler_cls = _setup_mocks(mock_daily_data, stats)

        with (
            patch("ktrdr.data.repository.DataRepository", return_value=mock_repo),
            patch("ktrdr.training.context_labeler.ContextLabeler", mock_labeler_cls),
        ):
            result = runner.invoke(
                app,
                [
                    "context",
                    "analyze",
                    "EURUSD",
                    "1d",
                    "--start-date",
                    "2024-01-01",
                    "--end-date",
                    "2024-12-31",
                    "--hourly-timeframe",
                    "1h",
                ],
            )
        assert result.exit_code == 0
        assert mock_repo.load_from_cache.call_count == 2
        assert "Return" in result.output or "return" in result.output.lower()

    def test_analyze_no_cached_data_errors(self, runner) -> None:
        """Missing cached data should show a clear error."""
        mock_repo = MagicMock()
        mock_repo.load_from_cache.side_effect = Exception("No cached data")

        with patch("ktrdr.data.repository.DataRepository", return_value=mock_repo):
            result = runner.invoke(
                app,
                ["context", "analyze", "EURUSD", "1d"],
            )
        assert result.exit_code != 0 or "error" in result.output.lower()

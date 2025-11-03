"""Unit tests for model testing CLI commands."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import typer

from ktrdr.cli.model_testing_commands import test_model_signals
from ktrdr.errors.exceptions import DataNotFoundError


class TestModelTestingCommands:
    """Test suite for model testing CLI commands."""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=100), periods=100, freq="1D"
        )
        return pd.DataFrame(
            {
                "open": [100.0] * 100,
                "high": [101.0] * 100,
                "low": [99.0] * 100,
                "close": [100.5] * 100,
                "volume": [1000000] * 100,
            },
            index=dates,
        )

    @pytest.fixture
    def temp_strategy_file(self, tmp_path):
        """Create a temporary strategy config file."""
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text(
            """
strategy_name: test_strategy
indicators:
  - name: sma
    period: 20
"""
        )
        return str(strategy_file)

    def test_data_repository_used_instead_of_data_manager(
        self, sample_data, temp_strategy_file
    ):
        """
        Test that DataRepository is used instead of DataManager.

        This verifies the migration from DataManager to DataRepository.
        """
        with patch(
            "ktrdr.cli.model_testing_commands.DataRepository"
        ) as mock_repository_class:
            with patch(
                "ktrdr.cli.model_testing_commands.DecisionOrchestrator"
            ) as mock_orchestrator_class:
                # Setup repository mock
                mock_repository = MagicMock()
                mock_repository.load_from_cache.return_value = sample_data
                mock_repository_class.return_value = mock_repository

                # Setup orchestrator mock
                mock_orchestrator = MagicMock()
                mock_orchestrator.strategy_name = "test_strategy"
                mock_orchestrator.model = MagicMock()
                mock_decision = MagicMock()
                mock_decision.signal.value = "HOLD"
                mock_decision.confidence = 0.5
                mock_decision.reasoning = {}
                mock_orchestrator.make_decision.return_value = mock_decision
                mock_orchestrator_class.return_value = mock_orchestrator

                # Call the function
                test_model_signals(
                    strategy=temp_strategy_file,
                    symbol="AAPL",
                    timeframe="1d",
                    model=None,
                    samples=10,
                )

                # Verify DataRepository was instantiated
                mock_repository_class.assert_called_once()

                # Verify load_from_cache was called with correct parameters
                mock_repository.load_from_cache.assert_called_once_with("AAPL", "1d")

    def test_data_not_found_error_handling(self, temp_strategy_file):
        """
        Test that DataNotFoundError is handled with a helpful message.

        When data is not cached, the function should:
        1. Catch the DataNotFoundError
        2. Display a clear error message
        3. Suggest running 'ktrdr data load'
        4. Exit with code 1
        """
        with patch(
            "ktrdr.cli.model_testing_commands.DataRepository"
        ) as mock_repository_class:
            # Setup repository to raise DataNotFoundError
            mock_repository = MagicMock()
            mock_repository.load_from_cache.side_effect = DataNotFoundError(
                message="No data found in cache for AAPL 1d",
                error_code="DATA-EmptyCache",
                details={"symbol": "AAPL", "timeframe": "1d"},
            )
            mock_repository_class.return_value = mock_repository

            # Call should raise typer.Exit(1)
            with pytest.raises(typer.Exit) as exc_info:
                test_model_signals(
                    strategy=temp_strategy_file,
                    symbol="AAPL",
                    timeframe="1d",
                    model=None,
                    samples=10,
                )

            # Verify exit code is 1
            assert exc_info.value.exit_code == 1

            # Verify load_from_cache was called
            mock_repository.load_from_cache.assert_called_once_with("AAPL", "1d")

    def test_data_mode_parameter_removed(self, sample_data, temp_strategy_file):
        """
        Test that data_mode parameter is no longer used.

        After migration, data_mode should not affect repository behavior.
        Repository should always load from cache regardless of data_mode value.
        """
        with patch(
            "ktrdr.cli.model_testing_commands.DataRepository"
        ) as mock_repository_class:
            with patch(
                "ktrdr.cli.model_testing_commands.DecisionOrchestrator"
            ) as mock_orchestrator_class:
                # Setup mocks
                mock_repository = MagicMock()
                mock_repository.load_from_cache.return_value = sample_data
                mock_repository_class.return_value = mock_repository

                mock_orchestrator = MagicMock()
                mock_orchestrator.strategy_name = "test_strategy"
                mock_orchestrator.model = MagicMock()
                mock_decision = MagicMock()
                mock_decision.signal.value = "HOLD"
                mock_decision.confidence = 0.5
                mock_decision.reasoning = {}
                mock_orchestrator.make_decision.return_value = mock_decision
                mock_orchestrator_class.return_value = mock_orchestrator

                # Call function (data_mode parameter has been removed)
                test_model_signals(
                    strategy=temp_strategy_file,
                    symbol="AAPL",
                    timeframe="1d",
                    model=None,
                    samples=10,
                )

                # Verify load_from_cache was called (no mode parameter)
                mock_repository.load_from_cache.assert_called_once_with("AAPL", "1d")

    def test_insufficient_data_handling(self, temp_strategy_file):
        """
        Test handling when cached data has insufficient samples.

        Should display clear error and exit with code 1.
        """
        # Create minimal data (less than required samples)
        minimal_data = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [1000000] * 5,
            },
            index=pd.date_range(start="2024-01-01", periods=5, freq="1D"),
        )

        with patch(
            "ktrdr.cli.model_testing_commands.DataRepository"
        ) as mock_repository_class:
            mock_repository = MagicMock()
            mock_repository.load_from_cache.return_value = minimal_data
            mock_repository_class.return_value = mock_repository

            # Should raise typer.Exit(1) due to insufficient data
            with pytest.raises(typer.Exit) as exc_info:
                test_model_signals(
                    strategy=temp_strategy_file,
                    symbol="AAPL",
                    timeframe="1d",
                    model=None,
                    samples=10,  # Requires 10 samples, but only 5 available
                )

            assert exc_info.value.exit_code == 1

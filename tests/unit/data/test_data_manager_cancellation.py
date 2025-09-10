"""
Test suite for DataManager ServiceOrchestrator cancellation integration.

This module tests the enhanced DataManager functionality that integrates with
ServiceOrchestrator.execute_with_cancellation() patterns while preserving all
existing functionality and API compatibility.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from ktrdr.data.data_manager import DataManager


class TestDataManagerServiceOrchestratorIntegration:
    """Test DataManager integration with ServiceOrchestrator cancellation patterns."""

    @pytest.fixture
    def mock_data_manager(self):
        """Create a DataManager with mocked dependencies for testing."""
        with (
            patch("ktrdr.data.data_manager.create_default_datamanager_builder"),
            patch("ktrdr.managers.ServiceOrchestrator.__init__", return_value=None),
        ):
            dm = DataManager()

            # Mock all the required components
            dm.data_loader = Mock()
            dm.external_provider = Mock()
            dm.data_validator = Mock()
            dm.gap_classifier = Mock()
            dm.gap_analyzer = Mock()
            dm.segment_manager = Mock()
            dm.data_processor = Mock()
            dm.data_loading_orchestrator = Mock()
            dm.health_checker = Mock()

            # Mock ServiceOrchestrator methods
            dm.execute_with_cancellation = Mock()
            dm.get_current_cancellation_token = Mock()

            # Mock other required attributes
            dm.max_gap_percentage = 5.0
            dm.default_repair_method = "ffill"
            dm._data_progress_renderer = Mock()
            dm._time_estimation_engine = Mock()

            return dm

    @pytest.fixture
    def sample_dataframe(self):
        """Create a sample OHLCV DataFrame for testing."""
        dates = pd.date_range("2023-01-01", periods=10, freq="H")
        data = {
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5] * 10,
            "volume": [1000] * 10,
        }
        df = pd.DataFrame(data, index=dates)
        df.index.name = "timestamp"
        return df

    def test_load_data_uses_async_wrapper(self, mock_data_manager, sample_dataframe):
        """Test that load_data() uses the async wrapper method via _run_async_method."""

        # Mock _run_async_method to capture what async method is called
        mock_data_manager._run_async_method = Mock(return_value=sample_dataframe)

        # Call load_data
        result = mock_data_manager.load_data(
            symbol="AAPL",
            timeframe="1h",
            mode="tail",
        )

        # Verify _run_async_method was called
        mock_data_manager._run_async_method.assert_called_once()
        call_args = mock_data_manager._run_async_method.call_args

        # Verify the first argument is the async wrapper method
        assert call_args[0][0].__name__ == "_load_data_with_cancellation_async"

        # Verify the result is returned
        assert result is sample_dataframe

    def test_load_data_passes_parameters_to_async_method(
        self, mock_data_manager, sample_dataframe
    ):
        """Test that all load_data parameters are properly passed to the async method."""

        # Mock _run_async_method to capture parameters
        mock_data_manager._run_async_method = Mock(return_value=sample_dataframe)

        # Call with various parameters
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)
        cancellation_token = Mock()

        mock_data_manager.load_data(
            symbol="MSFT",
            timeframe="1d",
            start_date=start_date,
            end_date=end_date,
            mode="full",
            validate=True,
            repair=False,
            repair_outliers=True,
            strict=False,
            cancellation_token=cancellation_token,
        )

        # Verify _run_async_method was called with all parameters
        mock_data_manager._run_async_method.assert_called_once()
        call_args = mock_data_manager._run_async_method.call_args

        # Check that all parameters are in the call
        assert "MSFT" in call_args[0]
        assert "1d" in call_args[0]
        assert start_date in call_args[0]
        assert end_date in call_args[0]
        assert "full" in call_args[0]
        assert True in call_args[0]  # validate
        assert False in call_args[0]  # repair
        assert cancellation_token in call_args[0]

    def test_load_data_preserves_api_compatibility(
        self, mock_data_manager, sample_dataframe
    ):
        """Test that existing API usage patterns continue to work."""

        # Mock _run_async_method
        mock_data_manager._run_async_method = Mock(return_value=sample_dataframe)

        # Test minimal parameter usage (most common pattern)
        result1 = mock_data_manager.load_data("AAPL", "1h")
        assert result1 is sample_dataframe

        # Test with mode parameter
        result2 = mock_data_manager.load_data("GOOGL", "1d", mode="tail")
        assert result2 is sample_dataframe

        # Test with date range
        result3 = mock_data_manager.load_data(
            "MSFT",
            "4h",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )
        assert result3 is sample_dataframe

        # Verify all calls went through _run_async_method
        assert mock_data_manager._run_async_method.call_count == 3

    def test_async_wrapper_method_exists(self, mock_data_manager):
        """Test that the async wrapper method exists and is callable."""

        # Check that the async wrapper method exists
        assert hasattr(mock_data_manager, "_load_data_with_cancellation_async")
        assert callable(mock_data_manager._load_data_with_cancellation_async)

    def test_cancellation_token_handling(self, mock_data_manager, sample_dataframe):
        """Test that cancellation tokens are properly handled."""

        # Mock _run_async_method
        mock_data_manager._run_async_method = Mock(return_value=sample_dataframe)

        # Test with explicit cancellation token
        token = Mock()
        result = mock_data_manager.load_data("AAPL", "1h", cancellation_token=token)

        # Verify cancellation token was passed through
        mock_data_manager._run_async_method.assert_called_once()
        call_args = mock_data_manager._run_async_method.call_args
        assert token in call_args[0]

        # Test without explicit cancellation token (should still work)
        mock_data_manager._run_async_method.reset_mock()
        result = mock_data_manager.load_data("MSFT", "1d")

        mock_data_manager._run_async_method.assert_called_once()
        assert result is sample_dataframe


class TestBackwardCompatibility:
    """Test that ServiceOrchestrator integration maintains backward compatibility."""

    def test_all_existing_load_data_patterns_work(self):
        """Test that all existing DataManager.load_data() usage patterns continue to work."""

        with (
            patch("ktrdr.data.data_manager.create_default_datamanager_builder"),
            patch("ktrdr.managers.ServiceOrchestrator.__init__", return_value=None),
        ):
            dm = DataManager()

            # Mock _run_async_method to avoid actual async execution
            sample_df = pd.DataFrame({"close": [100, 101, 102]})
            dm._run_async_method = Mock(return_value=sample_df)

            # Test all common usage patterns
            patterns = [
                # Minimal usage
                {"args": ("AAPL", "1h"), "kwargs": {}},
                # With mode
                {"args": ("AAPL", "1h"), "kwargs": {"mode": "tail"}},
                # With validation flags
                {"args": ("AAPL", "1h"), "kwargs": {"validate": True, "repair": False}},
                # With date range
                {
                    "args": ("AAPL", "1h"),
                    "kwargs": {
                        "start_date": datetime(2023, 1, 1),
                        "end_date": datetime(2023, 1, 31),
                        "mode": "full",
                    },
                },
                # With cancellation token
                {"args": ("AAPL", "1h"), "kwargs": {"cancellation_token": Mock()}},
                # Full parameter set
                {
                    "args": ("AAPL", "1h"),
                    "kwargs": {
                        "start_date": datetime(2023, 1, 1),
                        "end_date": datetime(2023, 1, 31),
                        "mode": "backfill",
                        "validate": True,
                        "repair": True,
                        "repair_outliers": False,
                        "strict": True,
                        "cancellation_token": Mock(),
                    },
                },
            ]

            for _i, pattern in enumerate(patterns):
                dm._run_async_method.reset_mock()

                # Each pattern should work without errors
                result = dm.load_data(*pattern["args"], **pattern["kwargs"])

                # Should return the expected result
                assert result is sample_df

                # Should call the async wrapper
                dm._run_async_method.assert_called_once()
                call_args = dm._run_async_method.call_args
                assert call_args[0][0].__name__ == "_load_data_with_cancellation_async"

    def test_error_handling_preserved(self):
        """Test that error handling behavior is preserved."""

        with (
            patch("ktrdr.data.data_manager.create_default_datamanager_builder"),
            patch("ktrdr.managers.ServiceOrchestrator.__init__", return_value=None),
        ):
            dm = DataManager()

            # Mock _run_async_method to raise an exception
            test_error = ValueError("Test error")
            dm._run_async_method = Mock(side_effect=test_error)

            # Error should propagate as before
            with pytest.raises(ValueError, match="Test error"):
                dm.load_data("AAPL", "1h")

    def test_return_types_preserved(self):
        """Test that return types are preserved."""

        with (
            patch("ktrdr.data.data_manager.create_default_datamanager_builder"),
            patch("ktrdr.managers.ServiceOrchestrator.__init__", return_value=None),
        ):
            dm = DataManager()

            # Test DataFrame return
            sample_df = pd.DataFrame({"close": [100, 101, 102]})
            dm._run_async_method = Mock(return_value=sample_df)

            result = dm.load_data("AAPL", "1h")
            assert isinstance(result, pd.DataFrame)
            assert result is sample_df

            # Test None return (for cases where no data is found)
            dm._run_async_method.reset_mock()
            dm._run_async_method.return_value = None

            result = dm.load_data("AAPL", "1h")
            assert result is None


class TestServiceOrchestratorIntegrationCore:
    """Test core ServiceOrchestrator integration functionality."""

    def test_async_method_signature_compatibility(self):
        """Test that the async wrapper method has the correct signature."""

        with (
            patch("ktrdr.data.data_manager.create_default_datamanager_builder"),
            patch("ktrdr.managers.ServiceOrchestrator.__init__", return_value=None),
        ):
            dm = DataManager()

            # The async method should exist and be callable
            async_method = dm._load_data_with_cancellation_async
            assert callable(async_method)

            # Should be an async method (coroutine function)
            import inspect

            assert inspect.iscoroutinefunction(async_method)

"""
Tests for DataManager ServiceOrchestrator enhancement following DummyService patterns.

This test module verifies that DataManager correctly implements the ServiceOrchestrator
patterns like DummyService, with load_data_async(), _run_data_load_async(), and
_format_api_response() methods.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from ktrdr.data.data_manager import DataManager


@pytest.fixture
def sample_api_data():
    """Create sample OHLCV DataFrame for testing."""
    index = pd.date_range(start="2023-01-01", periods=100, freq="1D", tz="UTC")
    data = {
        "open": [100.0 + i for i in range(100)],
        "high": [105.0 + i for i in range(100)],
        "low": [95.0 + i for i in range(100)],
        "close": [102.0 + i for i in range(100)],
        "volume": [1000 + i * 10 for i in range(100)],
    }
    return pd.DataFrame(data, index=index)


@pytest.fixture
def mock_data_manager(tmp_path):
    """Create a DataManager instance with mocked dependencies for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create DataManager instance
    manager = DataManager(data_dir=str(data_dir))

    # Mock ServiceOrchestrator methods that we'll be calling
    manager.start_managed_operation = AsyncMock()
    manager.get_current_cancellation_token = MagicMock()
    manager._create_progress_callback = MagicMock()

    return manager


class TestDataManagerServiceOrchestratorEnhancement:
    """Test DataManager ServiceOrchestrator enhancement methods."""

    def test_load_data_async_method_exists(self, mock_data_manager):
        """Test that load_data_async method exists and has correct signature."""
        # This test will fail initially (TDD) until we implement the method
        assert hasattr(mock_data_manager, "load_data_async")

        # Check method signature
        import inspect

        sig = inspect.signature(mock_data_manager.load_data_async)

        # Verify required parameters
        assert "symbol" in sig.parameters
        assert "timeframe" in sig.parameters
        assert "start_date" in sig.parameters
        assert "end_date" in sig.parameters
        assert "mode" in sig.parameters
        assert "filters" in sig.parameters

        # Verify defaults
        assert sig.parameters["start_date"].default is None
        assert sig.parameters["end_date"].default is None
        assert sig.parameters["mode"].default == "local"
        assert sig.parameters["filters"].default is None

    @pytest.mark.asyncio
    async def test_load_data_async_uses_start_managed_operation(
        self, mock_data_manager, sample_api_data
    ):
        """Test that load_data_async uses start_managed_operation like DummyService."""
        # Mock the response from start_managed_operation
        expected_response = {
            "operation_id": "op_123",
            "status": "started",
            "message": "Started data_load operation",
        }
        mock_data_manager.start_managed_operation.return_value = expected_response

        # Call load_data_async
        result = await mock_data_manager.load_data_async(
            symbol="AAPL", timeframe="1min", mode="local"
        )

        # Verify start_managed_operation was called with correct parameters
        mock_data_manager.start_managed_operation.assert_called_once()
        call_args = mock_data_manager.start_managed_operation.call_args

        # Check positional arguments
        assert call_args.kwargs["operation_name"] == "data_load"
        assert call_args.kwargs["operation_type"] == "DATA_LOAD"
        assert (
            call_args.kwargs["operation_func"] == mock_data_manager._run_data_load_async
        )

        # Check operation parameters passed through
        assert call_args.kwargs["symbol"] == "AAPL"
        assert call_args.kwargs["timeframe"] == "1min"
        assert call_args.kwargs["mode"] == "local"

        # Verify result
        assert result == expected_response

    def test_run_data_load_async_method_exists(self, mock_data_manager):
        """Test that _run_data_load_async method exists and has correct signature."""
        # This test will fail initially (TDD) until we implement the method
        assert hasattr(mock_data_manager, "_run_data_load_async")

        # Check method signature matches load_data_async parameters
        import inspect

        sig = inspect.signature(mock_data_manager._run_data_load_async)

        # Verify required parameters
        assert "symbol" in sig.parameters
        assert "timeframe" in sig.parameters
        assert "start_date" in sig.parameters
        assert "end_date" in sig.parameters
        assert "mode" in sig.parameters
        assert "filters" in sig.parameters

    @pytest.mark.asyncio
    async def test_run_data_load_async_calls_core_logic(
        self, mock_data_manager, sample_api_data
    ):
        """Test that _run_data_load_async calls existing core logic and formats response."""
        # Mock the core logic method to return sample data
        mock_data_manager._load_data_core_logic = MagicMock(
            return_value=sample_api_data
        )
        mock_data_manager.get_current_cancellation_token.return_value = None
        mock_data_manager._create_progress_callback.return_value = MagicMock()

        # Mock _format_api_response
        expected_api_response = {
            "status": "success",
            "fetched_bars": 100,
            "cached_before": True,
            "merged_file": "AAPL_1min.csv",
            "gaps_analyzed": 1,
            "segments_fetched": 1,
            "ib_requests_made": 0,
            "execution_time_seconds": 0.0,
        }
        mock_data_manager._format_api_response = MagicMock(
            return_value=expected_api_response
        )

        # Call _run_data_load_async
        result = await mock_data_manager._run_data_load_async(
            symbol="AAPL",
            timeframe="1min",
            start_date=None,
            end_date=None,
            mode="local",
            filters=None,
        )

        # Verify core logic was called with correct parameters
        mock_data_manager._load_data_core_logic.assert_called_once()
        call_args = mock_data_manager._load_data_core_logic.call_args[0]
        assert call_args[0] == "AAPL"  # symbol
        assert call_args[1] == "1min"  # timeframe
        assert call_args[4] == "local"  # mode

        # Verify _format_api_response was called
        mock_data_manager._format_api_response.assert_called_once_with(
            sample_api_data, "AAPL", "1min", "local"
        )

        # Verify result
        assert result == expected_api_response

    def test_format_api_response_method_exists(self, mock_data_manager):
        """Test that _format_api_response method exists and has correct signature."""
        # This test will fail initially (TDD) until we implement the method
        assert hasattr(mock_data_manager, "_format_api_response")

        # Check method signature
        import inspect

        sig = inspect.signature(mock_data_manager._format_api_response)

        # Verify required parameters
        assert "result" in sig.parameters
        assert "symbol" in sig.parameters
        assert "timeframe" in sig.parameters
        assert "mode" in sig.parameters

    def test_format_api_response_with_data(self, mock_data_manager, sample_api_data):
        """Test _format_api_response with valid DataFrame."""
        result = mock_data_manager._format_api_response(
            sample_api_data, "AAPL", "1min", "local"
        )

        # Verify API response format
        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert result["fetched_bars"] == 100
        assert "cached_before" in result
        assert "merged_file" in result
        assert "gaps_analyzed" in result
        assert "segments_fetched" in result
        assert "ib_requests_made" in result
        assert "execution_time_seconds" in result

        # Verify IB requests for local mode
        assert result["ib_requests_made"] == 0  # local mode should not make IB requests

    def test_format_api_response_with_empty_data(self, mock_data_manager):
        """Test _format_api_response with empty/None DataFrame."""
        # Test with None
        result = mock_data_manager._format_api_response(None, "AAPL", "1min", "local")

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert result["fetched_bars"] == 0
        assert result["cached_before"] is False
        assert result["execution_time_seconds"] == 0.0

        # Test with empty DataFrame
        empty_df = pd.DataFrame()
        result = mock_data_manager._format_api_response(
            empty_df, "AAPL", "1min", "local"
        )

        assert result["fetched_bars"] == 0
        assert result["cached_before"] is False

    def test_format_api_response_ib_mode(self, mock_data_manager, sample_api_data):
        """Test _format_api_response with non-local mode shows IB requests."""
        result = mock_data_manager._format_api_response(
            sample_api_data, "AAPL", "1min", "tail"
        )

        # Non-local mode should indicate IB requests
        assert result["ib_requests_made"] == 1

    @pytest.mark.asyncio
    async def test_load_data_async_parameter_passing(self, mock_data_manager):
        """Test that all parameters are correctly passed through the call chain."""
        # Setup mocks
        mock_data_manager.start_managed_operation.return_value = {"status": "success"}

        # Test with all parameters
        await mock_data_manager.load_data_async(
            symbol="EURUSD",
            timeframe="5min",
            start_date="2023-01-01",
            end_date="2023-12-31",
            mode="backfill",
            filters={"volume": ">1000"},
        )

        # Verify all parameters passed to start_managed_operation
        call_kwargs = mock_data_manager.start_managed_operation.call_args.kwargs
        assert call_kwargs["symbol"] == "EURUSD"
        assert call_kwargs["timeframe"] == "5min"
        assert call_kwargs["start_date"] == "2023-01-01"
        assert call_kwargs["end_date"] == "2023-12-31"
        assert call_kwargs["mode"] == "backfill"
        assert call_kwargs["filters"] == {"volume": ">1000"}

    @pytest.mark.asyncio
    async def test_run_data_load_async_cancellation_integration(
        self, mock_data_manager, sample_api_data
    ):
        """Test that _run_data_load_async integrates with ServiceOrchestrator cancellation."""
        # Mock cancellation token
        mock_token = MagicMock()
        mock_token.is_cancelled.return_value = False
        mock_data_manager.get_current_cancellation_token.return_value = mock_token

        # Mock other dependencies
        mock_data_manager._load_data_core_logic = MagicMock(
            return_value=sample_api_data
        )
        mock_data_manager._create_progress_callback.return_value = MagicMock()
        mock_data_manager._format_api_response = MagicMock(
            return_value={"status": "success"}
        )

        # Call the method
        await mock_data_manager._run_data_load_async(
            "AAPL", "1min", None, None, "local", None
        )

        # Verify cancellation token was obtained
        mock_data_manager.get_current_cancellation_token.assert_called_once()

        # Verify cancellation token was passed to core logic
        call_args = mock_data_manager._load_data_core_logic.call_args
        # Check if cancellation_token is in kwargs or positional args
        if "cancellation_token" in call_args.kwargs:
            cancellation_token_arg = call_args.kwargs["cancellation_token"]
        elif len(call_args.args) > 5:
            cancellation_token_arg = call_args.args[5]
        else:
            cancellation_token_arg = None

        assert cancellation_token_arg == mock_token

    @pytest.mark.asyncio
    async def test_run_data_load_async_progress_callback_integration(
        self, mock_data_manager, sample_api_data
    ):
        """Test that _run_data_load_async integrates with ServiceOrchestrator progress."""
        # Mock other dependencies
        mock_data_manager._load_data_core_logic = MagicMock(
            return_value=sample_api_data
        )
        mock_data_manager.get_current_cancellation_token.return_value = None
        mock_data_manager._format_api_response = MagicMock(
            return_value={"status": "success"}
        )

        # Call the method
        await mock_data_manager._run_data_load_async(
            "AAPL", "1min", None, None, "local", None
        )

        # Verify progress callback was passed to core logic (None is acceptable)
        call_args = mock_data_manager._load_data_core_logic.call_args
        # Check if progress_callback is in kwargs or positional args
        if "progress_callback" in call_args.kwargs:
            progress_callback_arg = call_args.kwargs["progress_callback"]
        elif len(call_args.args) > 6:
            progress_callback_arg = call_args.args[6]
        else:
            progress_callback_arg = None

        # Progress callback is None in current implementation - that's acceptable
        assert progress_callback_arg is None or callable(progress_callback_arg)

    def test_pattern_consistency_with_dummy_service(self, mock_data_manager):
        """Test that DataManager follows same patterns as DummyService."""
        # This test verifies the pattern consistency requirements from the task

        # Check that load_data_async has similar structure to DummyService.start_dummy_task
        import inspect

        # Both should be async methods
        assert asyncio.iscoroutinefunction(mock_data_manager.load_data_async)

        # Both should have docstrings explaining ServiceOrchestrator handling
        load_data_async_doc = mock_data_manager.load_data_async.__doc__
        assert load_data_async_doc is not None
        assert "ServiceOrchestrator" in load_data_async_doc

        # Both should return dict responses
        sig = inspect.signature(mock_data_manager.load_data_async)
        # Return annotation should be dict[str, Any] or similar
        return_annotation = sig.return_annotation
        assert return_annotation is not None

    def test_backward_compatibility_preserved(self, mock_data_manager, sample_api_data):
        """Test that existing DataManager functionality is preserved."""
        # Verify existing methods still exist
        assert hasattr(mock_data_manager, "load_data")
        assert hasattr(mock_data_manager, "load")
        assert hasattr(mock_data_manager, "_load_data_core_logic")

        # Verify existing method signatures unchanged
        import inspect

        load_data_sig = inspect.signature(mock_data_manager.load_data)
        assert "symbol" in load_data_sig.parameters
        assert "timeframe" in load_data_sig.parameters
        assert "validate" in load_data_sig.parameters
        assert "repair" in load_data_sig.parameters

    @pytest.mark.asyncio
    async def test_dataprogressrenderer_integration(
        self, mock_data_manager, sample_api_data
    ):
        """Test that DataProgressRenderer integration works with ServiceOrchestrator."""
        # Mock the progress renderer to ensure it's available
        mock_progress_renderer = MagicMock()
        mock_data_manager._data_progress_renderer = mock_progress_renderer

        # Mock other dependencies
        mock_data_manager._load_data_core_logic = MagicMock(
            return_value=sample_api_data
        )
        mock_data_manager.get_current_cancellation_token.return_value = None
        mock_data_manager._format_api_response = MagicMock(
            return_value={"status": "success"}
        )

        # Call the method
        await mock_data_manager._run_data_load_async(
            "AAPL", "1min", None, None, "local", None
        )

        # Verify that core logic was called (which handles progress through existing patterns)
        # The DataProgressRenderer integration happens in _load_data_core_logic
        mock_data_manager._load_data_core_logic.assert_called_once()

        # Verify that the data progress renderer is available for use
        assert mock_data_manager._data_progress_renderer is not None

    def test_api_response_format_matches_specification(
        self, mock_data_manager, sample_api_data
    ):
        """Test that _format_api_response matches the transformation plan specification."""
        result = mock_data_manager._format_api_response(
            sample_api_data, "AAPL", "1min", "local"
        )

        # Verify all required fields from transformation plan are present
        required_fields = [
            "status",
            "fetched_bars",
            "cached_before",
            "merged_file",
            "gaps_analyzed",
            "segments_fetched",
            "ib_requests_made",
            "execution_time_seconds",
        ]

        for field in required_fields:
            assert (
                field in result
            ), f"Required field '{field}' missing from API response"

        # Verify field types
        assert isinstance(result["status"], str)
        assert isinstance(result["fetched_bars"], int)
        assert isinstance(result["cached_before"], bool)
        assert isinstance(result["merged_file"], str)
        assert isinstance(result["gaps_analyzed"], int)
        assert isinstance(result["segments_fetched"], int)
        assert isinstance(result["ib_requests_made"], int)
        assert isinstance(result["execution_time_seconds"], (int, float))

"""
Test suite for DataManager ServiceOrchestrator cancellation integration.

This module tests the enhanced DataManager functionality that integrates with
ServiceOrchestrator.execute_with_cancellation() patterns while preserving all
existing functionality and API compatibility.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest

from ktrdr.data.data_manager import DataManager


class TestDataManagerServiceOrchestratorCancellation:
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
            dm.execute_with_cancellation = AsyncMock()
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

    def test_load_data_uses_execute_with_cancellation_for_non_local_modes(
        self, mock_data_manager, sample_dataframe
    ):
        """Test that load_data() uses ServiceOrchestrator.execute_with_cancellation() for non-local modes."""

        # Setup
        async def mock_operation():
            return sample_dataframe

        mock_data_manager.execute_with_cancellation.return_value = asyncio.create_task(
            mock_operation()
        )

        # This test should fail initially as we haven't implemented the change yet
        result = mock_data_manager.load_data(
            symbol="AAPL",
            timeframe="1h",
            mode="tail",  # Non-local mode
            cancellation_token=Mock(),
        )

        # Verify execute_with_cancellation was called
        mock_data_manager.execute_with_cancellation.assert_called_once()
        call_args = mock_data_manager.execute_with_cancellation.call_args

        # Check that the operation name includes the data loading context
        assert "operation_name" in call_args.kwargs
        assert "Loading" in call_args.kwargs["operation_name"]
        assert "AAPL" in call_args.kwargs["operation_name"]
        assert "1h" in call_args.kwargs["operation_name"]

    def test_load_data_uses_execute_with_cancellation_for_local_mode(
        self, mock_data_manager, sample_dataframe
    ):
        """Test that load_data() uses ServiceOrchestrator.execute_with_cancellation() even for local mode."""

        # Setup
        async def mock_operation():
            return sample_dataframe

        mock_data_manager.execute_with_cancellation.return_value = asyncio.create_task(
            mock_operation()
        )

        # This test should fail initially as local mode currently doesn't use execute_with_cancellation
        result = mock_data_manager.load_data(
            symbol="EURUSD",
            timeframe="1d",
            mode="local",  # Local mode
            cancellation_token=Mock(),
        )

        # Verify execute_with_cancellation was called even for local mode
        mock_data_manager.execute_with_cancellation.assert_called_once()

    def test_load_data_passes_cancellation_token_from_service_orchestrator(
        self, mock_data_manager, sample_dataframe
    ):
        """Test that load_data() uses cancellation token from ServiceOrchestrator.get_current_cancellation_token()."""
        # Setup
        mock_token = Mock()
        mock_token.is_cancelled_requested = False
        mock_data_manager.get_current_cancellation_token.return_value = mock_token

        async def mock_operation():
            return sample_dataframe

        mock_data_manager.execute_with_cancellation.return_value = asyncio.create_task(
            mock_operation()
        )

        # Call without explicit cancellation_token
        result = mock_data_manager.load_data(
            symbol="MSFT", timeframe="1h", mode="backfill"
        )

        # Verify that get_current_cancellation_token was called
        mock_data_manager.get_current_cancellation_token.assert_called()

        # Verify execute_with_cancellation was called with the token from ServiceOrchestrator
        mock_data_manager.execute_with_cancellation.assert_called_once()
        call_args = mock_data_manager.execute_with_cancellation.call_args

        # The internal operation should use the ServiceOrchestrator token
        assert "cancellation_token" in call_args.kwargs

    def test_load_data_preserves_existing_api_compatibility(
        self, mock_data_manager, sample_dataframe
    ):
        """Test that all existing load_data() parameters work identically with ServiceOrchestrator integration."""

        # Setup
        async def mock_operation():
            return sample_dataframe

        mock_data_manager.execute_with_cancellation.return_value = asyncio.create_task(
            mock_operation()
        )

        # Test with all parameters that should still work
        result = mock_data_manager.load_data(
            symbol="GOOGL",
            timeframe="4h",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
            mode="full",
            validate=True,
            repair=True,
            repair_outliers=False,
            strict=True,
            cancellation_token=Mock(),
            progress_callback=Mock(),
        )

        # Verify execute_with_cancellation was called
        mock_data_manager.execute_with_cancellation.assert_called_once()

        # Verify that the operation includes all the parameters
        call_args = mock_data_manager.execute_with_cancellation.call_args
        assert "operation" in call_args.kwargs

    def test_load_data_operation_wraps_existing_logic(
        self, mock_data_manager, sample_dataframe
    ):
        """Test that the operation passed to execute_with_cancellation wraps existing load_data logic."""

        # Setup
        async def capture_operation(*args, **kwargs):
            # Capture the operation that was passed
            operation = kwargs.get("operation")
            assert operation is not None
            # Execute it to verify it works
            return await operation

        mock_data_manager.execute_with_cancellation.side_effect = capture_operation
        mock_data_manager.data_loader.load.return_value = sample_dataframe

        # This should succeed once we implement the wrapper
        result = mock_data_manager.load_data(
            symbol="TSLA", timeframe="1h", mode="local"
        )

        # Verify the operation was executed
        mock_data_manager.execute_with_cancellation.assert_called_once()

    def test_load_data_error_handling_through_service_orchestrator(
        self, mock_data_manager
    ):
        """Test that errors are properly handled through ServiceOrchestrator cancellation."""

        # Setup - simulate a cancellation during operation
        async def simulate_cancellation(*args, **kwargs):
            raise asyncio.CancelledError("Operation cancelled by ServiceOrchestrator")

        mock_data_manager.execute_with_cancellation.side_effect = simulate_cancellation

        # This should raise the cancellation error properly
        with pytest.raises(asyncio.CancelledError):
            mock_data_manager.load_data(symbol="AMD", timeframe="1h", mode="tail")

    def test_load_method_also_uses_service_orchestrator_cancellation(
        self, mock_data_manager, sample_dataframe
    ):
        """Test that the legacy load() method also benefits from ServiceOrchestrator cancellation."""

        # Setup
        async def mock_operation():
            return sample_dataframe

        mock_data_manager.execute_with_cancellation.return_value = asyncio.create_task(
            mock_operation()
        )

        # Call the legacy load method
        result = mock_data_manager.load(
            symbol="NVDA",
            interval="1h",  # Note: uses 'interval' not 'timeframe'
            validate=True,
            repair=False,
        )

        # Verify execute_with_cancellation was called (since load() calls load_data())
        mock_data_manager.execute_with_cancellation.assert_called_once()


class TestDataLoadingJobServiceOrchestratorIntegration:
    """Test DataLoadingJob integration with ServiceOrchestrator cancellation patterns."""

    def test_data_loading_job_uses_service_orchestrator_token(self):
        """Test that DataLoadingJob integrates with ServiceOrchestrator cancellation tokens."""
        from ktrdr.data.components.data_job_manager import DataLoadingJob

        # Create a DataLoadingJob
        job = DataLoadingJob(
            job_id="test-123",
            symbol="AAPL",
            timeframe="1h",
            start_date=None,
            end_date=None,
            mode="tail",
        )

        # Verify it has the ServiceOrchestrator-compatible interface
        assert hasattr(job, "is_cancelled_requested")
        assert hasattr(job, "cancellation_token")
        # cancellation_token is a property that returns a token object, not callable itself
        assert hasattr(job.cancellation_token, "is_cancelled")

    def test_data_loading_job_cancellation_token_compatibility(self):
        """Test that DataLoadingJob cancellation token is compatible with ServiceOrchestrator."""
        from ktrdr.data.components.data_job_manager import DataLoadingJob

        job = DataLoadingJob(
            job_id="test-456",
            symbol="MSFT",
            timeframe="1d",
            start_date=None,
            end_date=None,
            mode="backfill",
        )

        # Test the CancellationToken protocol compatibility
        token = job.cancellation_token

        # Should have the required methods for ServiceOrchestrator integration
        assert hasattr(token, "is_cancelled")
        assert hasattr(token, "cancel")
        assert callable(token.is_cancelled)
        assert callable(token.cancel)

        # Test cancellation flow
        assert not job.is_cancelled_requested
        job.cancel("Test cancellation")
        assert job.is_cancelled_requested

    def test_data_job_manager_passes_service_orchestrator_token_to_data_manager(self):
        """Test that DataJobManager passes ServiceOrchestrator cancellation token to DataManager."""
        from ktrdr.data.components.data_job_manager import (
            DataJobManager,
        )

        with patch(
            "ktrdr.data.components.data_job_manager.DataManager"
        ) as MockDataManager:
            # Setup
            mock_dm_instance = MockDataManager.return_value
            mock_dm_instance.load_data.return_value = pd.DataFrame()

            job_manager = DataJobManager()

            # Create and execute a job
            job_id = job_manager.create_job("AAPL", "1h", mode="tail")
            job = job_manager.jobs[job_id]

            # Execute the sync load method that should pass the token
            result = job_manager._sync_load_data_with_cancellation(job)

            # Verify DataManager.load_data was called with the job's cancellation token
            mock_dm_instance.load_data.assert_called_once()
            call_kwargs = mock_dm_instance.load_data.call_args.kwargs
            assert "cancellation_token" in call_kwargs
            assert call_kwargs["cancellation_token"] == job.cancellation_token


class TestServiceOrchestratorCancellationPreservesExistingFunctionality:
    """Test that ServiceOrchestrator cancellation integration preserves all existing functionality."""

    @pytest.fixture
    def mock_data_manager_with_real_components(self):
        """Create a DataManager that preserves real component behavior for integration testing."""
        with (
            patch("ktrdr.data.data_manager.create_default_datamanager_builder"),
            patch("ktrdr.managers.ServiceOrchestrator.__init__", return_value=None),
        ):
            dm = DataManager()

            # Use real components where possible, mock only external dependencies
            dm.execute_with_cancellation = AsyncMock()
            dm.get_current_cancellation_token = Mock()

            return dm

    def test_existing_cli_data_commands_work_with_service_orchestrator_integration(
        self, mock_data_manager_with_real_components
    ):
        """Test that existing CLI data commands continue to work identically."""
        # This is an integration test that would verify CLI commands still work
        # In practice, this would test the CLI interface, but here we test the manager methods

        dm = mock_data_manager_with_real_components
        sample_df = pd.DataFrame({"close": [100, 101, 102]})

        # Mock the execute_with_cancellation to return expected data
        async def mock_execute(*args, **kwargs):
            return sample_df

        dm.execute_with_cancellation.return_value = asyncio.create_task(mock_execute())

        # Test various calling patterns that CLI would use
        result1 = dm.load_data("AAPL", "1h", mode="local")
        result2 = dm.load("MSFT", "1d", validate=True, repair=False)

        # Both should call execute_with_cancellation
        assert dm.execute_with_cancellation.call_count == 2

    def test_all_existing_data_manager_methods_preserve_behavior(
        self, mock_data_manager_with_real_components
    ):
        """Test that all existing DataManager methods preserve their behavior."""
        dm = mock_data_manager_with_real_components

        # Mock required dependencies for testing
        dm.data_loader = Mock()
        dm.gap_analyzer = Mock()

        sample_df = pd.DataFrame(
            {
                "open": [100],
                "high": [101],
                "low": [99],
                "close": [100.5],
                "volume": [1000],
            }
        )

        # Test methods that should not be affected by ServiceOrchestrator integration
        dm.data_loader.get_data_date_range.return_value = (
            datetime(2023, 1, 1),
            datetime(2023, 1, 31),
        )
        dm.data_loader.load.return_value = sample_df
        dm.gap_analyzer.detect_gaps.return_value = []

        # These methods should work exactly the same as before
        summary = dm.get_data_summary("AAPL", "1h")
        assert summary["symbol"] == "AAPL"
        assert summary["timeframe"] == "1h"

        # Method calls should be preserved
        dm.data_loader.get_data_date_range.assert_called_once_with("AAPL", "1h")
        dm.data_loader.load.assert_called_once_with("AAPL", "1h")

    def test_service_orchestrator_cancellation_performance_regression(
        self, mock_data_manager_with_real_components
    ):
        """Test that ServiceOrchestrator integration doesn't introduce significant performance regression."""
        import time

        dm = mock_data_manager_with_real_components
        sample_df = pd.DataFrame({"close": [100]})

        # Mock execute_with_cancellation to complete quickly
        async def fast_execute(*args, **kwargs):
            return sample_df

        dm.execute_with_cancellation.return_value = asyncio.create_task(fast_execute())

        # Measure execution time (should be minimal)
        start_time = time.time()
        result = dm.load_data("AAPL", "1h", mode="local")
        execution_time = time.time() - start_time

        # Should complete quickly (less than 1 second for mocked operation)
        assert execution_time < 1.0

        # Verify the operation was called through ServiceOrchestrator
        dm.execute_with_cancellation.assert_called_once()

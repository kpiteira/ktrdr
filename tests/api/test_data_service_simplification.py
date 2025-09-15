"""
Tests for DataService simplification - Phase 2 of transformation.

These tests verify that DataService has been transformed from a complex orchestrator
to a thin API adapter that delegates to enhanced DataManager.

Test Requirements (TDD approach):
- DataService.load_data() delegates to DataManager.load_data_async()
- Complex orchestration methods are removed (315+ lines eliminated)
- API compatibility is maintained
- 60% code reduction achieved (1001 → ~400 lines)
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.services.data_service import DataService


@pytest.fixture
def mock_data_manager():
    """Mock DataManager with load_data_async method."""
    with patch("ktrdr.api.services.data_service.DataManager") as mock:
        mock_instance = MagicMock()
        # Mock the new load_data_async method that returns API-formatted response
        mock_instance.load_data_async = AsyncMock(
            return_value={
                "status": "success",
                "fetched_bars": 100,
                "cached_before": True,
                "merged_file": "AAPL_1d.csv",
                "gaps_analyzed": 0,
                "segments_fetched": 1,
                "ib_requests_made": 0,
                "execution_time_seconds": 0.5,
                "error_message": None,
            }
        )
        mock.return_value = mock_instance
        yield mock_instance


@pytest.mark.api
@pytest.mark.asyncio
async def test_load_data_delegates_to_datamanager_async(mock_data_manager):
    """
    Test that DataService.load_data() delegates to DataManager.load_data_async().

    This is the core test for the transformation - DataService should no longer
    contain complex orchestration but simply delegate to the enhanced DataManager.

    THIS TEST WILL FAIL INITIALLY - this is expected for TDD approach.
    After implementation, this test should pass.
    """
    service = DataService()

    # Call the load_data method
    result = await service.load_data(
        symbol="AAPL",
        timeframe="1d",
        start_date="2023-01-01",
        end_date="2023-01-03",
        mode="local",
        filters={"trading_hours_only": True},
    )

    # Verify DataManager.load_data_async was called with correct parameters
    mock_data_manager.load_data_async.assert_called_once_with(
        symbol="AAPL",
        timeframe="1d",
        start_date="2023-01-01",
        end_date="2023-01-03",
        mode="local",
        filters={"trading_hours_only": True},
    )

    # Verify result is directly from DataManager (already API-formatted)
    assert result == {
        "status": "success",
        "fetched_bars": 100,
        "cached_before": True,
        "merged_file": "AAPL_1d.csv",
        "gaps_analyzed": 0,
        "segments_fetched": 1,
        "ib_requests_made": 0,
        "execution_time_seconds": 0.5,
        "error_message": None,
    }


@pytest.mark.api
def test_complex_orchestration_methods_removed():
    """
    Test that complex orchestration methods have been removed from DataService.

    These methods should no longer exist after simplification:
    - _cancellable_data_load() (177 lines)
    - _run_data_loading_operation() (76 lines)
    - start_data_loading_operation() (62 lines)

    Total: 315+ lines of redundant orchestration eliminated.

    THIS TEST WILL FAIL INITIALLY - these methods currently exist.
    After implementation, this test should pass.
    """
    service = DataService()

    # These methods should NOT exist in simplified DataService
    assert not hasattr(
        service, "_cancellable_data_load"
    ), "_cancellable_data_load should be removed (177 lines eliminated)"

    assert not hasattr(
        service, "_run_data_loading_operation"
    ), "_run_data_loading_operation should be removed (76 lines eliminated)"

    # start_data_loading_operation should be simplified but kept for backward compatibility
    if hasattr(service, "start_data_loading_operation"):
        # Check that it's simplified (inspect source for delegation pattern)
        import inspect

        source = inspect.getsource(service.start_data_loading_operation)
        assert (
            "data_manager.load_data_async" in source
        ), "start_data_loading_operation should delegate to DataManager"
        assert (
            "ThreadPoolExecutor" not in source
        ), "start_data_loading_operation should not use ThreadPoolExecutor"


@pytest.mark.api
def test_api_helper_methods_preserved():
    """
    Test that API-specific helper methods are preserved in simplified DataService.

    These methods should remain as they provide API-specific functionality:
    - _convert_df_to_api_format() - API formatting helper
    - _filter_trading_hours() - API filtering helper
    - get_available_symbols() - API metadata (should be simplified to delegate)
    - health_check() - API service interface
    """
    service = DataService()

    # These methods should still exist (API-specific helpers)
    assert hasattr(
        service, "_convert_df_to_api_format"
    ), "_convert_df_to_api_format should be preserved (API formatting)"

    assert hasattr(
        service, "_filter_trading_hours"
    ), "_filter_trading_hours should be preserved (API filtering)"

    assert hasattr(
        service, "get_available_symbols"
    ), "get_available_symbols should be preserved (API metadata)"

    assert hasattr(
        service, "health_check"
    ), "health_check should be preserved (API service interface)"


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_available_symbols_simplified(mock_data_manager):
    """
    Test that get_available_symbols() is working properly after simplification.

    Since this method provides API-specific metadata aggregation, we keep it
    but ensure it's not overly complex.
    """
    # Mock the data_loader that get_available_symbols uses
    mock_data_manager.data_loader.get_available_data_files.return_value = [
        ("AAPL", "1d"),
        ("AAPL", "1h"),
    ]
    mock_data_manager.data_loader.get_data_date_range.return_value = (
        datetime(2023, 1, 1),
        datetime(2023, 12, 31),
    )

    service = DataService()
    result = await service.get_available_symbols()

    # Should work with existing pattern (API-specific logic is appropriate here)
    mock_data_manager.data_loader.get_available_data_files.assert_called_once()

    # Should return symbol information
    assert isinstance(result, list)
    if result:
        assert "symbol" in result[0]
        assert "available_timeframes" in result[0]


@pytest.mark.api
def test_dataservice_line_count_reduction():
    """
    Test that DataService has achieved 60% code reduction.

    Target: 1001 lines → ~400 lines (60% reduction)

    This test verifies the quantitative aspect of the simplification.

    THIS TEST WILL INITIALLY FAIL - file currently has 1001 lines.
    After implementation, this test should pass.
    """
    import inspect

    # Get the DataService source file path
    data_service_file = inspect.getfile(DataService)

    # Count lines in the file
    with open(data_service_file) as f:
        line_count = len(f.readlines())

    # Verify significant reduction (target: ~400 lines, allow reasonable flexibility)
    max_allowed_lines = 550  # Allow reasonable buffer for API helpers and docstrings
    assert line_count <= max_allowed_lines, (
        f"DataService should be significantly simplified, but has {line_count} lines. "
        f"Should be under {max_allowed_lines} lines (started at 1001 lines)"
    )

    # Also verify it's actually been reduced from original
    original_lines = 1001
    reduction_percentage = (original_lines - line_count) / original_lines * 100
    assert (
        reduction_percentage >= 50
    ), f"DataService should achieve at least 50% reduction, got {reduction_percentage:.1f}%"


@pytest.mark.api
def test_no_threadpool_executor_imports():
    """
    Test that DataService no longer imports or uses ThreadPoolExecutor.

    The simplified DataService should not have any manual async orchestration,
    so concurrent.futures imports should be removed.

    THIS TEST WILL INITIALLY FAIL - DataService currently uses ThreadPoolExecutor.
    After implementation, this test should pass.
    """
    import inspect

    # Get the DataService source code
    source = inspect.getsource(DataService)

    # Check for ThreadPoolExecutor usage
    assert (
        "concurrent.futures" not in source
    ), "DataService should not import concurrent.futures (orchestration eliminated)"

    assert (
        "ThreadPoolExecutor" not in source
    ), "DataService should not use ThreadPoolExecutor (delegated to DataManager)"


@pytest.mark.api
def test_no_manual_progress_callback_code():
    """
    Test that DataService no longer contains manual progress callback code.

    Progress handling should be delegated to DataManager's ServiceOrchestrator,
    so manual progress callback functions should be removed.

    THIS TEST WILL INITIALLY FAIL - DataService currently has progress callbacks.
    After implementation, this test should pass.
    """
    import inspect

    # Get the DataService source code
    source = inspect.getsource(DataService)

    # Check for manual progress callback patterns
    assert (
        "progress_callback_fn" not in source
    ), "Manual progress callbacks should be removed (delegated to ServiceOrchestrator)"

    assert (
        "update_progress_periodically" not in source
    ), "Manual progress updates should be removed (delegated to ServiceOrchestrator)"

    assert (
        "OperationProgress(" not in source
    ), "Manual OperationProgress creation should be removed"


@pytest.mark.api
@pytest.mark.asyncio
async def test_backward_compatibility_maintained(mock_data_manager):
    """
    Test that DataService API remains backward compatible after simplification.

    All existing API functionality should work the same way from the outside,
    even though internal implementation is simplified.
    """
    service = DataService()

    # Test all the main API methods still work

    # load_data should work
    result = await service.load_data("AAPL", "1d")
    assert "status" in result
    assert "fetched_bars" in result

    # health_check should work
    health_result = await service.health_check()
    assert "status" in health_result

    # get_available_timeframes should work
    timeframes = await service.get_available_timeframes()
    assert isinstance(timeframes, list)

    # All methods should still be callable with same signatures
    # (implementation changes but API contract remains same)


@pytest.mark.api
def test_simplified_load_data_method_structure():
    """
    Test that load_data method has been simplified to ~5-10 lines.

    The method should be simple delegation, not complex orchestration.

    THIS TEST WILL INITIALLY FAIL - load_data currently has complex logic.
    After implementation, this test should pass.
    """
    import inspect

    # Get the load_data method source
    load_data_method = inspect.getsource(DataService.load_data)

    # Count non-comment, non-empty lines
    lines = [
        line.strip()
        for line in load_data_method.split("\n")
        if line.strip()
        and not line.strip().startswith("#")
        and not line.strip().startswith('"""')
        and not line.strip().startswith("'''")
    ]

    # Method should be much simpler than before (was ~80+ lines of complex logic)
    max_lines = 40  # Allow flexibility for decorators, docstring, and simple delegation
    assert len(lines) <= max_lines, (
        f"load_data should be simplified from complex orchestration to simple delegation, "
        f"but has {len(lines)} lines (including decorators and docstring)"
    )

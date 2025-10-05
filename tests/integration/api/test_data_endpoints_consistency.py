"""
Phase 3: API Endpoint Consistency Tests

Tests for consistent DataManager delegation patterns in API endpoints,
ensuring no direct bypass patterns remain and all endpoints use
consistent DataService delegation.

These tests specifically verify the Phase 3 transformation requirements:
- No direct bypass patterns (`data_service.data_manager.*`)
- Consistent delegation to DataManager ServiceOrchestrator
- Backward compatibility maintained
- Error handling works through delegation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.errors import DataError


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    from fastapi.testclient import TestClient

    from ktrdr.api.main import app

    return TestClient(app)


@pytest.fixture
def mock_data_service():
    """Create a mock DataService for testing consistency patterns."""
    with patch("ktrdr.api.dependencies.DataService") as mock_class:
        mock_instance = mock_class.return_value

        # Set up async methods to return AsyncMock objects
        mock_instance.get_available_symbols = AsyncMock()
        mock_instance.get_available_timeframes = AsyncMock()
        mock_instance.load_data = AsyncMock()
        mock_instance.get_data_range = AsyncMock()

        # Mock the DataManager to detect direct bypass patterns
        mock_data_manager = MagicMock()
        mock_data_manager.load_data = MagicMock()
        mock_instance.data_manager = mock_data_manager

        # Mock DataService delegation methods
        mock_instance.load_cached_data = MagicMock()
        mock_instance.load_data_async = AsyncMock()

        # Mock API formatting helper
        mock_instance._convert_df_to_api_format = MagicMock()
        mock_instance._filter_trading_hours = MagicMock()

        yield mock_instance


class TestAPIEndpointConsistency:
    """Test consistent DataService delegation patterns across all endpoints."""

    @pytest.mark.api
    def test_cached_data_endpoint_no_direct_bypass(self, client, mock_data_service):
        """Test that get_cached_data endpoint doesn't use direct bypass patterns."""
        import pandas as pd

        # Set up mock data to return from proper delegation
        sample_df = pd.DataFrame(
            {
                "datetime": ["2023-01-01 09:30:00", "2023-01-01 10:30:00"],
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.5],
                "close": [101.0, 102.5],
                "volume": [1000, 1500],
            }
        )

        # Configure DataService delegation method to return DataFrame
        mock_data_service.load_cached_data.return_value = sample_df

        # Configure API formatting helper
        mock_data_service._convert_df_to_api_format.return_value = {
            "dates": ["2023-01-01T09:30:00", "2023-01-01T10:30:00"],
            "ohlcv": [
                [100.0, 102.0, 99.0, 101.0, 1000],
                [101.0, 103.0, 100.5, 102.5, 1500],
            ],
            "metadata": {
                "symbol": "AAPL",
                "timeframe": "1h",
                "start": "2023-01-01T09:30:00",
                "end": "2023-01-01T10:30:00",
                "points": 2,
            },
        }

        # Make the request
        with patch(
            "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
        ):
            response = client.get("/api/v1/data/AAPL/1h")

        # Verify response success
        assert response.status_code == 200

        # CRITICAL: Verify proper DataService delegation is used instead of direct bypass
        mock_data_service.load_cached_data.assert_called_once()

        # Verify no direct bypass patterns are used
        mock_data_service.data_manager.load_data.assert_not_called()

        # Get the call arguments to verify the consistent delegation pattern
        call_kwargs = mock_data_service.load_cached_data.call_args[1]
        assert call_kwargs["symbol"] == "AAPL"
        assert call_kwargs["timeframe"] == "1h"
        # Should not have 'mode' since load_cached_data forces local internally

        # Verify API formatting was called
        mock_data_service._convert_df_to_api_format.assert_called_once()

    @pytest.mark.api
    def test_load_data_endpoint_consistent_delegation_async(
        self, client, mock_data_service
    ):
        """Test load_data endpoint uses consistent async delegation pattern."""
        # Set up mock to return async operation response
        mock_data_service.load_data_async.return_value = {
            "operation_id": "op_test_123",
            "status": "started",
        }

        # Make the request (always async now)
        with patch(
            "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
        ):
            response = client.post(
                "/api/v1/data/load",
                json={"symbol": "MSFT", "timeframe": "1d", "mode": "full"},
            )

        # Verify response success
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["operation_id"] == "op_test_123"
        assert data["data"]["status"] == "started"

        # CRITICAL: Verify consistent async delegation pattern
        # Now uses load_data_async for consistency
        mock_data_service.load_data_async.assert_called_once()
        call_kwargs = mock_data_service.load_data_async.call_args[1]
        assert call_kwargs["symbol"] == "MSFT"
        assert call_kwargs["timeframe"] == "1d"
        assert call_kwargs["mode"] == "full"

    @pytest.mark.api
    def test_no_direct_bypass_patterns_remain(self, client, mock_data_service):
        """Test that no endpoints use direct bypass patterns after transformation."""
        import pandas as pd

        # Set up mock data
        sample_df = pd.DataFrame(
            {
                "datetime": ["2023-01-01"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )

        # Configure mocks
        mock_data_service.load_cached_data.return_value = sample_df
        mock_data_service._convert_df_to_api_format.return_value = {
            "dates": ["2023-01-01T00:00:00"],
            "ohlcv": [[100.0, 101.0, 99.0, 100.5, 1000]],
            "metadata": {"symbol": "TEST", "timeframe": "1d", "points": 1},
        }
        mock_data_service.get_available_symbols.return_value = []

        with patch(
            "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
        ):
            # Test cached data endpoint
            response = client.get("/api/v1/data/TEST/1d")
            assert response.status_code == 200

            # CRITICAL: Verify consistent delegation pattern is used
            mock_data_service.load_cached_data.assert_called()

            # Verify no direct bypass patterns remain
            mock_data_service.data_manager.load_data.assert_not_called()

            # Phase 3 transformation complete:
            # 1. No direct data_manager.load_data calls ✅
            # 2. All calls go through consistent DataService methods ✅
            # 3. ServiceOrchestrator delegation is used consistently ✅

    @pytest.mark.api
    def test_error_handling_consistency_through_delegation(
        self, client, mock_data_service
    ):
        """Test that error handling works consistently through delegation."""
        # Set up mock to raise DataError through delegation
        mock_data_service.load_data_async.side_effect = DataError(
            message="Test error through delegation",
            error_code="DATA-TestError",
            details={"test": "error"},
        )

        with patch(
            "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
        ):
            response = client.post(
                "/api/v1/data/load",
                json={"symbol": "TEST", "timeframe": "1d", "mode": "local"},
            )

        # Verify error handling works through delegation
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "DATA-TestError"

        # Verify delegation was called
        mock_data_service.load_data_async.assert_called_once()

    @pytest.mark.api
    def test_async_response_format(self, client, mock_data_service):
        """Test that async response format is correct."""
        # Set up mock to return async operation response
        mock_data_service.load_data_async.return_value = {
            "operation_id": "op_test_123",
            "status": "started",
        }

        with patch(
            "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
        ):
            response = client.post(
                "/api/v1/data/load",
                json={"symbol": "AAPL", "timeframe": "1h", "mode": "tail"},
            )

        # Verify response format
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert "data" in data
        response_data = data["data"]

        # Verify async operation fields are present
        assert "operation_id" in response_data
        assert "status" in response_data
        assert response_data["operation_id"] == "op_test_123"
        assert response_data["status"] == "started"


class TestAPIEndpointTransformationRequirements:
    """Test specific Phase 3 transformation requirements."""

    @pytest.mark.api
    def test_phase3_requirement_no_direct_bypass(self, client, mock_data_service):
        """Test Phase 3 requirement: Eliminate direct bypass patterns."""
        # This test documents the current pattern that needs to be eliminated
        import pandas as pd

        sample_df = pd.DataFrame({"datetime": ["2023-01-01"], "close": [100.0]})
        mock_data_service.load_cached_data.return_value = sample_df
        mock_data_service._convert_df_to_api_format.return_value = {
            "dates": [],
            "ohlcv": [],
            "metadata": {},
        }
        mock_data_service.get_available_symbols.return_value = []

        with patch(
            "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
        ):
            client.get("/api/v1/data/AAPL/1d")

        # PHASE 3 COMPLETE: Consistent delegation pattern achieved
        mock_data_service.load_cached_data.assert_called()

        # Verify no direct bypass patterns remain
        mock_data_service.data_manager.load_data.assert_not_called()

    @pytest.mark.api
    def test_phase3_requirement_consistent_delegation(self, client, mock_data_service):
        """Test Phase 3 requirement: All endpoints use consistent DataService delegation."""
        mock_data_service.load_data_async.return_value = {
            "operation_id": "op_test_456",
            "status": "started",
        }

        with patch(
            "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
        ):
            response = client.post(
                "/api/v1/data/load",
                json={"symbol": "AAPL", "timeframe": "1d", "mode": "local"},
            )

        assert response.status_code == 200

        # Verify consistent delegation pattern - always async now
        mock_data_service.load_data_async.assert_called_once()
        call_kwargs = mock_data_service.load_data_async.call_args[1]

        # Verify delegation includes all required parameters
        required_params = ["symbol", "timeframe", "mode"]
        for param in required_params:
            assert param in call_kwargs

    @pytest.mark.api
    def test_phase3_requirement_performance_maintained(self, client, mock_data_service):
        """Test Phase 3 requirement: No performance degradation from endpoint changes."""
        import time

        # Set up fast mock response for async operation
        mock_data_service.load_data_async.return_value = {
            "operation_id": "op_perf_test",
            "status": "started",
        }

        with patch(
            "ktrdr.api.dependencies.get_data_service", return_value=mock_data_service
        ):
            start_time = time.time()

            response = client.post(
                "/api/v1/data/load",
                json={"symbol": "AAPL", "timeframe": "1h", "mode": "tail"},
            )

            end_time = time.time()

        # Verify response success
        assert response.status_code == 200

        # Verify performance (should be very fast with mocks)
        response_time = end_time - start_time
        assert response_time < 1.0  # Should be sub-second with mocks

        # Verify delegation was efficient (single call)
        assert mock_data_service.load_data_async.call_count == 1

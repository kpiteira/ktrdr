"""
Tests for the GET /fuzzy/data endpoint.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

# Test setup will be handled by the test runner
from ktrdr.api.main import app


class TestFuzzyDataEndpoint:
    """Test cases for GET /fuzzy/data endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def teardown_method(self):
        """Clean up after tests."""
        # Clear any dependency overrides
        app.dependency_overrides.clear()

    def test_get_fuzzy_overlay_data_success(self):
        """Test successful fuzzy overlay data retrieval."""
        # Mock the service response
        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            return_value={
                "symbol": "AAPL",
                "timeframe": "1h",
                "data": {
                    "rsi": [
                        {
                            "set": "low",
                            "membership": [
                                {"timestamp": "2023-01-01T09:00:00", "value": 0.8},
                                {"timestamp": "2023-01-01T10:00:00", "value": 0.6},
                            ],
                        },
                        {
                            "set": "high",
                            "membership": [
                                {"timestamp": "2023-01-01T09:00:00", "value": 0.2},
                                {"timestamp": "2023-01-01T10:00:00", "value": 0.4},
                            ],
                        },
                    ]
                },
            }
        )

        # Override the dependency
        from ktrdr.api.dependencies import get_fuzzy_service

        app.dependency_overrides[get_fuzzy_service] = lambda: mock_service

        try:
            # Make request
            response = self.client.get("/api/v1/fuzzy/data?symbol=AAPL&timeframe=1h")

            # Verify response
            assert response.status_code == 200
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["timeframe"] == "1h"
        assert "rsi" in data["data"]
        assert len(data["data"]["rsi"]) == 2

        # Verify fuzzy sets
        set_names = [fs["set"] for fs in data["data"]["rsi"]]
        assert "low" in set_names
        assert "high" in set_names

        # Verify membership structure
        low_set = next(fs for fs in data["data"]["rsi"] if fs["set"] == "low")
        assert len(low_set["membership"]) == 2
        assert low_set["membership"][0]["value"] == 0.8

    @patch("ktrdr.api.dependencies.get_fuzzy_service")
    def test_get_fuzzy_overlay_data_with_indicators_filter(self, mock_get_service):
        """Test fuzzy overlay data with specific indicators."""
        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            return_value={
                "symbol": "AAPL",
                "timeframe": "1h",
                "data": {"rsi": [{"set": "low", "membership": []}]},
            }
        )
        mock_get_service.return_value = mock_service

        # Make request with specific indicators
        response = self.client.get(
            "/api/v1/fuzzy/data?symbol=AAPL&timeframe=1h&indicators=rsi&indicators=macd"
        )

        assert response.status_code == 200

        # Verify service was called with correct parameters
        mock_service.get_fuzzy_overlays.assert_called_once()
        call_args = mock_service.get_fuzzy_overlays.call_args
        assert call_args.kwargs["symbol"] == "AAPL"
        assert call_args.kwargs["timeframe"] == "1h"
        assert call_args.kwargs["indicators"] == ["rsi", "macd"]

    @patch("ktrdr.api.dependencies.get_fuzzy_service")
    def test_get_fuzzy_overlay_data_with_date_range(self, mock_get_service):
        """Test fuzzy overlay data with date range filtering."""
        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            return_value={"symbol": "AAPL", "timeframe": "1h", "data": {}}
        )
        mock_get_service.return_value = mock_service

        # Make request with date range
        response = self.client.get(
            "/api/v1/fuzzy/data?symbol=AAPL&timeframe=1h"
            "&start_date=2023-01-01T00:00:00"
            "&end_date=2023-01-31T23:59:59"
        )

        assert response.status_code == 200

        # Verify service was called with date parameters
        call_args = mock_service.get_fuzzy_overlays.call_args
        assert call_args.kwargs["start_date"] == "2023-01-01T00:00:00"
        assert call_args.kwargs["end_date"] == "2023-01-31T23:59:59"

    @patch("ktrdr.api.dependencies.get_fuzzy_service")
    def test_get_fuzzy_overlay_data_with_warnings(self, mock_get_service):
        """Test fuzzy overlay data response with warnings."""
        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            return_value={
                "symbol": "AAPL",
                "timeframe": "1h",
                "data": {"rsi": [{"set": "low", "membership": []}]},
                "warnings": ["Unknown indicator 'invalid_indicator' - skipping"],
            }
        )
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/v1/fuzzy/data?symbol=AAPL&timeframe=1h")

        assert response.status_code == 200
        data = response.json()

        assert "warnings" in data
        assert len(data["warnings"]) == 1
        assert "invalid_indicator" in data["warnings"][0]

    def test_get_fuzzy_overlay_data_missing_symbol(self):
        """Test error handling for missing symbol parameter."""
        response = self.client.get("/api/v1/fuzzy/data?timeframe=1h")

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "symbol" in str(data["detail"]).lower()

    def test_get_fuzzy_overlay_data_missing_timeframe(self):
        """Test error handling for missing timeframe parameter."""
        response = self.client.get("/api/v1/fuzzy/data?symbol=AAPL")

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "timeframe" in str(data["detail"]).lower()

    @patch("ktrdr.api.dependencies.get_fuzzy_service")
    def test_get_fuzzy_overlay_data_data_error(self, mock_get_service):
        """Test handling of DataError (no data available)."""
        from ktrdr.errors import DataError

        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            side_effect=DataError(
                message="No data available for INVALID (1h)",
                error_code="DATA-NoData",
                details={"symbol": "INVALID", "timeframe": "1h"},
            )
        )
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/v1/fuzzy/data?symbol=INVALID&timeframe=1h")

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "DATA-NoData"
        assert "No data available" in data["error"]["message"]

    @patch("ktrdr.api.dependencies.get_fuzzy_service")
    def test_get_fuzzy_overlay_data_configuration_error(self, mock_get_service):
        """Test handling of ConfigurationError."""
        from ktrdr.errors import ConfigurationError

        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            side_effect=ConfigurationError(
                message="Fuzzy engine is not initialized",
                error_code="CONFIG-FuzzyEngineNotInitialized",
                details={},
            )
        )
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/v1/fuzzy/data?symbol=AAPL&timeframe=1h")

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "CONFIG-FuzzyEngineNotInitialized"
        assert "not initialized" in data["error"]["message"]

    @patch("ktrdr.api.dependencies.get_fuzzy_service")
    def test_get_fuzzy_overlay_data_processing_error(self, mock_get_service):
        """Test handling of ProcessingError."""
        from ktrdr.errors import ProcessingError

        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            side_effect=ProcessingError(
                message="Failed to process fuzzy overlays",
                error_code="PROC-FuzzyOverlayError",
                details={"error": "Calculation failed"},
            )
        )
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/v1/fuzzy/data?symbol=AAPL&timeframe=1h")

        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "PROC-FuzzyOverlayError"
        assert "Failed to process" in data["error"]["message"]

    @patch("ktrdr.api.dependencies.get_fuzzy_service")
    def test_get_fuzzy_overlay_data_unexpected_error(self, mock_get_service):
        """Test handling of unexpected errors."""
        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            side_effect=Exception("Unexpected error occurred")
        )
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/v1/fuzzy/data?symbol=AAPL&timeframe=1h")

        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "INTERNAL_ERROR"
        assert "unexpected error" in data["error"]["message"].lower()

    @patch("ktrdr.api.dependencies.get_fuzzy_service")
    def test_get_fuzzy_overlay_data_empty_response(self, mock_get_service):
        """Test response with empty data (no valid indicators)."""
        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            return_value={
                "symbol": "AAPL",
                "timeframe": "1h",
                "data": {},
                "warnings": ["No valid indicators found"],
            }
        )
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/v1/fuzzy/data?symbol=AAPL&timeframe=1h")

        assert response.status_code == 200
        data = response.json()

        assert data["symbol"] == "AAPL"
        assert data["timeframe"] == "1h"
        assert data["data"] == {}
        assert "warnings" in data
        assert "No valid indicators" in data["warnings"][0]

    @patch("ktrdr.api.dependencies.get_fuzzy_service")
    def test_get_fuzzy_overlay_data_response_format(self, mock_get_service):
        """Test that response matches expected Pydantic model format."""
        mock_service = Mock()
        mock_service.get_fuzzy_overlays = AsyncMock(
            return_value={
                "symbol": "aapl",  # Should be normalized to uppercase
                "timeframe": " 1h ",  # Should be trimmed
                "data": {
                    "rsi": [
                        {
                            "set": "low",
                            "membership": [
                                {"timestamp": "2023-01-01T09:00:00", "value": 0.8}
                            ],
                        }
                    ]
                },
            }
        )
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/v1/fuzzy/data?symbol=aapl&timeframe= 1h ")

        assert response.status_code == 200
        data = response.json()

        # Verify Pydantic validation worked
        assert data["symbol"] == "AAPL"  # Normalized to uppercase
        assert data["timeframe"] == "1h"  # Trimmed

        # Verify structure matches FuzzyOverlayResponse
        assert "data" in data
        assert "rsi" in data["data"]
        rsi_data = data["data"]["rsi"][0]
        assert "set" in rsi_data
        assert "membership" in rsi_data
        assert isinstance(rsi_data["membership"], list)

        # Verify membership point structure
        membership_point = rsi_data["membership"][0]
        assert "timestamp" in membership_point
        assert "value" in membership_point
        assert membership_point["value"] == 0.8

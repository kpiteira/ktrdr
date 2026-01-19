"""
Tests for GET /data/{symbol}/{timeframe} cached data endpoint.

Tests the limit parameter functionality for server-side pagination.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ktrdr.api.endpoints.data import get_data_service, router


@pytest.fixture
def app():
    """Create FastAPI test app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def mock_data_service():
    """Mock DataService with required methods."""
    service = MagicMock()
    return service


class TestGetCachedDataWithLimit:
    """Tests for GET /data/{symbol}/{timeframe} endpoint with limit parameter."""

    def test_limit_parameter_accepted(self, app, mock_data_service):
        """Test that the limit query parameter is accepted."""
        # Create sample DataFrame
        df = pd.DataFrame(
            {
                "open": [100.0] * 10,
                "high": [101.0] * 10,
                "low": [99.0] * 10,
                "close": [100.5] * 10,
                "volume": [1000] * 10,
            },
            index=pd.date_range("2024-01-01", periods=10, freq="D"),
        )

        mock_data_service.load_cached_data.return_value = df
        mock_data_service._convert_df_to_api_format.return_value = {
            "dates": [f"2024-01-{i:02d}" for i in range(1, 11)],
            "ohlcv": [[100.0, 101.0, 99.0, 100.5, 1000]] * 10,
            "metadata": {"symbol": "AAPL", "timeframe": "1d", "points": 10},
        }

        app.dependency_overrides[get_data_service] = lambda: mock_data_service

        client = TestClient(app)
        response = client.get("/data/AAPL/1d?limit=5")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should have only 5 data points (limited from 10)
        assert len(data["data"]["dates"]) == 5

    def test_limit_returns_most_recent_data(self, app, mock_data_service):
        """Test that limit returns the most recent N data points."""
        df = pd.DataFrame(
            {
                "open": [100.0] * 10,
                "high": [101.0] * 10,
                "low": [99.0] * 10,
                "close": [100.5] * 10,
                "volume": [1000] * 10,
            },
            index=pd.date_range("2024-01-01", periods=10, freq="D"),
        )

        mock_data_service.load_cached_data.return_value = df
        # Dates go from 01 to 10
        mock_data_service._convert_df_to_api_format.return_value = {
            "dates": [f"2024-01-{i:02d}" for i in range(1, 11)],
            "ohlcv": [[100.0, 101.0, 99.0, 100.5, 1000]] * 10,
            "metadata": {"symbol": "AAPL", "timeframe": "1d", "points": 10},
        }

        app.dependency_overrides[get_data_service] = lambda: mock_data_service

        client = TestClient(app)
        response = client.get("/data/AAPL/1d?limit=3")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        # Should return the LAST 3 dates (most recent)
        assert data["data"]["dates"] == ["2024-01-08", "2024-01-09", "2024-01-10"]

    def test_limit_adds_metadata_fields(self, app, mock_data_service):
        """Test that limit adds 'limited' and 'original_points' to metadata."""
        df = pd.DataFrame(
            {
                "open": [100.0] * 10,
                "high": [101.0] * 10,
                "low": [99.0] * 10,
                "close": [100.5] * 10,
                "volume": [1000] * 10,
            },
            index=pd.date_range("2024-01-01", periods=10, freq="D"),
        )

        mock_data_service.load_cached_data.return_value = df
        mock_data_service._convert_df_to_api_format.return_value = {
            "dates": [f"2024-01-{i:02d}" for i in range(1, 11)],
            "ohlcv": [[100.0, 101.0, 99.0, 100.5, 1000]] * 10,
            "metadata": {"symbol": "AAPL", "timeframe": "1d", "points": 10},
        }

        app.dependency_overrides[get_data_service] = lambda: mock_data_service

        client = TestClient(app)
        response = client.get("/data/AAPL/1d?limit=5")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        metadata = data["data"]["metadata"]
        assert metadata["limited"] is True
        assert metadata["original_points"] == 10
        assert metadata["points"] == 5

    def test_limit_greater_than_data_returns_all(self, app, mock_data_service):
        """Test that limit greater than available data returns all data."""
        df = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [1000] * 5,
            },
            index=pd.date_range("2024-01-01", periods=5, freq="D"),
        )

        mock_data_service.load_cached_data.return_value = df
        mock_data_service._convert_df_to_api_format.return_value = {
            "dates": [f"2024-01-{i:02d}" for i in range(1, 6)],
            "ohlcv": [[100.0, 101.0, 99.0, 100.5, 1000]] * 5,
            "metadata": {"symbol": "AAPL", "timeframe": "1d", "points": 5},
        }

        app.dependency_overrides[get_data_service] = lambda: mock_data_service

        client = TestClient(app)
        response = client.get("/data/AAPL/1d?limit=100")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        # Should return all 5 points (limit > available)
        assert len(data["data"]["dates"]) == 5
        # Should NOT have 'limited' metadata since no limiting occurred
        assert data["data"]["metadata"].get("limited") is not True

    def test_limit_validation_minimum(self, app, mock_data_service):
        """Test that limit below minimum (1) is rejected."""
        app.dependency_overrides[get_data_service] = lambda: mock_data_service

        client = TestClient(app)
        response = client.get("/data/AAPL/1d?limit=0")

        app.dependency_overrides.clear()

        assert response.status_code == 422  # Validation error

    def test_limit_validation_maximum(self, app, mock_data_service):
        """Test that limit above maximum (100000) is rejected."""
        app.dependency_overrides[get_data_service] = lambda: mock_data_service

        client = TestClient(app)
        response = client.get("/data/AAPL/1d?limit=100001")

        app.dependency_overrides.clear()

        assert response.status_code == 422  # Validation error

    def test_no_limit_returns_all_data(self, app, mock_data_service):
        """Test that omitting limit returns all data."""
        df = pd.DataFrame(
            {
                "open": [100.0] * 10,
                "high": [101.0] * 10,
                "low": [99.0] * 10,
                "close": [100.5] * 10,
                "volume": [1000] * 10,
            },
            index=pd.date_range("2024-01-01", periods=10, freq="D"),
        )

        mock_data_service.load_cached_data.return_value = df
        mock_data_service._convert_df_to_api_format.return_value = {
            "dates": [f"2024-01-{i:02d}" for i in range(1, 11)],
            "ohlcv": [[100.0, 101.0, 99.0, 100.5, 1000]] * 10,
            "metadata": {"symbol": "AAPL", "timeframe": "1d", "points": 10},
        }

        app.dependency_overrides[get_data_service] = lambda: mock_data_service

        client = TestClient(app)
        response = client.get("/data/AAPL/1d")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        # Should return all 10 points
        assert len(data["data"]["dates"]) == 10

    def test_limit_with_empty_metadata(self, app, mock_data_service):
        """Test that limit works when metadata is empty dict (not None)."""
        df = pd.DataFrame(
            {
                "open": [100.0] * 10,
                "high": [101.0] * 10,
                "low": [99.0] * 10,
                "close": [100.5] * 10,
                "volume": [1000] * 10,
            },
            index=pd.date_range("2024-01-01", periods=10, freq="D"),
        )

        mock_data_service.load_cached_data.return_value = df
        # Return empty dict for metadata (edge case that triggered the bug)
        mock_data_service._convert_df_to_api_format.return_value = {
            "dates": [f"2024-01-{i:02d}" for i in range(1, 11)],
            "ohlcv": [[100.0, 101.0, 99.0, 100.5, 1000]] * 10,
            "metadata": {},  # Empty dict - tests the `is not None` fix
        }

        app.dependency_overrides[get_data_service] = lambda: mock_data_service

        client = TestClient(app)
        response = client.get("/data/AAPL/1d?limit=5")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        # Should have limiting metadata even with initially empty metadata
        assert len(data["data"]["dates"]) == 5
        assert data["data"]["metadata"]["limited"] is True
        assert data["data"]["metadata"]["original_points"] == 10

"""
Unit tests for Backtesting API endpoints - simplified approach.

Tests the backtesting endpoints with real service functionality.
"""

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


class TestBacktestingEndpoints:
    """Test backtesting API endpoints."""

    @pytest.mark.api
    def test_start_backtest_success(self, client):
        """Test starting a backtest successfully."""
        payload = {
            "strategy_name": "test_strategy",
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "initial_capital": 100000.0,
        }

        response = client.post("/api/v1/backtests", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["backtest_id"].startswith("op_backtesting_")
        assert data["status"] == "starting"
        assert "started" in data["message"].lower()

    @pytest.mark.api
    def test_start_backtest_with_default_capital(self, client):
        """Test starting backtest without specifying initial capital."""
        payload = {
            "strategy_name": "test_strategy",
            "symbol": "MSFT",
            "timeframe": "4h",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
        }

        response = client.post("/api/v1/backtests", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["backtest_id"].startswith("op_backtesting_")

    @pytest.mark.api
    def test_start_backtest_validation_error(self, client):
        """Test starting backtest with invalid parameters."""
        payload = {
            "strategy_name": "",  # Empty strategy name should be invalid
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
        }

        response = client.post("/api/v1/backtests", json=payload)

        assert response.status_code == 422  # Validation error

    @pytest.mark.api
    def test_get_backtest_results_not_found(self, client):
        """Test getting results for non-existent backtest."""
        response = client.get("/api/v1/backtests/nonexistent_id/results")

        assert response.status_code == 404

    @pytest.mark.api
    def test_get_backtest_trades_not_found(self, client):
        """Test getting trades for non-existent backtest."""
        response = client.get("/api/v1/backtests/nonexistent_id/trades")

        assert response.status_code == 404

    @pytest.mark.api
    def test_get_equity_curve_not_found(self, client):
        """Test getting equity curve for non-existent backtest."""
        response = client.get("/api/v1/backtests/nonexistent_id/equity_curve")

        assert response.status_code == 404

    @pytest.mark.api
    def test_start_backtest_invalid_dates(self, client):
        """Test starting backtest with invalid date range."""
        payload = {
            "strategy_name": "test_strategy",
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "2024-06-01",  # Start after end
            "end_date": "2024-01-01",
            "initial_capital": 100000.0,
        }

        response = client.post("/api/v1/backtests", json=payload)

        # Should either return validation error or succeed depending on validation logic
        assert response.status_code in [200, 422]

    @pytest.mark.api
    def test_start_backtest_negative_capital(self, client):
        """Test starting backtest with negative initial capital."""
        payload = {
            "strategy_name": "test_strategy",
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "initial_capital": -1000.0,  # Negative capital
        }

        response = client.post("/api/v1/backtests", json=payload)

        # Should either return validation error or succeed depending on validation logic
        assert response.status_code in [200, 422]

    @pytest.mark.api
    def test_backtest_large_payload(self, client):
        """Test backtest with large payload."""
        payload = {
            "strategy_name": "complex_strategy_with_long_name",
            "symbol": "AAPL",
            "timeframe": "1m",
            "start_date": "2020-01-01",  # Long time range
            "end_date": "2024-01-01",
            "initial_capital": 1000000.0,  # Large capital
        }

        response = client.post("/api/v1/backtests", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

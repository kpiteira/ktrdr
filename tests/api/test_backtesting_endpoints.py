"""
Unit tests for Backtesting API endpoints.

Tests the backtesting endpoints following async operations architecture.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_backtesting_service():
    """Create a mock BacktestingService for testing endpoints."""
    mock_instance = AsyncMock()
    # Mock the run_backtest method (new BacktestingService method)
    mock_instance.run_backtest = AsyncMock()
    return mock_instance


@pytest.fixture
def client_with_mocked_service(client, mock_backtesting_service):
    """Create a test client with mocked backtesting service."""
    from ktrdr.api.endpoints.backtesting import get_backtesting_service

    # Override the dependency
    client.app.dependency_overrides[get_backtesting_service] = (
        lambda: mock_backtesting_service
    )

    yield client

    # Clean up
    client.app.dependency_overrides.clear()


class TestBacktestingEndpoints:
    """Test backtesting API endpoints."""

    @pytest.mark.api
    def test_start_backtest_success(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test starting a backtest successfully."""
        mock_backtesting_service.run_backtest.return_value = {
            "success": True,
            "operation_id": "op_backtest_20250103_abc123",
            "status": "started",
            "message": "Backtest started for AAPL 1h",
            "symbol": "AAPL",
            "timeframe": "1h",
            "mode": "local",
        }

        payload = {
            "strategy_name": "test_strategy",
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "initial_capital": 100000.0,
        }

        response = client_with_mocked_service.post(
            "/api/v1/backtests/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "op_backtest_20250103_abc123"
        assert data["status"] == "started"
        assert data["message"] == "Backtest started for AAPL 1h"
        assert data["symbol"] == "AAPL"
        assert data["timeframe"] == "1h"

        # Verify service was called with correct parameters
        # (strategy_name auto-converted to paths internally)
        mock_backtesting_service.run_backtest.assert_called_once()
        call_kwargs = mock_backtesting_service.run_backtest.call_args[1]
        assert call_kwargs["symbol"] == "AAPL"
        assert call_kwargs["timeframe"] == "1h"
        assert call_kwargs["strategy_config_path"] == "strategies/test_strategy.yaml"
        assert call_kwargs["model_path"] is None  # Not provided in request
        assert isinstance(call_kwargs["start_date"], datetime)
        assert isinstance(call_kwargs["end_date"], datetime)
        assert call_kwargs["initial_capital"] == 100000.0

    @pytest.mark.api
    def test_start_backtest_with_defaults(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test starting backtest with default initial capital."""
        mock_backtesting_service.run_backtest.return_value = {
            "success": True,
            "operation_id": "op_backtest_67890",
            "status": "started",
            "message": "Backtest started for MSFT 1d",
            "symbol": "MSFT",
            "timeframe": "1d",
            "mode": "local",
        }

        payload = {
            "strategy_name": "momentum_strategy",
            "symbol": "MSFT",
            "timeframe": "1d",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            # initial_capital not provided, should use default (100000.0)
        }

        response = client_with_mocked_service.post(
            "/api/v1/backtests/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "op_backtest_67890"

        # Verify default initial capital was used
        call_kwargs = mock_backtesting_service.run_backtest.call_args[1]
        assert call_kwargs["initial_capital"] == 100000.0

    @pytest.mark.api
    def test_start_backtest_validation_error_empty_string(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test starting backtest with empty strategy name."""
        payload = {
            "strategy_name": "",  # Empty string should be invalid
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
        }

        response = client_with_mocked_service.post(
            "/api/v1/backtests/start", json=payload
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.api
    def test_start_backtest_missing_required_field(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test starting backtest with missing required fields."""
        payload = {
            "strategy_name": "test_strategy",
            # Missing symbol, timeframe, dates
        }

        response = client_with_mocked_service.post(
            "/api/v1/backtests/start", json=payload
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.api
    def test_start_backtest_invalid_date_format(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test starting backtest with invalid date format."""
        payload = {
            "strategy_name": "test_strategy",
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "invalid-date",  # Invalid format
            "end_date": "2024-06-01",
        }

        response = client_with_mocked_service.post(
            "/api/v1/backtests/start", json=payload
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.api
    def test_start_backtest_service_error(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test handling service errors during backtest start."""
        from ktrdr.errors import ValidationError

        mock_backtesting_service.run_backtest.side_effect = ValidationError(
            "Strategy configuration invalid"
        )

        payload = {
            "strategy_name": "invalid_strategy",
            "symbol": "AAPL",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
        }

        response = client_with_mocked_service.post(
            "/api/v1/backtests/start", json=payload
        )

        assert response.status_code == 400
        assert "Strategy configuration invalid" in str(response.json()["detail"])

    @pytest.mark.api
    def test_start_backtest_with_commission_and_slippage(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test starting backtest with custom commission and slippage."""
        mock_backtesting_service.run_backtest.return_value = {
            "success": True,
            "operation_id": "op_backtest_custom",
            "status": "started",
            "message": "Backtest started for EURUSD 4h",
            "symbol": "EURUSD",
            "timeframe": "4h",
            "mode": "local",
        }

        payload = {
            "strategy_name": "forex_strategy",
            "symbol": "EURUSD",
            "timeframe": "4h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "initial_capital": 50000.0,
            "commission": 0.002,
            "slippage": 0.0015,
        }

        response = client_with_mocked_service.post(
            "/api/v1/backtests/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify commission and slippage were passed
        call_kwargs = mock_backtesting_service.run_backtest.call_args[1]
        assert call_kwargs["commission"] == 0.002
        assert call_kwargs["slippage"] == 0.0015


class TestBacktestingOptionalSymbolTimeframe:
    """Test optional symbol/timeframe behavior (extracted from strategy config)."""

    @pytest.mark.api
    def test_start_backtest_without_symbol_timeframe(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test starting backtest without symbol/timeframe (uses strategy config)."""
        from unittest.mock import patch

        mock_backtesting_service.run_backtest.return_value = {
            "success": True,
            "operation_id": "op_backtest_20250118_xyz",
            "status": "started",
            "message": "Backtest started for AAPL 1h",
            "symbol": "AAPL",
            "timeframe": "1h",
            "mode": "distributed",
        }

        payload = {
            "strategy_name": "test_strategy",
            # symbol and timeframe intentionally omitted
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "initial_capital": 100000.0,
        }

        # Mock strategy config extraction
        with patch(
            "ktrdr.api.endpoints.backtesting.extract_symbols_timeframes_from_strategy"
        ) as mock_extract:
            mock_extract.return_value = (["AAPL"], ["1h"])

            response = client_with_mocked_service.post(
                "/api/v1/backtests/start", json=payload
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "op_backtest_20250118_xyz"

        # Verify service was called with resolved symbol/timeframe
        call_kwargs = mock_backtesting_service.run_backtest.call_args[1]
        assert call_kwargs["symbol"] == "AAPL"
        assert call_kwargs["timeframe"] == "1h"

    @pytest.mark.api
    def test_start_backtest_with_symbol_only(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test starting backtest with only symbol (timeframe from strategy)."""
        from unittest.mock import patch

        mock_backtesting_service.run_backtest.return_value = {
            "success": True,
            "operation_id": "op_backtest_symbol_only",
            "status": "started",
            "message": "Backtest started for MSFT 1h",
            "symbol": "MSFT",
            "timeframe": "1h",
            "mode": "distributed",
        }

        payload = {
            "strategy_name": "momentum_strategy",
            "symbol": "MSFT",
            # timeframe intentionally omitted
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
        }

        # Mock strategy config extraction (only timeframe will be used)
        with patch(
            "ktrdr.api.endpoints.backtesting.extract_symbols_timeframes_from_strategy"
        ) as mock_extract:
            mock_extract.return_value = (["AAPL"], ["1h"])

            response = client_with_mocked_service.post(
                "/api/v1/backtests/start", json=payload
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify service was called with request symbol and config timeframe
        call_kwargs = mock_backtesting_service.run_backtest.call_args[1]
        assert call_kwargs["symbol"] == "MSFT"  # From request
        assert call_kwargs["timeframe"] == "1h"  # From config

    @pytest.mark.api
    def test_start_backtest_with_timeframe_only(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test starting backtest with only timeframe (symbol from strategy)."""
        from unittest.mock import patch

        mock_backtesting_service.run_backtest.return_value = {
            "success": True,
            "operation_id": "op_backtest_tf_only",
            "status": "started",
            "message": "Backtest started for AAPL 4h",
            "symbol": "AAPL",
            "timeframe": "4h",
            "mode": "distributed",
        }

        payload = {
            "strategy_name": "momentum_strategy",
            # symbol intentionally omitted
            "timeframe": "4h",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
        }

        # Mock strategy config extraction (only symbol will be used)
        with patch(
            "ktrdr.api.endpoints.backtesting.extract_symbols_timeframes_from_strategy"
        ) as mock_extract:
            mock_extract.return_value = (["AAPL"], ["1h"])

            response = client_with_mocked_service.post(
                "/api/v1/backtests/start", json=payload
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify service was called with config symbol and request timeframe
        call_kwargs = mock_backtesting_service.run_backtest.call_args[1]
        assert call_kwargs["symbol"] == "AAPL"  # From config
        assert call_kwargs["timeframe"] == "4h"  # From request

    @pytest.mark.api
    def test_start_backtest_configuration_error_when_strategy_has_no_symbols(
        self, client_with_mocked_service, mock_backtesting_service
    ):
        """Test 400 response when strategy config is missing symbols/timeframes."""
        from unittest.mock import patch

        from ktrdr.errors import ConfigurationError

        payload = {
            "strategy_name": "invalid_strategy",
            # symbol and timeframe intentionally omitted
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
        }

        # Mock strategy config extraction to raise ConfigurationError
        with patch(
            "ktrdr.api.endpoints.backtesting.extract_symbols_timeframes_from_strategy"
        ) as mock_extract:
            mock_extract.side_effect = ConfigurationError(
                message="Strategy 'invalid_strategy' has no symbols configured",
                error_code="STRATEGY-NoSymbols",
            )

            response = client_with_mocked_service.post(
                "/api/v1/backtests/start", json=payload
            )

        assert response.status_code == 400
        assert "no symbols configured" in str(response.json()["detail"]).lower()


class TestBacktestStartRequestModel:
    """Test BacktestStartRequest Pydantic model."""

    def test_model_accepts_optional_symbol(self):
        """BacktestStartRequest accepts None for symbol."""
        from ktrdr.api.models.backtesting import BacktestStartRequest

        request = BacktestStartRequest(
            strategy_name="test_strategy",
            symbol=None,
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        assert request.symbol is None
        assert request.timeframe == "1h"

    def test_model_accepts_optional_timeframe(self):
        """BacktestStartRequest accepts None for timeframe."""
        from ktrdr.api.models.backtesting import BacktestStartRequest

        request = BacktestStartRequest(
            strategy_name="test_strategy",
            symbol="AAPL",
            timeframe=None,
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        assert request.symbol == "AAPL"
        assert request.timeframe is None

    def test_model_accepts_both_optional(self):
        """BacktestStartRequest accepts None for both symbol and timeframe."""
        from ktrdr.api.models.backtesting import BacktestStartRequest

        request = BacktestStartRequest(
            strategy_name="test_strategy",
            symbol=None,
            timeframe=None,
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        assert request.symbol is None
        assert request.timeframe is None

    def test_model_accepts_omitted_symbol_timeframe(self):
        """BacktestStartRequest works when symbol/timeframe are omitted entirely."""
        from ktrdr.api.models.backtesting import BacktestStartRequest

        request = BacktestStartRequest(
            strategy_name="test_strategy",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        assert request.symbol is None
        assert request.timeframe is None

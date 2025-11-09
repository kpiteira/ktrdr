"""Tests for BacktestWorker following training-host-service pattern."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType


@pytest.fixture
def mock_backtest_engine():
    """Mock BacktestingEngine."""
    with patch("ktrdr.backtesting.backtest_worker.BacktestingEngine") as mock:
        engine_instance = MagicMock()
        # Mock the run method to return a result object
        result_mock = MagicMock()
        result_mock.to_dict.return_value = {
            "total_return": 0.25,
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.10,
            "total_trades": 42,
            "win_rate": 0.60,
            "result_summary": {"return": "25%", "sharpe": "1.5"},
        }
        engine_instance.run.return_value = result_mock
        mock.return_value = engine_instance
        yield mock


@pytest.fixture
def mock_asyncio_to_thread():
    """Mock asyncio.to_thread."""

    async def mock_to_thread(func, *args, **kwargs):
        # Call the function synchronously in tests
        return func(*args, **kwargs)

    with patch("asyncio.to_thread", side_effect=mock_to_thread):
        yield


class TestBacktestWorker:
    """Test BacktestWorker implementation."""

    def test_worker_initialization(self):
        """Test BacktestWorker initializes correctly."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        worker = BacktestWorker(worker_port=5003, backend_url="http://backend:8000")

        assert worker.worker_type == WorkerType.BACKTESTING
        assert worker.operation_type == OperationType.BACKTESTING
        assert worker.worker_port == 5003
        assert worker._operations_service is not None

    def test_backtest_start_endpoint_exists(self):
        """Test /backtests/start endpoint is registered."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        worker = BacktestWorker()
        client = TestClient(worker.app)

        # Test endpoint exists (should return 422 for missing body)
        response = client.post("/backtests/start")
        assert (
            response.status_code == 422
        )  # Unprocessable entity (missing request body)

    @pytest.mark.asyncio
    async def test_backtest_start_generates_operation_id_if_not_provided(
        self, mock_backtest_engine, mock_asyncio_to_thread
    ):
        """Test operation_id is generated if task_id not provided."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        worker = BacktestWorker()
        client = TestClient(worker.app)

        request_data = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "strategy_name": "test_strategy",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000.0,
        }

        response = client.post("/backtests/start", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "operation_id" in data
        assert data["operation_id"].startswith("worker_backtest_")
        assert data["status"] == "started"

    @pytest.mark.asyncio
    async def test_backtest_start_uses_provided_task_id(
        self, mock_backtest_engine, mock_asyncio_to_thread
    ):
        """Test operation_id uses provided task_id (ID synchronization)."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        worker = BacktestWorker()
        client = TestClient(worker.app)

        request_data = {
            "task_id": "backend_op_12345",  # Backend provides this
            "symbol": "EURUSD",
            "timeframe": "1h",
            "strategy_name": "test_strategy",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }

        response = client.post("/backtests/start", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "backend_op_12345"  # Same ID returned!

    @pytest.mark.asyncio
    async def test_backtest_creates_operation_in_operations_service(
        self, mock_backtest_engine, mock_asyncio_to_thread
    ):
        """Test backtest creates operation in worker's OperationsService."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        worker = BacktestWorker()
        client = TestClient(worker.app)

        request_data = {
            "task_id": "test_op_123",
            "symbol": "GBPUSD",
            "timeframe": "4h",
            "strategy_name": "test_strategy",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }

        response = client.post("/backtests/start", json=request_data)
        assert response.status_code == 200

        # Verify operation was created in OperationsService
        operation = await worker._operations_service.get_operation("test_op_123")
        assert operation is not None
        assert operation.operation_id == "test_op_123"
        assert operation.operation_type == OperationType.BACKTESTING
        assert operation.metadata.symbol == "GBPUSD"
        assert operation.metadata.timeframe == "4h"

    @pytest.mark.asyncio
    async def test_backtest_engine_is_called_with_correct_config(
        self, mock_backtest_engine, mock_asyncio_to_thread
    ):
        """Test BacktestingEngine is called with correct configuration."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        worker = BacktestWorker()
        client = TestClient(worker.app)

        request_data = {
            "symbol": "USDJPY",
            "timeframe": "1d",
            "strategy_name": "neuro_mean_reversion",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 50000.0,
            "commission": 0.002,
            "slippage": 0.001,
        }

        response = client.post("/backtests/start", json=request_data)
        assert response.status_code == 200

        # Verify BacktestingEngine was called
        assert mock_backtest_engine.called
        config_arg = mock_backtest_engine.call_args[1]["config"]
        assert config_arg.symbol == "USDJPY"
        assert config_arg.timeframe == "1d"
        assert config_arg.initial_capital == 50000.0
        assert config_arg.commission == 0.002
        assert config_arg.slippage == 0.001

    @pytest.mark.asyncio
    async def test_backtest_completes_operation_on_success(
        self, mock_backtest_engine, mock_asyncio_to_thread
    ):
        """Test operation is marked completed on successful backtest."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        worker = BacktestWorker()
        client = TestClient(worker.app)

        request_data = {
            "task_id": "test_complete_op",
            "symbol": "AAPL",
            "timeframe": "1h",
            "strategy_name": "test_strategy",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        response = client.post("/backtests/start", json=request_data)
        assert response.status_code == 200

        # Verify operation completed
        operation = await worker._operations_service.get_operation("test_complete_op")
        assert operation.status.value in ["completed", "running"]  # May complete async

    @pytest.mark.asyncio
    async def test_backtest_returns_result_summary(
        self, mock_backtest_engine, mock_asyncio_to_thread
    ):
        """Test backtest returns result summary."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        worker = BacktestWorker()
        client = TestClient(worker.app)

        request_data = {
            "symbol": "EURUSD",
            "timeframe": "1d",
            "strategy_name": "test_strategy",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }

        response = client.post("/backtests/start", json=request_data)
        assert response.status_code == 200
        data = response.json()

        assert "result_summary" in data
        assert isinstance(data["result_summary"], dict)

    @pytest.mark.asyncio
    async def test_backtest_fails_operation_on_exception(
        self, mock_backtest_engine, mock_asyncio_to_thread
    ):
        """Test operation is marked failed on exception."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        # Make engine raise exception
        mock_backtest_engine.return_value.run.side_effect = Exception("Test error")

        worker = BacktestWorker()
        client = TestClient(worker.app)

        request_data = {
            "task_id": "test_fail_op",
            "symbol": "AAPL",
            "timeframe": "1d",
            "strategy_name": "test_strategy",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }

        # Should raise exception
        with pytest.raises(Exception, match="Test error"):
            client.post("/backtests/start", json=request_data)

        # Verify operation failed
        operation = await worker._operations_service.get_operation("test_fail_op")
        assert operation.status.value == "failed"

    def test_worker_forces_local_mode(self):
        """Test worker forces USE_REMOTE_BACKTEST_SERVICE=false."""
        import os

        from ktrdr.backtesting.backtest_worker import BacktestWorker

        # Set to true initially
        os.environ["USE_REMOTE_BACKTEST_SERVICE"] = "true"

        BacktestWorker()  # Create worker (forces env var to false)

        # Should be forced to false
        assert os.environ.get("USE_REMOTE_BACKTEST_SERVICE") == "false"

    def test_worker_app_is_fastapi_instance(self):
        """Test worker exports FastAPI app for uvicorn."""
        from fastapi import FastAPI

        from ktrdr.backtesting.backtest_worker import app, worker

        assert isinstance(app, FastAPI)
        assert app is worker.app

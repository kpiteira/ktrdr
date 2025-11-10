"""
Unit tests for BacktestingService.

Tests the service orchestration layer for backtesting operations,
following the pull-based operations architecture pattern with ServiceOrchestrator.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.workers import WorkerStatus, WorkerType
from ktrdr.api.services.worker_registry import WorkerRegistry
from ktrdr.backtesting.backtesting_service import BacktestingService
from ktrdr.backtesting.progress_bridge import BacktestProgressBridge


@pytest.fixture
def worker_registry():
    """Create WorkerRegistry for testing."""
    return WorkerRegistry()


@pytest.fixture
def backtest_service(worker_registry):
    """Create BacktestingService instance for testing (distributed-only mode)."""
    return BacktestingService(worker_registry=worker_registry)


class TestBacktestingServiceInitialization:
    """Test BacktestingService initialization and configuration (distributed-only)."""

    def test_init_inherits_from_service_orchestrator(self, backtest_service):
        """Test service properly inherits from ServiceOrchestrator."""
        from ktrdr.async_infrastructure import ServiceOrchestrator

        assert isinstance(backtest_service, ServiceOrchestrator)
        assert hasattr(backtest_service, "operations_service")

    def test_init_implements_required_abstract_methods(self, backtest_service):
        """Test service implements all ServiceOrchestrator abstract methods."""
        # These should not raise NotImplementedError
        assert backtest_service._get_service_name() == "Backtesting"

    def test_init_requires_worker_registry(self):
        """Test service requires WorkerRegistry in distributed-only mode."""
        with pytest.raises(TypeError, match="worker_registry"):
            # Missing required parameter should raise TypeError
            BacktestingService()

    def test_init_with_worker_registry(self, worker_registry):
        """Test service initializes correctly with WorkerRegistry."""
        service = BacktestingService(worker_registry=worker_registry)

        assert service.worker_registry is worker_registry
        assert isinstance(service._operation_workers, dict)

    def test_init_logs_distributed_mode(self, worker_registry):
        """Test service logs distributed mode initialization."""
        with patch("ktrdr.backtesting.backtesting_service.logger") as mock_logger:
            BacktestingService(worker_registry=worker_registry)

            # Should log distributed mode message
            mock_logger.info.assert_called()
            logged_message = mock_logger.info.call_args[0][0]
            assert "distributed" in logged_message.lower() or "Backtesting service initialized" in logged_message


class TestBacktestingServiceDistributedMode:
    """Test distributed mode backtest execution (workers-only)."""

    @pytest.mark.asyncio
    async def test_run_backtest_creates_operation_via_orchestrator(
        self, backtest_service
    ):
        """Test run_backtest uses ServiceOrchestrator's start_managed_operation."""
        with patch.object(
            backtest_service, "start_managed_operation", new_callable=AsyncMock
        ) as mock_start:
            mock_start.return_value = {
                "operation_id": "op_test_123",
                "status": "started",
                "message": "Test operation started",
            }

            result = await backtest_service.run_backtest(
                symbol="AAPL",
                timeframe="1h",
                strategy_config_path="strategies/test.yaml",
                model_path="models/test.pt",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            )

            # Verify start_managed_operation was called
            mock_start.assert_called_once()
            assert result["operation_id"] == "op_test_123"
            assert result["status"] == "started"


class TestBacktestingServiceWorkerDispatch:
    """Test backtest dispatch to workers."""

    @pytest.mark.asyncio
    async def test_run_backtest_on_worker_registers_proxy(self, backtest_service, worker_registry):
        """Test run_backtest_on_worker registers OperationServiceProxy."""
        operation_id = "op_test_123"
        remote_operation_id = "remote_op_456"

        # Register a worker
        worker_registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        with patch(
            "ktrdr.backtesting.backtesting_service.httpx.AsyncClient"
        ) as MockClient:
            with patch("ktrdr.backtesting.backtesting_service.OperationServiceProxy"):
                # Mock HTTP response from remote service
                mock_response = MagicMock()
                mock_response.json.return_value = {"operation_id": remote_operation_id}
                mock_response.raise_for_status = MagicMock()

                mock_client = MockClient.return_value.__aenter__.return_value
                mock_client.post = AsyncMock(return_value=mock_response)

                # Mock operations service
                mock_ops = MagicMock()
                mock_ops.register_remote_proxy = MagicMock()
                backtest_service.operations_service = mock_ops

                await backtest_service.run_backtest_on_worker(
                    operation_id=operation_id,
                    symbol="AAPL",
                    timeframe="1h",
                    strategy_config_path="strategies/test.yaml",
                    model_path="models/test.pt",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 12, 31),
                    initial_capital=100000.0,
                )

                # Verify proxy was registered
                mock_ops.register_remote_proxy.assert_called_once()


class TestBacktestingServiceErrorHandling:
    """Test error handling and validation."""

    @pytest.mark.asyncio
    async def test_run_backtest_validates_required_parameters(self, backtest_service):
        """Test run_backtest validates required parameters."""
        with pytest.raises(TypeError):
            # Missing required parameters should raise TypeError
            await backtest_service.run_backtest(symbol="AAPL")



class TestBacktestingServiceWorkerRegistry:
    """Test WorkerRegistry integration for distributed backtesting."""

    def test_init_accepts_worker_registry(self):
        """Test BacktestingService can be initialized with WorkerRegistry."""
        registry = WorkerRegistry()
        service = BacktestingService(worker_registry=registry)

        assert service.worker_registry is registry
        assert isinstance(service._operation_workers, dict)


    @pytest.mark.asyncio
    async def test_worker_dispatch_selects_worker_from_registry(self):
        """Test backtest dispatch selects worker from WorkerRegistry."""
        # Create registry and register a worker
        registry = WorkerRegistry()
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Create service with registry
        service = BacktestingService(worker_registry=registry)

        operation_id = "op_test_123"
        remote_operation_id = "remote_op_456"

        with patch(
            "ktrdr.backtesting.backtesting_service.httpx.AsyncClient"
        ) as MockClient:
            with patch("ktrdr.backtesting.backtesting_service.OperationServiceProxy"):
                # Mock HTTP response from remote service
                mock_response = MagicMock()
                mock_response.json.return_value = {"operation_id": remote_operation_id}
                mock_response.raise_for_status = MagicMock()

                mock_client = MockClient.return_value.__aenter__.return_value
                mock_client.post = AsyncMock(return_value=mock_response)

                # Mock operations service
                mock_ops = MagicMock()
                mock_ops.register_remote_proxy = MagicMock()
                service.operations_service = mock_ops

                result = await service.run_backtest_on_worker(
                    operation_id=operation_id,
                    symbol="AAPL",
                    timeframe="1h",
                    strategy_config_path="strategies/test.yaml",
                    model_path="models/test.pt",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 12, 31),
                    initial_capital=100000.0,
                )

                # Verify worker was selected and used
                assert result["worker_id"] == "worker-1"
                # Verify HTTP request went to worker's endpoint
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert call_args[0][0] == "http://worker-1:5003/backtests/start"

    @pytest.mark.asyncio
    async def test_worker_dispatch_marks_worker_busy(self):
        """Test backtest dispatch marks worker as busy."""
        # Create registry and register a worker
        registry = WorkerRegistry()
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Create service with registry
        service = BacktestingService(worker_registry=registry)

        operation_id = "op_test_123"
        remote_operation_id = "remote_op_456"

        with patch(
            "ktrdr.backtesting.backtesting_service.httpx.AsyncClient"
        ) as MockClient:
            with patch("ktrdr.backtesting.backtesting_service.OperationServiceProxy"):
                # Mock HTTP response
                mock_response = MagicMock()
                mock_response.json.return_value = {"operation_id": remote_operation_id}
                mock_response.raise_for_status = MagicMock()

                mock_client = MockClient.return_value.__aenter__.return_value
                mock_client.post = AsyncMock(return_value=mock_response)

                # Mock operations service
                mock_ops = MagicMock()
                service.operations_service = mock_ops

                # Worker should start as AVAILABLE
                worker = registry.get_worker("worker-1")
                assert worker.status == WorkerStatus.AVAILABLE

                await service.run_backtest_on_worker(
                    operation_id=operation_id,
                    symbol="AAPL",
                    timeframe="1h",
                    strategy_config_path="strategies/test.yaml",
                    model_path="models/test.pt",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 12, 31),
                    initial_capital=100000.0,
                )

                # Worker should now be BUSY
                assert worker.status == WorkerStatus.BUSY
                assert worker.current_operation_id == operation_id

                # Mapping should be stored
                assert service._operation_workers[operation_id] == "worker-1"

    @pytest.mark.asyncio
    async def test_worker_dispatch_raises_when_no_workers_available(self):
        """Test backtest dispatch raises error when no workers available (distributed-only mode)."""
        # Create registry with no workers
        registry = WorkerRegistry()

        # Create service with registry
        service = BacktestingService(worker_registry=registry)

        operation_id = "op_test_123"

        # Mock operations service
        mock_ops = MagicMock()
        service.operations_service = mock_ops

        with pytest.raises(
            RuntimeError,
            match="No available backtest workers",
        ):
            await service.run_backtest_on_worker(
                operation_id=operation_id,
                symbol="AAPL",
                timeframe="1h",
                strategy_config_path="strategies/test.yaml",
                model_path="models/test.pt",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                initial_capital=100000.0,
            )

    def test_cleanup_worker_marks_available(self):
        """Test cleanup_worker marks worker as available."""
        # Create registry and register a worker
        registry = WorkerRegistry()
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        service = BacktestingService(worker_registry=registry)

        # Mark worker as busy
        operation_id = "op_test_123"
        registry.mark_busy("worker-1", operation_id)
        service._operation_workers[operation_id] = "worker-1"

        # Verify worker is busy
        worker = registry.get_worker("worker-1")
        assert worker.status == WorkerStatus.BUSY

        # Cleanup
        service.cleanup_worker(operation_id)

        # Verify worker is available
        assert worker.status == WorkerStatus.AVAILABLE
        assert worker.current_operation_id is None

        # Verify mapping is removed
        assert operation_id not in service._operation_workers

    def test_cleanup_worker_handles_missing_operation(self):
        """Test cleanup_worker handles missing operation gracefully."""
        registry = WorkerRegistry()
        service = BacktestingService(worker_registry=registry)

        # Should not raise error for nonexistent operation
        service.cleanup_worker("nonexistent_op")


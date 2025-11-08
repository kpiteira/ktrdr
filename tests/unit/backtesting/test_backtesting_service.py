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
def backtest_service():
    """Create BacktestingService instance for testing."""
    return BacktestingService()


class TestBacktestingServiceInitialization:
    """Test BacktestingService initialization and configuration."""

    def test_init_inherits_from_service_orchestrator(self, backtest_service):
        """Test service properly inherits from ServiceOrchestrator."""
        from ktrdr.async_infrastructure import ServiceOrchestrator

        assert isinstance(backtest_service, ServiceOrchestrator)
        assert hasattr(backtest_service, "operations_service")

    def test_init_implements_required_abstract_methods(self, backtest_service):
        """Test service implements all ServiceOrchestrator abstract methods."""
        # These should not raise NotImplementedError
        assert backtest_service._get_service_name() == "Backtesting"
        assert backtest_service._get_default_host_url() == "http://localhost:5003"
        assert backtest_service._get_env_var_prefix() == "BACKTEST"

    def test_init_detects_local_mode_by_default(self):
        """Test service defaults to local mode when env var not set."""
        with patch.dict("os.environ", {}, clear=True):
            service = BacktestingService()
            assert service._use_remote is False

    def test_init_detects_remote_mode_when_enabled(self):
        """Test service detects remote mode when env var is true."""
        with patch.dict("os.environ", {"USE_REMOTE_BACKTEST_SERVICE": "true"}):
            service = BacktestingService()
            assert service._use_remote is True

    def test_get_remote_service_url_default(self):
        """Test getting default remote service URL."""
        with patch.dict("os.environ", {}, clear=True):
            service = BacktestingService()
            url = service._get_remote_service_url()
            assert url == "http://localhost:5003"

    def test_get_remote_service_url_custom(self):
        """Test getting custom remote service URL from env var."""
        custom_url = "http://backtest-worker:5003"
        with patch.dict("os.environ", {"REMOTE_BACKTEST_SERVICE_URL": custom_url}):
            service = BacktestingService()
            url = service._get_remote_service_url()
            assert url == custom_url


class TestBacktestingServiceLocalMode:
    """Test local mode backtest execution."""

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

    @pytest.mark.asyncio
    async def test_run_backtest_routes_to_local_when_configured(self):
        """Test run_backtest routes to local execution in local mode."""
        with patch.dict("os.environ", {"USE_REMOTE_BACKTEST_SERVICE": "false"}):
            service = BacktestingService()

            with patch.object(service, "_run_local_backtest", new_callable=AsyncMock):
                with patch.object(
                    service, "start_managed_operation", new_callable=AsyncMock
                ) as mock_start:
                    mock_start.return_value = {
                        "operation_id": "op_test_123",
                        "status": "started",
                    }

                    await service.run_backtest(
                        symbol="AAPL",
                        timeframe="1h",
                        strategy_config_path="strategies/test.yaml",
                        model_path="models/test.pt",
                        start_date=datetime(2024, 1, 1),
                        end_date=datetime(2024, 12, 31),
                    )

                    # Verify local method was called via the operation function
                    # (it will be called indirectly through start_managed_operation)
                    assert mock_start.called

    @pytest.mark.asyncio
    async def test_local_backtest_creates_and_registers_bridge(self, backtest_service):
        """Test local backtest creates BacktestProgressBridge and registers it."""
        operation_id = "op_test_123"

        # Mock BacktestingEngine
        with patch("ktrdr.backtesting.backtesting_service.BacktestingEngine"):
            with patch(
                "ktrdr.backtesting.backtesting_service.asyncio.to_thread",
                new_callable=AsyncMock,
            ) as mock_to_thread:
                mock_results = MagicMock()
                mock_results.to_dict.return_value = {"total_return": 0.15}
                mock_to_thread.return_value = mock_results

                # Mock operations service
                mock_ops = MagicMock()
                mock_ops.register_local_bridge = MagicMock()
                backtest_service.operations_service = mock_ops

                await backtest_service._run_local_backtest(
                    operation_id=operation_id,
                    symbol="AAPL",
                    timeframe="1h",
                    strategy_config_path="strategies/test.yaml",
                    model_path="models/test.pt",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 12, 31),
                    initial_capital=100000.0,
                )

                # Verify bridge was registered
                mock_ops.register_local_bridge.assert_called_once()
                call_args = mock_ops.register_local_bridge.call_args
                assert call_args[0][0] == operation_id
                assert isinstance(call_args[0][1], BacktestProgressBridge)

    @pytest.mark.asyncio
    async def test_local_backtest_runs_engine_in_thread(self, backtest_service):
        """Test local backtest runs BacktestingEngine in thread pool."""
        operation_id = "op_test_123"

        with patch("ktrdr.backtesting.backtesting_service.BacktestingEngine"):
            with patch(
                "ktrdr.backtesting.backtesting_service.asyncio.to_thread",
                new_callable=AsyncMock,
            ) as mock_to_thread:
                mock_results = MagicMock()
                mock_results.to_dict.return_value = {"total_return": 0.15}
                mock_to_thread.return_value = mock_results

                # Mock operations service
                mock_ops = MagicMock()
                mock_ops.register_local_bridge = MagicMock()
                backtest_service.operations_service = mock_ops

                result = await backtest_service._run_local_backtest(
                    operation_id=operation_id,
                    symbol="AAPL",
                    timeframe="1h",
                    strategy_config_path="strategies/test.yaml",
                    model_path="models/test.pt",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 12, 31),
                    initial_capital=100000.0,
                )

                # Verify engine was run in thread
                mock_to_thread.assert_called_once()
                # Verify results were returned
                assert result == {"total_return": 0.15}


class TestBacktestingServiceRemoteMode:
    """Test remote mode backtest execution (Phase 3)."""

    @pytest.mark.asyncio
    async def test_run_backtest_routes_to_remote_when_configured(self):
        """Test run_backtest routes to remote execution in remote mode."""
        with patch.dict("os.environ", {"USE_REMOTE_BACKTEST_SERVICE": "true"}):
            service = BacktestingService()

            with patch.object(
                service, "_run_remote_backtest", new_callable=AsyncMock
            ) as mock_remote:
                mock_remote.return_value = {"session_id": "test", "status": "started"}
                with patch.object(
                    service, "start_managed_operation", new_callable=AsyncMock
                ) as mock_start:
                    mock_start.return_value = {
                        "operation_id": "op_test_123",
                        "status": "started",
                    }

                    await service.run_backtest(
                        symbol="AAPL",
                        timeframe="1h",
                        strategy_config_path="strategies/test.yaml",
                        model_path="models/test.pt",
                        start_date=datetime(2024, 1, 1),
                        end_date=datetime(2024, 12, 31),
                    )

                    # Verify operation was created
                    assert mock_start.called

    @pytest.mark.asyncio
    async def test_remote_backtest_registers_proxy(self, backtest_service):
        """Test remote backtest registers OperationServiceProxy."""
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
                backtest_service.operations_service = mock_ops

                await backtest_service._run_remote_backtest(
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

    @pytest.mark.asyncio
    async def test_local_backtest_handles_engine_initialization_error(
        self, backtest_service
    ):
        """Test local backtest handles engine initialization errors gracefully."""
        operation_id = "op_test_123"

        with patch(
            "ktrdr.backtesting.backtesting_service.BacktestingEngine"
        ) as MockEngine:
            # Mock engine initialization failure
            MockEngine.side_effect = ValueError("Invalid configuration")

            # Mock operations service
            mock_ops = MagicMock()
            mock_ops.register_local_bridge = MagicMock()
            backtest_service.operations_service = mock_ops

            with pytest.raises(ValueError, match="Invalid configuration"):
                await backtest_service._run_local_backtest(
                    operation_id=operation_id,
                    symbol="AAPL",
                    timeframe="1h",
                    strategy_config_path="strategies/invalid.yaml",
                    model_path="models/test.pt",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 12, 31),
                    initial_capital=100000.0,
                )


class TestBacktestingServiceWorkerRegistry:
    """Test WorkerRegistry integration for distributed backtesting."""

    def test_init_accepts_worker_registry(self):
        """Test BacktestingService can be initialized with WorkerRegistry."""
        registry = WorkerRegistry()
        service = BacktestingService(worker_registry=registry)

        assert service.worker_registry is registry
        assert isinstance(service._operation_workers, dict)

    def test_init_without_registry_uses_none(self):
        """Test BacktestingService works without WorkerRegistry (backward compat)."""
        service = BacktestingService()

        assert service.worker_registry is None

    @pytest.mark.asyncio
    async def test_remote_backtest_selects_worker_from_registry(self):
        """Test remote backtest selects worker from WorkerRegistry."""
        # Create registry and register a worker
        registry = WorkerRegistry()
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Create service with registry
        with patch.dict("os.environ", {"USE_REMOTE_BACKTEST_SERVICE": "true"}):
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

                result = await service._run_remote_backtest(
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
    async def test_remote_backtest_marks_worker_busy(self):
        """Test remote backtest marks worker as busy."""
        # Create registry and register a worker
        registry = WorkerRegistry()
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Create service with registry
        with patch.dict("os.environ", {"USE_REMOTE_BACKTEST_SERVICE": "true"}):
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

                await service._run_remote_backtest(
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
    async def test_remote_backtest_raises_when_no_workers_available(self):
        """Test remote backtest raises error when no workers available."""
        # Create registry with no workers
        registry = WorkerRegistry()

        # Create service with registry
        with patch.dict("os.environ", {"USE_REMOTE_BACKTEST_SERVICE": "true"}):
            service = BacktestingService(worker_registry=registry)

        operation_id = "op_test_123"

        # Mock operations service
        mock_ops = MagicMock()
        service.operations_service = mock_ops

        with pytest.raises(
            RuntimeError,
            match="No available backtest workers",
        ):
            await service._run_remote_backtest(
                operation_id=operation_id,
                symbol="AAPL",
                timeframe="1h",
                strategy_config_path="strategies/test.yaml",
                model_path="models/test.pt",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                initial_capital=100000.0,
            )

    @pytest.mark.asyncio
    async def test_remote_backtest_fallback_to_hardcoded_url_without_registry(self):
        """Test remote backtest falls back to hardcoded URL without registry."""
        # Create service without registry
        with patch.dict("os.environ", {"USE_REMOTE_BACKTEST_SERVICE": "true"}):
            service = BacktestingService(worker_registry=None)

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

                result = await service._run_remote_backtest(
                    operation_id=operation_id,
                    symbol="AAPL",
                    timeframe="1h",
                    strategy_config_path="strategies/test.yaml",
                    model_path="models/test.pt",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 12, 31),
                    initial_capital=100000.0,
                )

                # Verify fallback to hardcoded URL
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert call_args[0][0] == "http://localhost:5003/backtests/start"

                # worker_id should be None in result
                assert result["worker_id"] is None

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

    def test_cleanup_worker_without_registry(self):
        """Test cleanup_worker works without registry."""
        service = BacktestingService(worker_registry=None)

        # Store a mapping (shouldn't happen in practice, but test it)
        service._operation_workers["op_test"] = "worker-1"

        # Should not raise error
        service.cleanup_worker("op_test")

        # Mapping should be removed
        assert "op_test" not in service._operation_workers

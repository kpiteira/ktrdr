"""End-to-end integration test for distributed worker architecture.

This test verifies the complete flow:
1. Backend starts with worker registry
2. Worker starts and self-registers
3. Backend sees the registered worker
4. Worker info can be retrieved
"""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.api.models.workers import WorkerStatus, WorkerType
from ktrdr.api.services.worker_registry import WorkerRegistry
from ktrdr.backtesting.worker_registration import WorkerRegistration


class TestWorkerEndToEnd:
    """End-to-end tests for distributed worker architecture."""

    @pytest.mark.asyncio
    async def test_single_worker_registration_flow(self):
        """Test complete flow: worker starts, registers, and can be queried."""
        # 1. Backend: Initialize worker registry (simulates backend startup)
        registry = WorkerRegistry()
        assert len(registry.list_workers()) == 0, "Registry should start empty"

        # 2. Worker: Configure worker environment
        with patch.dict(
            os.environ,
            {
                "WORKER_ID": "backtest-worker-1",
                "WORKER_PORT": "5003",
                "KTRDR_API_URL": "http://backend:8000",
            },
        ):
            # 3. Worker: Initialize worker registration
            worker_reg = WorkerRegistration()
            assert worker_reg.worker_id == "backtest-worker-1"
            assert worker_reg.worker_type == "backtesting"

            # 4. Worker: Simulate successful HTTP registration
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "worker_id": "backtest-worker-1",
                "worker_type": "backtesting",
                "endpoint_url": "http://backtest-worker-1:5003",
                "status": "available",
                "capabilities": worker_reg.get_capabilities(),
            }

            # Mock the HTTP call, but actually register in the registry
            async def mock_register(*args, **kwargs):
                # Simulate what the backend endpoint does
                json_data = kwargs.get("json", {})
                registry.register_worker(
                    worker_id=json_data["worker_id"],
                    worker_type=WorkerType(json_data["worker_type"]),
                    endpoint_url=json_data["endpoint_url"],
                    capabilities=json_data.get("capabilities"),
                )
                return mock_response

            with patch("httpx.AsyncClient.post", side_effect=mock_register):
                # 5. Worker: Perform registration
                success = await worker_reg.register()
                assert success is True, "Worker registration should succeed"

            # 6. Backend: Verify worker is registered
            workers = registry.list_workers()
            assert len(workers) == 1, "Should have exactly one registered worker"

            worker = workers[0]
            assert worker.worker_id == "backtest-worker-1"
            assert worker.worker_type == WorkerType.BACKTESTING
            assert worker.status == WorkerStatus.AVAILABLE
            assert "cores" in worker.capabilities
            assert "memory_gb" in worker.capabilities

            # 7. Backend: Retrieve specific worker by ID
            retrieved_worker = registry.get_worker("backtest-worker-1")
            assert retrieved_worker is not None
            assert retrieved_worker.worker_id == "backtest-worker-1"
            assert retrieved_worker.last_healthy_at is not None

            # 8. Backend: Filter workers by type
            backtest_workers = registry.list_workers(worker_type=WorkerType.BACKTESTING)
            assert len(backtest_workers) == 1
            assert backtest_workers[0].worker_id == "backtest-worker-1"

            # 9. Backend: Filter workers by status
            available_workers = registry.list_workers(status=WorkerStatus.AVAILABLE)
            assert len(available_workers) == 1
            assert available_workers[0].worker_id == "backtest-worker-1"

    @pytest.mark.asyncio
    async def test_multiple_workers_registration(self):
        """Test multiple workers can register and be queried."""
        # 1. Backend: Initialize registry
        registry = WorkerRegistry()

        # 2. Simulate three workers registering
        workers_config = [
            {
                "worker_id": "backtest-1",
                "worker_type": WorkerType.BACKTESTING,
                "endpoint_url": "http://backtest-1:5003",
            },
            {
                "worker_id": "backtest-2",
                "worker_type": WorkerType.BACKTESTING,
                "endpoint_url": "http://backtest-2:5003",
            },
            {
                "worker_id": "cpu-training-1",
                "worker_type": WorkerType.CPU_TRAINING,
                "endpoint_url": "http://cpu-training-1:5004",
            },
        ]

        for config in workers_config:
            registry.register_worker(**config)

        # 3. Verify all workers registered
        all_workers = registry.list_workers()
        assert len(all_workers) == 3

        # 4. Verify filtering by type
        backtest_workers = registry.list_workers(worker_type=WorkerType.BACKTESTING)
        assert len(backtest_workers) == 2
        backtest_ids = {w.worker_id for w in backtest_workers}
        assert backtest_ids == {"backtest-1", "backtest-2"}

        training_workers = registry.list_workers(worker_type=WorkerType.CPU_TRAINING)
        assert len(training_workers) == 1
        assert training_workers[0].worker_id == "cpu-training-1"

    @pytest.mark.asyncio
    async def test_worker_reregistration_updates_info(self):
        """Test that worker re-registration updates existing worker info."""
        # 1. Backend: Initialize registry
        registry = WorkerRegistry()

        # 2. Worker: Initial registration
        with patch.dict(
            os.environ,
            {
                "WORKER_ID": "backtest-1",
                "WORKER_PORT": "5003",
            },
        ):
            worker_reg = WorkerRegistration()

            # Mock first registration
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "worker_id": "backtest-1",
                "worker_type": "backtesting",
            }

            async def mock_register_v1(*args, **kwargs):
                json_data = kwargs.get("json", {})
                registry.register_worker(
                    worker_id=json_data["worker_id"],
                    worker_type=WorkerType(json_data["worker_type"]),
                    endpoint_url=json_data["endpoint_url"],
                    capabilities=json_data.get("capabilities"),
                )
                return mock_response

            with patch("httpx.AsyncClient.post", side_effect=mock_register_v1):
                await worker_reg.register()

            # Verify first registration
            assert len(registry.list_workers()) == 1
            worker_v1 = registry.get_worker("backtest-1")
            first_healthy_at = worker_v1.last_healthy_at

        # 3. Worker: Restart and re-register (simulate restart)
        await asyncio.sleep(0.1)  # Small delay to ensure timestamp differs

        with patch.dict(
            os.environ,
            {
                "WORKER_ID": "backtest-1",
                "WORKER_PORT": "5003",
            },
        ):
            worker_reg2 = WorkerRegistration()

            async def mock_register_v2(*args, **kwargs):
                json_data = kwargs.get("json", {})
                registry.register_worker(
                    worker_id=json_data["worker_id"],
                    worker_type=WorkerType(json_data["worker_type"]),
                    endpoint_url=json_data["endpoint_url"],
                    capabilities=json_data.get("capabilities"),
                )
                return mock_response

            with patch("httpx.AsyncClient.post", side_effect=mock_register_v2):
                await worker_reg2.register()

            # Verify still only one worker (idempotent)
            assert len(registry.list_workers()) == 1

            # Verify last_healthy_at was updated
            worker_v2 = registry.get_worker("backtest-1")
            assert worker_v2.last_healthy_at > first_healthy_at

    @pytest.mark.asyncio
    async def test_worker_registration_with_network_failure_retry(self):
        """Test worker retries registration on network failure."""
        registry = WorkerRegistry()

        with patch.dict(
            os.environ,
            {
                "WORKER_ID": "backtest-1",
                "WORKER_PORT": "5003",
            },
        ):
            # Configure worker with shorter retry parameters for faster test
            worker_reg = WorkerRegistration(max_retries=3, retry_delay=0.05)

            attempt_count = 0

            async def mock_flaky_register(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1

                # Fail first 2 attempts, succeed on 3rd
                if attempt_count < 3:
                    raise Exception("Connection refused")

                # Success on 3rd attempt
                json_data = kwargs.get("json", {})
                registry.register_worker(
                    worker_id=json_data["worker_id"],
                    worker_type=WorkerType(json_data["worker_type"]),
                    endpoint_url=json_data["endpoint_url"],
                    capabilities=json_data.get("capabilities"),
                )

                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "worker_id": "backtest-1",
                    "worker_type": "backtesting",
                }
                return mock_response

            with patch("httpx.AsyncClient.post", side_effect=mock_flaky_register):
                success = await worker_reg.register()

            # Verify registration eventually succeeded
            assert success is True
            assert attempt_count == 3, "Should have retried 3 times"
            assert len(registry.list_workers()) == 1

    @pytest.mark.asyncio
    async def test_worker_capabilities_detection(self):
        """Test that worker correctly detects and reports capabilities."""
        with patch.dict(
            os.environ,
            {
                "WORKER_ID": "backtest-1",
                "WORKER_PORT": "5003",
            },
        ):
            worker_reg = WorkerRegistration()
            capabilities = worker_reg.get_capabilities()

            # Verify expected capability fields
            assert "cores" in capabilities
            assert "memory_gb" in capabilities
            assert "platform" in capabilities
            assert "python_version" in capabilities

            # Verify types
            assert isinstance(capabilities["cores"], int)
            assert isinstance(capabilities["memory_gb"], (int, float))
            assert isinstance(capabilities["platform"], str)
            assert isinstance(capabilities["python_version"], str)

            # Verify reasonable values
            assert capabilities["cores"] > 0
            assert capabilities["memory_gb"] > 0

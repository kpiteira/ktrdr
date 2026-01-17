"""Integration tests for worker load balancing under concurrent operations.

This test suite verifies:
- Multiple workers can handle concurrent operations
- Load balancing distributes work evenly across workers
- Health checking works correctly with multiple workers
- Worker failures are handled gracefully
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from ktrdr.api.models.workers import WorkerStatus, WorkerType
from ktrdr.api.services.worker_registry import WorkerRegistry


class TestWorkerLoadBalancing:
    """Integration tests for worker load balancing."""

    @pytest.mark.asyncio
    async def test_concurrent_worker_selection(self):
        """Test that concurrent selections distribute across multiple workers."""
        registry = WorkerRegistry()

        # Register 3 workers
        for i in range(1, 4):
            registry.register_worker(
                worker_id=f"worker-{i}",
                worker_type=WorkerType.BACKTESTING,
                endpoint_url=f"http://worker-{i}:5003",
            )

        # Simulate 30 concurrent operations
        selections = []

        async def select_worker():
            worker = registry.select_worker(WorkerType.BACKTESTING)
            if worker:
                selections.append(worker.worker_id)
            await asyncio.sleep(0.01)  # Small delay to simulate work

        # Run concurrent selections
        await asyncio.gather(*[select_worker() for _ in range(30)])

        # Verify distribution is relatively even
        # With 30 operations and 3 workers, expect ~10 per worker
        from collections import Counter

        distribution = Counter(selections)

        assert len(distribution) == 3, "All 3 workers should be selected"

        # Each worker should get between 7-13 selections (allowing for variance)
        for worker_id, count in distribution.items():
            assert 7 <= count <= 13, (
                f"Worker {worker_id} got {count} selections, "
                f"expected 7-13 for even distribution"
            )

    @pytest.mark.asyncio
    async def test_load_balancing_with_busy_workers(self):
        """Test load balancing when some workers are busy."""
        registry = WorkerRegistry()

        # Register 5 workers
        for i in range(1, 6):
            registry.register_worker(
                worker_id=f"worker-{i}",
                worker_type=WorkerType.BACKTESTING,
                endpoint_url=f"http://worker-{i}:5003",
            )

        # Mark workers 1-3 as busy
        registry.mark_busy("worker-1", "op-1")
        registry.mark_busy("worker-2", "op-2")
        registry.mark_busy("worker-3", "op-3")

        # Select 10 workers
        selections = []
        for _ in range(10):
            worker = registry.select_worker(WorkerType.BACKTESTING)
            assert worker is not None
            selections.append(worker.worker_id)

        # Only workers 4 and 5 should be selected
        unique_selections = set(selections)
        assert unique_selections == {"worker-4", "worker-5"}

        # They should be distributed evenly
        from collections import Counter

        distribution = Counter(selections)
        assert distribution["worker-4"] == 5
        assert distribution["worker-5"] == 5

    @pytest.mark.asyncio
    async def test_worker_becomes_available_after_operation(self):
        """Test that workers become available after operations complete."""
        registry = WorkerRegistry()

        # Register 2 workers
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )
        registry.register_worker(
            worker_id="worker-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-2:5003",
        )

        # Select workers in sequence
        w1 = registry.select_worker(WorkerType.BACKTESTING)
        w2 = registry.select_worker(WorkerType.BACKTESTING)

        # Both should be different
        assert w1.worker_id != w2.worker_id

        # Mark both as busy
        registry.mark_busy(w1.worker_id, "op-1")
        registry.mark_busy(w2.worker_id, "op-2")

        # No workers available
        w3 = registry.select_worker(WorkerType.BACKTESTING)
        assert w3 is None

        # Mark w1 as available
        registry.mark_available(w1.worker_id)

        # Now w1 should be available again
        w4 = registry.select_worker(WorkerType.BACKTESTING)
        assert w4 is not None
        assert w4.worker_id == w1.worker_id

    @pytest.mark.asyncio
    async def test_health_check_with_multiple_workers(self):
        """Test health checking with multiple workers running."""
        registry = WorkerRegistry()
        registry._health_check_interval = 0.1  # Fast for testing

        # Register 3 workers
        for i in range(1, 4):
            registry.register_worker(
                worker_id=f"worker-{i}",
                worker_type=WorkerType.BACKTESTING,
                endpoint_url=f"http://worker-{i}:5003",
            )

        health_check_calls = []

        async def mock_health_check(worker_id):
            """Mock health check that tracks calls."""
            health_check_calls.append(worker_id)
            # Simulate worker-2 failing
            if worker_id == "worker-2":
                return False
            return True

        # Start background health checks
        with pytest.MonkeyPatch.context() as m:
            m.setattr(registry, "health_check_worker", mock_health_check)
            await registry.start()

            # Wait for a few health check rounds
            await asyncio.sleep(0.3)

            await registry.stop()

        # All workers should have been health checked
        assert "worker-1" in health_check_calls
        assert "worker-2" in health_check_calls
        assert "worker-3" in health_check_calls

    @pytest.mark.asyncio
    async def test_round_robin_fairness_over_time(self):
        """Test that round-robin selection is fair over many operations."""
        registry = WorkerRegistry()

        # Register 4 workers
        for i in range(1, 5):
            registry.register_worker(
                worker_id=f"worker-{i}",
                worker_type=WorkerType.BACKTESTING,
                endpoint_url=f"http://worker-{i}:5003",
            )

        # Select 100 workers
        selections = []
        for _ in range(100):
            worker = registry.select_worker(WorkerType.BACKTESTING)
            assert worker is not None
            selections.append(worker.worker_id)

        # Distribution should be very even (25 per worker)
        from collections import Counter

        distribution = Counter(selections)

        assert len(distribution) == 4
        for worker_id, count in distribution.items():
            # Each should get exactly 25 selections
            assert count == 25, f"Worker {worker_id} got {count}, expected 25"

    @pytest.mark.asyncio
    async def test_worker_failure_during_load(self):
        """Test system handles worker failures gracefully during load."""
        registry = WorkerRegistry()
        registry._removal_threshold_seconds = 1  # Fast for testing

        # Register 3 workers
        for i in range(1, 4):
            registry.register_worker(
                worker_id=f"worker-{i}",
                worker_type=WorkerType.BACKTESTING,
                endpoint_url=f"http://worker-{i}:5003",
            )

        # Simulate worker-2 becoming unhealthy
        worker_2 = registry.get_worker("worker-2")
        worker_2.status = WorkerStatus.TEMPORARILY_UNAVAILABLE
        worker_2.last_healthy_at = datetime.now(UTC) - timedelta(seconds=2)

        # Run cleanup
        registry._cleanup_dead_workers()

        # Worker-2 should be removed
        assert registry.get_worker("worker-2") is None

        # Remaining workers still available
        selections = []
        for _ in range(10):
            worker = registry.select_worker(WorkerType.BACKTESTING)
            assert worker is not None
            selections.append(worker.worker_id)

        # Only workers 1 and 3 should be selected
        unique_selections = set(selections)
        assert unique_selections == {"worker-1", "worker-3"}

    @pytest.mark.asyncio
    async def test_concurrent_operations_with_varying_duration(self):
        """Test load balancing with operations of varying duration."""
        registry = WorkerRegistry()

        # Register 3 workers
        for i in range(1, 4):
            registry.register_worker(
                worker_id=f"worker-{i}",
                worker_type=WorkerType.BACKTESTING,
                endpoint_url=f"http://worker-{i}:5003",
            )

        completed_operations = []
        operation_counter = [0]

        async def run_operation(duration: float):
            """Simulate an operation with given duration."""
            # Retry until we get a worker (simulates waiting for availability)
            worker = None
            for _ in range(10):
                worker = registry.select_worker(WorkerType.BACKTESTING)
                if worker:
                    break
                await asyncio.sleep(0.01)

            if not worker:
                return None

            # Mark busy
            op_id = f"op-{operation_counter[0]}"
            operation_counter[0] += 1
            registry.mark_busy(worker.worker_id, op_id)

            # Simulate work
            await asyncio.sleep(duration)

            # Mark available
            registry.mark_available(worker.worker_id)
            completed_operations.append(worker.worker_id)

            return worker.worker_id

        # Run 15 operations with varying durations
        durations = [0.01, 0.02, 0.03] * 5  # Mix of short and medium operations
        results = await asyncio.gather(*[run_operation(d) for d in durations])

        # All operations should complete with retry logic
        assert None not in results
        assert len(results) == 15

        # All workers should have been used
        unique_workers = set(results)
        assert len(unique_workers) == 3

        # Verify work was distributed (not perfectly even due to varying durations)
        from collections import Counter

        distribution = Counter(completed_operations)
        assert len(distribution) == 3

    @pytest.mark.asyncio
    async def test_no_workers_available_scenario(self):
        """Test behavior when no workers are available."""
        registry = WorkerRegistry()

        # Register 2 workers
        for i in range(1, 3):
            registry.register_worker(
                worker_id=f"worker-{i}",
                worker_type=WorkerType.BACKTESTING,
                endpoint_url=f"http://worker-{i}:5003",
            )

        # Mark both as busy
        registry.mark_busy("worker-1", "op-1")
        registry.mark_busy("worker-2", "op-2")

        # Try to select a worker
        worker = registry.select_worker(WorkerType.BACKTESTING)

        # Should return None when no workers available
        assert worker is None

        # Verify workers are still registered
        assert len(registry.list_workers()) == 2

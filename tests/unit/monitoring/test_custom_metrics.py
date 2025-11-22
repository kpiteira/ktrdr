"""Tests for custom Prometheus metrics.

This module tests the custom business metrics for KTRDR operations:
- Worker metrics (registered, available)
- Operation metrics (active, total, duration)
"""

from unittest.mock import MagicMock

from prometheus_client import REGISTRY

from ktrdr.api.models.workers import WorkerStatus, WorkerType
from ktrdr.monitoring.metrics import (
    increment_operations_total,
    operation_duration_seconds,
    operations_active,
    operations_total,
    record_operation_duration,
    reset_metrics,
    update_worker_metrics,
    workers_available,
    workers_registered,
)


class TestWorkerMetrics:
    """Tests for worker-related metrics."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics()

    def test_workers_registered_gauge_exists(self):
        """Test that workers_registered gauge is defined correctly."""
        # Check gauge can be set
        workers_registered.labels(worker_type="backtesting").set(3)
        workers_registered.labels(worker_type="training").set(2)

        # Verify values
        assert workers_registered.labels(worker_type="backtesting")._value.get() == 3
        assert workers_registered.labels(worker_type="training")._value.get() == 2

    def test_workers_available_gauge_exists(self):
        """Test that workers_available gauge is defined correctly."""
        # Check gauge can be set
        workers_available.labels(worker_type="backtesting").set(2)
        workers_available.labels(worker_type="training").set(1)

        # Verify values
        assert workers_available.labels(worker_type="backtesting")._value.get() == 2
        assert workers_available.labels(worker_type="training")._value.get() == 1

    def test_update_worker_metrics_registered(self):
        """Test update_worker_metrics updates registered count correctly."""
        # Simulate 3 backtest and 2 training workers
        workers = {
            "backtest-1": MagicMock(
                worker_type=WorkerType.BACKTESTING, status=WorkerStatus.AVAILABLE
            ),
            "backtest-2": MagicMock(
                worker_type=WorkerType.BACKTESTING, status=WorkerStatus.BUSY
            ),
            "backtest-3": MagicMock(
                worker_type=WorkerType.BACKTESTING, status=WorkerStatus.AVAILABLE
            ),
            "training-1": MagicMock(
                worker_type=WorkerType.TRAINING, status=WorkerStatus.AVAILABLE
            ),
            "training-2": MagicMock(
                worker_type=WorkerType.TRAINING, status=WorkerStatus.BUSY
            ),
        }

        update_worker_metrics(workers)

        # Verify registered counts
        assert workers_registered.labels(worker_type="backtesting")._value.get() == 3
        assert workers_registered.labels(worker_type="training")._value.get() == 2

    def test_update_worker_metrics_available(self):
        """Test update_worker_metrics updates available count correctly."""
        # Simulate workers with mixed statuses
        workers = {
            "backtest-1": MagicMock(
                worker_type=WorkerType.BACKTESTING, status=WorkerStatus.AVAILABLE
            ),
            "backtest-2": MagicMock(
                worker_type=WorkerType.BACKTESTING, status=WorkerStatus.BUSY
            ),
            "training-1": MagicMock(
                worker_type=WorkerType.TRAINING, status=WorkerStatus.AVAILABLE
            ),
            "training-2": MagicMock(
                worker_type=WorkerType.TRAINING, status=WorkerStatus.AVAILABLE
            ),
        }

        update_worker_metrics(workers)

        # Verify available counts (only AVAILABLE status)
        assert workers_available.labels(worker_type="backtesting")._value.get() == 1
        assert workers_available.labels(worker_type="training")._value.get() == 2

    def test_update_worker_metrics_empty(self):
        """Test update_worker_metrics handles empty workers dict."""
        update_worker_metrics({})

        # Both should be 0
        assert workers_registered.labels(worker_type="backtesting")._value.get() == 0
        assert workers_registered.labels(worker_type="training")._value.get() == 0
        assert workers_available.labels(worker_type="backtesting")._value.get() == 0
        assert workers_available.labels(worker_type="training")._value.get() == 0


class TestOperationMetrics:
    """Tests for operation-related metrics."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics()

    def test_operations_active_gauge_exists(self):
        """Test that operations_active gauge is defined correctly."""
        operations_active.set(5)
        assert operations_active._value.get() == 5

    def test_operations_total_counter_exists(self):
        """Test that operations_total counter is defined correctly."""
        # Counter should support labels
        operations_total.labels(operation_type="training", status="completed").inc()
        operations_total.labels(operation_type="backtesting", status="failed").inc()
        operations_total.labels(operation_type="training", status="completed").inc()

        # Verify counts
        assert (
            operations_total.labels(
                operation_type="training", status="completed"
            )._value.get()
            == 2
        )
        assert (
            operations_total.labels(
                operation_type="backtesting", status="failed"
            )._value.get()
            == 1
        )

    def test_operation_duration_histogram_exists(self):
        """Test that operation_duration_seconds histogram is defined correctly."""
        # Histogram should support labels
        operation_duration_seconds.labels(
            operation_type="training", status="completed"
        ).observe(120.5)
        operation_duration_seconds.labels(
            operation_type="backtesting", status="completed"
        ).observe(45.3)

        # Histogram sum should reflect observations
        training_metric = operation_duration_seconds.labels(
            operation_type="training", status="completed"
        )
        assert training_metric._sum.get() == 120.5

    def test_increment_operations_total(self):
        """Test increment_operations_total helper function."""
        # Get initial values
        initial_completed = operations_total.labels(
            operation_type="training", status="completed"
        )._value.get()
        initial_failed = operations_total.labels(
            operation_type="training", status="failed"
        )._value.get()

        # Increment
        increment_operations_total("training", "completed")
        increment_operations_total("training", "completed")
        increment_operations_total("training", "failed")

        # Check increments (counters accumulate, can't be reset)
        assert (
            operations_total.labels(
                operation_type="training", status="completed"
            )._value.get()
            == initial_completed + 2
        )
        assert (
            operations_total.labels(
                operation_type="training", status="failed"
            )._value.get()
            == initial_failed + 1
        )

    def test_record_operation_duration(self):
        """Test record_operation_duration helper function."""
        # Get initial values (histograms accumulate, can't be reset)
        metric = operation_duration_seconds.labels(
            operation_type="backtesting", status="completed"
        )
        initial_sum = metric._sum.get()

        record_operation_duration("backtesting", "completed", 60.0)
        record_operation_duration("backtesting", "completed", 90.0)

        # Check sum increment
        assert metric._sum.get() == initial_sum + 150.0


class TestMetricsReset:
    """Tests for metrics reset functionality."""

    def test_reset_metrics_clears_all(self):
        """Test that reset_metrics clears all custom metrics."""
        # Set some values
        workers_registered.labels(worker_type="backtesting").set(5)
        workers_available.labels(worker_type="training").set(3)
        operations_active.set(10)

        # Reset
        reset_metrics()

        # All should be 0
        assert workers_registered.labels(worker_type="backtesting")._value.get() == 0
        assert workers_available.labels(worker_type="training")._value.get() == 0
        assert operations_active._value.get() == 0


class TestMetricsIntegration:
    """Integration tests for metrics with registry."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics()

    def test_metrics_registered_in_prometheus_registry(self):
        """Test that all metrics are registered in Prometheus registry."""
        # Get all metric names from registry
        metric_names = [
            metric.name
            for metric in REGISTRY.collect()
            if metric.name.startswith("ktrdr_")
        ]

        # Check our custom metrics are present
        # Note: prometheus_client adds _total suffix automatically for Counters
        assert "ktrdr_workers_registered_total" in metric_names
        assert "ktrdr_workers_available" in metric_names
        assert "ktrdr_operations_active" in metric_names
        assert (
            "ktrdr_operations" in metric_names
        )  # Counter without _total suffix in registry
        assert "ktrdr_operation_duration_seconds" in metric_names

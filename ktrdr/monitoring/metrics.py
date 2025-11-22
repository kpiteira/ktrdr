"""Custom Prometheus metrics for KTRDR operational visibility.

This module defines custom business metrics that provide insight into
worker status and operation lifecycle.

Metrics:
- ktrdr_workers_registered_total: Total registered workers by type
- ktrdr_workers_available: Currently available workers by type
- ktrdr_operations_active: Active operations count
- ktrdr_operations_total: Total operations by type and status
- ktrdr_operation_duration_seconds: Operation duration distribution
"""

import logging
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Worker type constants (to avoid circular import with ktrdr.api.models.workers)
WORKER_TYPE_BACKTESTING = "backtesting"
WORKER_TYPE_TRAINING = "training"
WORKER_STATUS_AVAILABLE = "available"

# Worker metrics
workers_registered = Gauge(
    "ktrdr_workers_registered_total",
    "Total registered workers",
    ["worker_type"],
)

workers_available = Gauge(
    "ktrdr_workers_available",
    "Currently available workers",
    ["worker_type"],
)

# Operation metrics
operations_active = Gauge(
    "ktrdr_operations_active",
    "Active operations count",
)

operations_total = Counter(
    "ktrdr_operations_total",
    "Total operations",
    ["operation_type", "status"],
)

# Histogram buckets for operation duration (in seconds)
# Range from 1 second to 1 hour
DURATION_BUCKETS = [1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]

operation_duration_seconds = Histogram(
    "ktrdr_operation_duration_seconds",
    "Operation duration distribution",
    ["operation_type", "status"],
    buckets=DURATION_BUCKETS,
)


def update_worker_metrics(workers: dict[str, Any]) -> None:
    """
    Update worker metrics from the workers dictionary.

    This function calculates registered and available counts for each
    worker type and updates the corresponding Prometheus gauges.

    Args:
        workers: Dictionary of worker_id -> WorkerEndpoint
    """
    # Count workers by type
    registered_by_type: dict[str, int] = {}
    available_by_type: dict[str, int] = {}

    for worker in workers.values():
        worker_type = worker.worker_type.value

        # Increment registered count
        registered_by_type[worker_type] = registered_by_type.get(worker_type, 0) + 1

        # Increment available count if worker is available
        # Compare status value to avoid circular import
        if worker.status.value == WORKER_STATUS_AVAILABLE:
            available_by_type[worker_type] = available_by_type.get(worker_type, 0) + 1

    # Update gauges for all known worker types
    for worker_type in [WORKER_TYPE_BACKTESTING, WORKER_TYPE_TRAINING]:
        workers_registered.labels(worker_type=worker_type).set(
            registered_by_type.get(worker_type, 0)
        )
        workers_available.labels(worker_type=worker_type).set(
            available_by_type.get(worker_type, 0)
        )

    logger.debug(
        f"Updated worker metrics: registered={registered_by_type}, "
        f"available={available_by_type}"
    )


def increment_operations_total(operation_type: str, status: str) -> None:
    """
    Increment the operations total counter.

    Args:
        operation_type: Type of operation (e.g., "training", "backtesting")
        status: Final status (e.g., "completed", "failed", "cancelled")
    """
    operations_total.labels(operation_type=operation_type, status=status).inc()
    logger.debug(
        f"Incremented operations_total: type={operation_type}, status={status}"
    )


def record_operation_duration(
    operation_type: str, status: str, duration_seconds: float
) -> None:
    """
    Record operation duration in histogram.

    Args:
        operation_type: Type of operation
        status: Final status
        duration_seconds: Duration in seconds
    """
    operation_duration_seconds.labels(
        operation_type=operation_type, status=status
    ).observe(duration_seconds)
    logger.debug(
        f"Recorded operation duration: type={operation_type}, "
        f"status={status}, duration={duration_seconds:.2f}s"
    )


def reset_metrics() -> None:
    """
    Reset all custom metrics to their initial values.

    This is primarily used for testing to ensure clean state between tests.
    """
    # Reset worker gauges
    for worker_type in [WORKER_TYPE_BACKTESTING, WORKER_TYPE_TRAINING]:
        workers_registered.labels(worker_type=worker_type).set(0)
        workers_available.labels(worker_type=worker_type).set(0)

    # Reset operations active gauge
    operations_active.set(0)

    # Note: Counters and histograms cannot be reset in prometheus_client
    # They are designed to only increase. For testing, we accept this limitation.

    logger.debug("Reset custom metrics to initial values")

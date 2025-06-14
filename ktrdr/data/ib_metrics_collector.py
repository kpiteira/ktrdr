"""
IB Metrics Collector

Comprehensive metrics collection system for Interactive Brokers operations.
Tracks performance, errors, connection health, and operational statistics.
"""

import time
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json
from pathlib import Path

from ktrdr.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MetricEvent:
    """Individual metric event."""

    timestamp: float
    component: str
    operation: str
    metric_type: str  # 'counter', 'gauge', 'histogram', 'timer'
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ComponentMetrics:
    """Metrics for a specific component."""

    component_name: str

    # Counters
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0

    # Timers (in seconds)
    total_duration: float = 0.0
    min_duration: float = float("inf")
    max_duration: float = 0.0

    # Error tracking
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    recent_errors: deque = field(default_factory=lambda: deque(maxlen=10))

    # Performance metrics
    operations_per_minute: float = 0.0
    average_duration: float = 0.0
    success_rate: float = 100.0

    # Connection specific
    connections_created: int = 0
    connections_failed: int = 0
    connections_active: int = 0

    # Data fetching specific
    total_bars_fetched: int = 0
    total_symbols_processed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    # Pace violations
    pace_violations: int = 0
    pace_waits: int = 0
    total_pace_wait_time: float = 0.0

    def update_timer(self, duration: float):
        """Update timer metrics with new duration."""
        self.total_duration += duration
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)
        if self.total_operations > 0:
            self.average_duration = self.total_duration / self.total_operations


class IbMetricsCollector:
    """
    Comprehensive metrics collector for IB operations.

    Features:
    - Real-time metrics collection
    - Component-specific tracking
    - Error aggregation and analysis
    - Performance monitoring
    - Exportable metrics in multiple formats
    """

    def __init__(
        self,
        retention_hours: int = 24,
        max_events: int = 10000,
        persist_to_disk: bool = True,
        metrics_file: Optional[str] = None,
    ):
        """
        Initialize metrics collector.

        Args:
            retention_hours: How long to keep detailed events
            max_events: Maximum events to keep in memory
            persist_to_disk: Whether to persist metrics to disk
            metrics_file: Custom metrics file path
        """
        self.retention_hours = retention_hours
        self.max_events = max_events
        self.persist_to_disk = persist_to_disk

        # Thread safety
        self._lock = threading.RLock()

        # Storage
        self._events: deque = deque(maxlen=max_events)
        self._component_metrics: Dict[str, ComponentMetrics] = {}
        self._operation_timers: Dict[str, float] = {}  # operation_id -> start_time

        # Aggregated metrics
        self._global_metrics = {
            "start_time": time.time(),
            "total_operations": 0,
            "total_errors": 0,
            "uptime_seconds": 0,
            "components_active": 0,
        }

        # File persistence
        if metrics_file:
            self.metrics_file = Path(metrics_file)
        else:
            self.metrics_file = Path("data/ib_metrics.json")

        # Load existing metrics if available
        self._load_metrics()

        logger.info(
            f"IB metrics collector initialized (retention: {retention_hours}h, max_events: {max_events})"
        )

    def record_operation_start(
        self, component: str, operation: str, labels: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Record the start of an operation.

        Returns:
            operation_id for tracking the operation
        """
        operation_id = f"{component}_{operation}_{time.time()}"

        with self._lock:
            self._operation_timers[operation_id] = time.time()

            # Create component metrics if not exists
            if component not in self._component_metrics:
                self._component_metrics[component] = ComponentMetrics(
                    component_name=component
                )

        return operation_id

    def record_operation_end(
        self,
        operation_id: str,
        component: str,
        operation: str,
        success: bool = True,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Record the completion of an operation."""
        if labels is None:
            labels = {}

        with self._lock:
            # Calculate duration
            start_time = self._operation_timers.pop(operation_id, time.time())
            duration = time.time() - start_time

            # Create event
            event = MetricEvent(
                timestamp=time.time(),
                component=component,
                operation=operation,
                metric_type="timer",
                value=duration,
                labels=labels,
                success=success,
                error_code=error_code,
                error_message=error_message,
            )

            self._events.append(event)

            # Update component metrics
            metrics = self._component_metrics.get(component)
            if metrics:
                metrics.total_operations += 1
                if success:
                    metrics.successful_operations += 1
                else:
                    metrics.failed_operations += 1
                    if error_code:
                        metrics.errors_by_type[error_code] = (
                            metrics.errors_by_type.get(error_code, 0) + 1
                        )

                    # Store recent error
                    metrics.recent_errors.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "operation": operation,
                            "error_code": error_code,
                            "error_message": error_message,
                        }
                    )

                metrics.update_timer(duration)

                # Update success rate
                if metrics.total_operations > 0:
                    metrics.success_rate = (
                        metrics.successful_operations / metrics.total_operations
                    ) * 100

            # Update global metrics
            self._global_metrics["total_operations"] += 1
            if not success:
                self._global_metrics["total_errors"] += 1

    def record_counter(
        self,
        component: str,
        metric_name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Record a counter metric."""
        if labels is None:
            labels = {}

        event = MetricEvent(
            timestamp=time.time(),
            component=component,
            operation=metric_name,
            metric_type="counter",
            value=value,
            labels=labels,
        )

        with self._lock:
            self._events.append(event)

            # Ensure component metrics exist
            if component not in self._component_metrics:
                self._component_metrics[component] = ComponentMetrics(
                    component_name=component
                )

            # Update component-specific counters
            metrics = self._component_metrics[component]
            if metric_name == "connection_created":
                metrics.connections_created += value
            elif metric_name == "connection_failed":
                metrics.connections_failed += value
            elif metric_name == "bars_fetched":
                metrics.total_bars_fetched += value
            elif metric_name == "symbol_processed":
                metrics.total_symbols_processed += value
            elif metric_name == "cache_hit":
                metrics.cache_hits += value
            elif metric_name == "cache_miss":
                metrics.cache_misses += value
            elif metric_name == "pace_violation":
                metrics.pace_violations += value
            elif metric_name == "pace_wait":
                metrics.pace_waits += value

    def record_gauge(
        self,
        component: str,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ):
        """Record a gauge metric."""
        if labels is None:
            labels = {}

        event = MetricEvent(
            timestamp=time.time(),
            component=component,
            operation=metric_name,
            metric_type="gauge",
            value=value,
            labels=labels,
        )

        with self._lock:
            self._events.append(event)

            # Ensure component metrics exist
            if component not in self._component_metrics:
                self._component_metrics[component] = ComponentMetrics(
                    component_name=component
                )

            # Update component-specific gauges
            metrics = self._component_metrics[component]
            if metric_name == "connections_active":
                metrics.connections_active = int(value)
            elif metric_name == "pace_wait_time":
                metrics.total_pace_wait_time += value

    def get_component_metrics(self, component: str) -> Optional[ComponentMetrics]:
        """Get metrics for a specific component."""
        with self._lock:
            return self._component_metrics.get(component)

    def get_all_component_metrics(self) -> Dict[str, ComponentMetrics]:
        """Get metrics for all components."""
        with self._lock:
            return self._component_metrics.copy()

    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global system metrics."""
        with self._lock:
            current_time = time.time()
            uptime = current_time - self._global_metrics["start_time"]

            metrics = self._global_metrics.copy()
            metrics["uptime_seconds"] = uptime
            metrics["components_active"] = len(self._component_metrics)
            metrics["timestamp"] = current_time

            # Calculate rates
            if uptime > 0:
                metrics["operations_per_second"] = (
                    self._global_metrics["total_operations"] / uptime
                )
                metrics["errors_per_hour"] = (
                    self._global_metrics["total_errors"] / uptime
                ) * 3600

            return metrics

    def get_recent_events(
        self,
        component: Optional[str] = None,
        operation: Optional[str] = None,
        max_events: int = 100,
    ) -> List[MetricEvent]:
        """Get recent events, optionally filtered."""
        with self._lock:
            events = list(self._events)

        # Apply filters
        if component:
            events = [e for e in events if e.component == component]
        if operation:
            events = [e for e in events if e.operation == operation]

        # Return most recent events
        return events[-max_events:]

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors across all components."""
        with self._lock:
            error_summary = {
                "total_errors": self._global_metrics["total_errors"],
                "errors_by_component": {},
                "errors_by_type": {},
                "recent_errors": [],
            }

            for component_name, metrics in self._component_metrics.items():
                if metrics.failed_operations > 0:
                    error_summary["errors_by_component"][component_name] = {
                        "failed_operations": metrics.failed_operations,
                        "success_rate": metrics.success_rate,
                        "errors_by_type": metrics.errors_by_type.copy(),
                    }

                # Aggregate error types
                for error_type, count in metrics.errors_by_type.items():
                    error_summary["errors_by_type"][error_type] = (
                        error_summary["errors_by_type"].get(error_type, 0) + count
                    )

                # Add recent errors
                error_summary["recent_errors"].extend(list(metrics.recent_errors))

            # Sort recent errors by timestamp
            error_summary["recent_errors"].sort(
                key=lambda x: x["timestamp"], reverse=True
            )
            error_summary["recent_errors"] = error_summary["recent_errors"][
                :20
            ]  # Last 20 errors

            return error_summary

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary across all components."""
        with self._lock:
            perf_summary = {"global": self.get_global_metrics(), "components": {}}

            for component_name, metrics in self._component_metrics.items():
                perf_summary["components"][component_name] = {
                    "total_operations": metrics.total_operations,
                    "success_rate": metrics.success_rate,
                    "average_duration": metrics.average_duration,
                    "min_duration": (
                        metrics.min_duration
                        if metrics.min_duration != float("inf")
                        else 0
                    ),
                    "max_duration": metrics.max_duration,
                    "operations_per_minute": metrics.operations_per_minute,
                    "connections_created": metrics.connections_created,
                    "connections_failed": metrics.connections_failed,
                    "connections_active": metrics.connections_active,
                    "pace_violations": metrics.pace_violations,
                    "pace_waits": metrics.pace_waits,
                    "total_pace_wait_time": metrics.total_pace_wait_time,
                }

            return perf_summary

    def export_metrics(self, format: str = "json") -> str:
        """Export all metrics in specified format."""
        if format.lower() == "json":
            return self._export_json()
        elif format.lower() == "prometheus":
            return self._export_prometheus()
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _export_json(self) -> str:
        """Export metrics as JSON."""
        export_data = {
            "timestamp": time.time(),
            "global_metrics": self.get_global_metrics(),
            "component_metrics": {},
            "error_summary": self.get_error_summary(),
            "performance_summary": self.get_performance_summary(),
        }

        # Convert ComponentMetrics to dict
        for component_name, metrics in self._component_metrics.items():
            export_data["component_metrics"][component_name] = {
                "component_name": metrics.component_name,
                "total_operations": metrics.total_operations,
                "successful_operations": metrics.successful_operations,
                "failed_operations": metrics.failed_operations,
                "total_duration": metrics.total_duration,
                "min_duration": (
                    metrics.min_duration if metrics.min_duration != float("inf") else 0
                ),
                "max_duration": metrics.max_duration,
                "average_duration": metrics.average_duration,
                "success_rate": metrics.success_rate,
                "errors_by_type": metrics.errors_by_type,
                "recent_errors": list(metrics.recent_errors),
                "connections_created": metrics.connections_created,
                "connections_failed": metrics.connections_failed,
                "connections_active": metrics.connections_active,
                "total_bars_fetched": metrics.total_bars_fetched,
                "total_symbols_processed": metrics.total_symbols_processed,
                "cache_hits": metrics.cache_hits,
                "cache_misses": metrics.cache_misses,
                "pace_violations": metrics.pace_violations,
                "pace_waits": metrics.pace_waits,
                "total_pace_wait_time": metrics.total_pace_wait_time,
            }

        return json.dumps(export_data, indent=2)

    def _export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        timestamp = int(time.time() * 1000)  # Prometheus uses milliseconds

        # Global metrics
        global_metrics = self.get_global_metrics()
        lines.append(
            f"ib_total_operations {global_metrics['total_operations']} {timestamp}"
        )
        lines.append(f"ib_total_errors {global_metrics['total_errors']} {timestamp}")
        lines.append(
            f"ib_uptime_seconds {global_metrics['uptime_seconds']} {timestamp}"
        )
        lines.append(
            f"ib_components_active {global_metrics['components_active']} {timestamp}"
        )

        # Component metrics
        for component_name, metrics in self._component_metrics.items():
            labels = f'component="{component_name}"'
            lines.append(
                f"ib_component_operations_total{{{labels}}} {metrics.total_operations} {timestamp}"
            )
            lines.append(
                f"ib_component_operations_successful{{{labels}}} {metrics.successful_operations} {timestamp}"
            )
            lines.append(
                f"ib_component_operations_failed{{{labels}}} {metrics.failed_operations} {timestamp}"
            )
            lines.append(
                f"ib_component_success_rate{{{labels}}} {metrics.success_rate} {timestamp}"
            )
            lines.append(
                f"ib_component_average_duration{{{labels}}} {metrics.average_duration} {timestamp}"
            )
            lines.append(
                f"ib_component_connections_active{{{labels}}} {metrics.connections_active} {timestamp}"
            )
            lines.append(
                f"ib_component_pace_violations{{{labels}}} {metrics.pace_violations} {timestamp}"
            )

        return "\n".join(lines)

    def _save_metrics(self):
        """Save metrics to disk."""
        if not self.persist_to_disk:
            return

        try:
            self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.metrics_file, "w") as f:
                f.write(self._export_json())

            logger.debug(f"Metrics saved to {self.metrics_file}")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def _load_metrics(self):
        """Load metrics from disk."""
        if not self.persist_to_disk or not self.metrics_file.exists():
            return

        try:
            with open(self.metrics_file, "r") as f:
                data = json.load(f)

            # Restore global metrics
            if "global_metrics" in data:
                self._global_metrics.update(data["global_metrics"])

            # Restore component metrics
            if "component_metrics" in data:
                for component_name, metrics_data in data["component_metrics"].items():
                    metrics = ComponentMetrics(component_name=component_name)

                    # Update all fields
                    for field_name, value in metrics_data.items():
                        if hasattr(metrics, field_name):
                            if field_name == "recent_errors":
                                metrics.recent_errors = deque(value, maxlen=10)
                            else:
                                setattr(metrics, field_name, value)

                    self._component_metrics[component_name] = metrics

            logger.info(f"Metrics loaded from {self.metrics_file}")

        except Exception as e:
            logger.warning(f"Failed to load metrics: {e}")

    def cleanup_old_events(self):
        """Remove events older than retention period."""
        cutoff_time = time.time() - (self.retention_hours * 3600)

        with self._lock:
            # Remove old events
            while self._events and self._events[0].timestamp < cutoff_time:
                self._events.popleft()

    def reset_metrics(self, component: Optional[str] = None):
        """Reset metrics for a component or all components."""
        with self._lock:
            if component:
                if component in self._component_metrics:
                    self._component_metrics[component] = ComponentMetrics(
                        component_name=component
                    )
            else:
                self._component_metrics.clear()
                self._global_metrics = {
                    "start_time": time.time(),
                    "total_operations": 0,
                    "total_errors": 0,
                    "uptime_seconds": 0,
                    "components_active": 0,
                }
                self._events.clear()

        logger.info(
            f"Metrics reset for {'all components' if not component else component}"
        )


# Global instance
_metrics_collector: Optional[IbMetricsCollector] = None


def get_metrics_collector() -> IbMetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = IbMetricsCollector()
    return _metrics_collector


def record_operation_start(
    component: str, operation: str, labels: Optional[Dict[str, str]] = None
) -> str:
    """Convenience function to record operation start."""
    return get_metrics_collector().record_operation_start(component, operation, labels)


def record_operation_end(
    operation_id: str,
    component: str,
    operation: str,
    success: bool = True,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None,
):
    """Convenience function to record operation end."""
    get_metrics_collector().record_operation_end(
        operation_id, component, operation, success, error_code, error_message, labels
    )


def record_counter(
    component: str,
    metric_name: str,
    value: int = 1,
    labels: Optional[Dict[str, str]] = None,
):
    """Convenience function to record counter."""
    get_metrics_collector().record_counter(component, metric_name, value, labels)


def record_gauge(
    component: str,
    metric_name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
):
    """Convenience function to record gauge."""
    get_metrics_collector().record_gauge(component, metric_name, value, labels)

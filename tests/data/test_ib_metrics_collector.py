"""
Unit tests for IbMetricsCollector.

Tests comprehensive metrics collection functionality including:
- Operation timing and recording
- Counter and gauge metrics
- Component-specific tracking
- Error aggregation
- Export capabilities
"""

import pytest
import time
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

from ktrdr.data.ib_metrics_collector import (
    IbMetricsCollector,
    MetricEvent,
    ComponentMetrics,
    get_metrics_collector,
    record_operation_start,
    record_operation_end,
    record_counter,
    record_gauge,
)


class TestMetricEvent:
    """Test MetricEvent dataclass."""

    def test_metric_event_creation(self):
        """Test creating a metric event."""
        event = MetricEvent(
            timestamp=time.time(),
            component="test_component",
            operation="test_operation",
            metric_type="counter",
            value=1.0,
            labels={"key": "value"},
            success=True,
        )

        assert event.component == "test_component"
        assert event.operation == "test_operation"
        assert event.metric_type == "counter"
        assert event.value == 1.0
        assert event.labels == {"key": "value"}
        assert event.success is True
        assert event.error_code is None
        assert event.error_message is None


class TestComponentMetrics:
    """Test ComponentMetrics dataclass."""

    def test_component_metrics_creation(self):
        """Test creating component metrics."""
        metrics = ComponentMetrics(component_name="test_component")

        assert metrics.component_name == "test_component"
        assert metrics.total_operations == 0
        assert metrics.successful_operations == 0
        assert metrics.failed_operations == 0
        assert metrics.success_rate == 100.0
        assert metrics.min_duration == float("inf")
        assert metrics.max_duration == 0.0

    def test_update_timer(self):
        """Test timer metric updates."""
        metrics = ComponentMetrics(component_name="test_component")

        # First update
        metrics.update_timer(2.5)
        assert metrics.total_duration == 2.5
        assert metrics.min_duration == 2.5
        assert metrics.max_duration == 2.5

        # Second update
        metrics.total_operations = 2  # Simulate operations count
        metrics.update_timer(1.0)
        assert metrics.total_duration == 3.5
        assert metrics.min_duration == 1.0
        assert metrics.max_duration == 2.5
        assert metrics.average_duration == 1.75  # 3.5 / 2


class TestIbMetricsCollector:
    """Test IbMetricsCollector class."""

    @pytest.fixture
    def temp_metrics_file(self):
        """Create temporary metrics file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            yield f.name
        Path(f.name).unlink(missing_ok=True)

    @pytest.fixture
    def metrics_collector(self, temp_metrics_file):
        """Create metrics collector for testing."""
        return IbMetricsCollector(
            retention_hours=1,
            max_events=100,
            persist_to_disk=True,
            metrics_file=temp_metrics_file,
        )

    def test_metrics_collector_initialization(self, metrics_collector):
        """Test metrics collector initialization."""
        assert metrics_collector.retention_hours == 1
        assert metrics_collector.max_events == 100
        assert metrics_collector.persist_to_disk is True
        assert len(metrics_collector._events) == 0
        assert len(metrics_collector._component_metrics) == 0

    def test_record_operation_timing(self, metrics_collector):
        """Test operation timing recording."""
        # Start operation
        operation_id = metrics_collector.record_operation_start(
            "test_component", "test_operation", {"key": "value"}
        )

        assert operation_id is not None
        assert operation_id in metrics_collector._operation_timers

        # Small delay
        time.sleep(0.01)

        # End operation
        metrics_collector.record_operation_end(
            operation_id,
            "test_component",
            "test_operation",
            success=True,
            labels={"result": "success"},
        )

        # Check metrics
        assert operation_id not in metrics_collector._operation_timers
        assert len(metrics_collector._events) == 1

        event = metrics_collector._events[0]
        assert event.component == "test_component"
        assert event.operation == "test_operation"
        assert event.metric_type == "timer"
        assert event.value > 0  # Should have some duration
        assert event.success is True

        # Check component metrics
        component_metrics = metrics_collector._component_metrics["test_component"]
        assert component_metrics.total_operations == 1
        assert component_metrics.successful_operations == 1
        assert component_metrics.failed_operations == 0
        assert component_metrics.success_rate == 100.0

    def test_record_operation_failure(self, metrics_collector):
        """Test operation failure recording."""
        operation_id = metrics_collector.record_operation_start(
            "test_component", "test_operation"
        )

        metrics_collector.record_operation_end(
            operation_id,
            "test_component",
            "test_operation",
            success=False,
            error_code="TEST_ERROR",
            error_message="Test error message",
        )

        # Check metrics
        component_metrics = metrics_collector._component_metrics["test_component"]
        assert component_metrics.total_operations == 1
        assert component_metrics.successful_operations == 0
        assert component_metrics.failed_operations == 1
        assert component_metrics.success_rate == 0.0
        assert "TEST_ERROR" in component_metrics.errors_by_type
        assert component_metrics.errors_by_type["TEST_ERROR"] == 1
        assert len(component_metrics.recent_errors) == 1

    def test_record_counter_metrics(self, metrics_collector):
        """Test counter metric recording."""
        metrics_collector.record_counter(
            "connection_pool", "connection_created", 1, {"purpose": "data_manager"}
        )

        metrics_collector.record_counter("connection_pool", "bars_fetched", 100)

        # Check events
        assert len(metrics_collector._events) == 2

        # Check component metrics
        component_metrics = metrics_collector._component_metrics["connection_pool"]
        assert component_metrics.connections_created == 1
        assert component_metrics.total_bars_fetched == 100

    def test_record_gauge_metrics(self, metrics_collector):
        """Test gauge metric recording."""
        metrics_collector.record_gauge("connection_pool", "connections_active", 5.0)

        metrics_collector.record_gauge("connection_pool", "pace_wait_time", 2.5)

        # Check events
        assert len(metrics_collector._events) == 2

        # Check component metrics
        component_metrics = metrics_collector._component_metrics["connection_pool"]
        assert component_metrics.connections_active == 5
        assert component_metrics.total_pace_wait_time == 2.5

    def test_get_component_metrics(self, metrics_collector):
        """Test getting component metrics."""
        # Add some metrics
        operation_id = metrics_collector.record_operation_start(
            "test_component", "test_op"
        )
        metrics_collector.record_operation_end(
            operation_id, "test_component", "test_op", True
        )

        # Get metrics
        metrics = metrics_collector.get_component_metrics("test_component")
        assert metrics is not None
        assert metrics.component_name == "test_component"
        assert metrics.total_operations == 1

        # Non-existent component
        assert metrics_collector.get_component_metrics("non_existent") is None

    def test_get_all_component_metrics(self, metrics_collector):
        """Test getting all component metrics."""
        # Add metrics for multiple components
        op1 = metrics_collector.record_operation_start("component1", "op1")
        metrics_collector.record_operation_end(op1, "component1", "op1", True)

        op2 = metrics_collector.record_operation_start("component2", "op2")
        metrics_collector.record_operation_end(op2, "component2", "op2", False, "ERROR")

        all_metrics = metrics_collector.get_all_component_metrics()
        assert len(all_metrics) == 2
        assert "component1" in all_metrics
        assert "component2" in all_metrics
        assert all_metrics["component1"].successful_operations == 1
        assert all_metrics["component2"].failed_operations == 1

    def test_get_global_metrics(self, metrics_collector):
        """Test getting global metrics."""
        # Add some operations
        op1 = metrics_collector.record_operation_start("component1", "op1")
        metrics_collector.record_operation_end(op1, "component1", "op1", True)

        op2 = metrics_collector.record_operation_start("component2", "op2")
        metrics_collector.record_operation_end(op2, "component2", "op2", False, "ERROR")

        global_metrics = metrics_collector.get_global_metrics()

        assert global_metrics["total_operations"] == 2
        assert global_metrics["total_errors"] == 1
        assert global_metrics["components_active"] == 2
        assert global_metrics["uptime_seconds"] > 0
        assert "operations_per_second" in global_metrics
        assert "timestamp" in global_metrics

    def test_get_recent_events(self, metrics_collector):
        """Test getting recent events."""
        # Add multiple events
        for i in range(5):
            op_id = metrics_collector.record_operation_start(f"component{i}", f"op{i}")
            metrics_collector.record_operation_end(
                op_id, f"component{i}", f"op{i}", True
            )

        # Get all recent events
        events = metrics_collector.get_recent_events()
        assert len(events) == 5

        # Get filtered events
        component1_events = metrics_collector.get_recent_events(component="component1")
        assert len(component1_events) == 1
        assert component1_events[0].component == "component1"

        # Get limited events
        limited_events = metrics_collector.get_recent_events(max_events=3)
        assert len(limited_events) == 3

    def test_get_error_summary(self, metrics_collector):
        """Test error summary generation."""
        # Add successful and failed operations
        op1 = metrics_collector.record_operation_start("component1", "op1")
        metrics_collector.record_operation_end(op1, "component1", "op1", True)

        op2 = metrics_collector.record_operation_start("component1", "op2")
        metrics_collector.record_operation_end(
            op2, "component1", "op2", False, "ERROR_A"
        )

        op3 = metrics_collector.record_operation_start("component2", "op3")
        metrics_collector.record_operation_end(
            op3, "component2", "op3", False, "ERROR_B"
        )

        error_summary = metrics_collector.get_error_summary()

        assert error_summary["total_errors"] == 2
        assert len(error_summary["errors_by_component"]) == 2
        assert (
            error_summary["errors_by_component"]["component1"]["failed_operations"] == 1
        )
        assert (
            error_summary["errors_by_component"]["component2"]["failed_operations"] == 1
        )
        assert error_summary["errors_by_type"]["ERROR_A"] == 1
        assert error_summary["errors_by_type"]["ERROR_B"] == 1
        assert len(error_summary["recent_errors"]) == 2

    def test_get_performance_summary(self, metrics_collector):
        """Test performance summary generation."""
        # Add some operations with timing
        op1 = metrics_collector.record_operation_start("component1", "op1")
        time.sleep(0.01)
        metrics_collector.record_operation_end(op1, "component1", "op1", True)

        perf_summary = metrics_collector.get_performance_summary()

        assert "global" in perf_summary
        assert "components" in perf_summary
        assert "component1" in perf_summary["components"]

        component1_perf = perf_summary["components"]["component1"]
        assert component1_perf["total_operations"] == 1
        assert component1_perf["success_rate"] == 100.0
        assert component1_perf["average_duration"] > 0

    def test_export_json(self, metrics_collector):
        """Test JSON export functionality."""
        # Add some data
        op1 = metrics_collector.record_operation_start("component1", "op1")
        metrics_collector.record_operation_end(op1, "component1", "op1", True)

        json_export = metrics_collector.export_metrics("json")

        # Parse JSON to verify structure
        data = json.loads(json_export)
        assert "timestamp" in data
        assert "global_metrics" in data
        assert "component_metrics" in data
        assert "error_summary" in data
        assert "performance_summary" in data
        assert "component1" in data["component_metrics"]

    def test_export_prometheus(self, metrics_collector):
        """Test Prometheus export functionality."""
        # Add some data
        op1 = metrics_collector.record_operation_start("component1", "op1")
        metrics_collector.record_operation_end(op1, "component1", "op1", True)

        prom_export = metrics_collector.export_metrics("prometheus")

        # Check Prometheus format
        lines = prom_export.split("\n")
        assert any("ib_total_operations" in line for line in lines)
        assert any("ib_uptime_seconds" in line for line in lines)
        assert any('component="component1"' in line for line in lines)

    def test_export_invalid_format(self, metrics_collector):
        """Test export with invalid format."""
        with pytest.raises(ValueError, match="Unsupported export format"):
            metrics_collector.export_metrics("invalid_format")

    def test_cleanup_old_events(self, metrics_collector):
        """Test cleanup of old events."""
        # Set very short retention (approximately 0.036 seconds)
        metrics_collector.retention_hours = 0.00001  # ~0.036 seconds

        # Add an event
        op1 = metrics_collector.record_operation_start("component1", "op1")
        metrics_collector.record_operation_end(op1, "component1", "op1", True)

        assert len(metrics_collector._events) == 1

        # Wait for retention period to pass
        time.sleep(0.05)  # Wait 50ms to ensure retention period has passed

        # Clean up
        metrics_collector.cleanup_old_events()

        # Event should be removed
        assert len(metrics_collector._events) == 0

    def test_reset_metrics(self, metrics_collector):
        """Test metrics reset functionality."""
        # Add some data
        op1 = metrics_collector.record_operation_start("component1", "op1")
        metrics_collector.record_operation_end(op1, "component1", "op1", True)

        assert len(metrics_collector._component_metrics) == 1
        assert len(metrics_collector._events) == 1

        # Reset all metrics
        metrics_collector.reset_metrics()

        assert len(metrics_collector._component_metrics) == 0
        assert len(metrics_collector._events) == 0

        # Test component-specific reset
        op2 = metrics_collector.record_operation_start("component1", "op2")
        metrics_collector.record_operation_end(op2, "component1", "op2", True)

        op3 = metrics_collector.record_operation_start("component2", "op3")
        metrics_collector.record_operation_end(op3, "component2", "op3", True)

        assert len(metrics_collector._component_metrics) == 2

        # Reset only component1
        metrics_collector.reset_metrics("component1")

        assert len(metrics_collector._component_metrics) == 2  # Still 2 components
        assert metrics_collector._component_metrics["component1"].total_operations == 0
        assert metrics_collector._component_metrics["component2"].total_operations == 1

    def test_persistence_to_disk(self, temp_metrics_file):
        """Test metrics persistence to disk."""
        # Create collector with persistence
        collector = IbMetricsCollector(
            persist_to_disk=True, metrics_file=temp_metrics_file
        )

        # Add some data
        op1 = collector.record_operation_start("component1", "op1")
        collector.record_operation_end(op1, "component1", "op1", True)

        # Save to disk
        collector._save_metrics()

        # Verify file exists and contains data
        assert Path(temp_metrics_file).exists()

        with open(temp_metrics_file, "r") as f:
            data = json.load(f)

        assert "component_metrics" in data
        assert "component1" in data["component_metrics"]

    def test_loading_from_disk(self, temp_metrics_file):
        """Test loading metrics from disk."""
        # Create test data
        test_data = {
            "global_metrics": {"total_operations": 5, "total_errors": 1},
            "component_metrics": {
                "component1": {
                    "component_name": "component1",
                    "total_operations": 5,
                    "successful_operations": 4,
                    "failed_operations": 1,
                    "total_duration": 10.0,
                    "min_duration": 1.0,
                    "max_duration": 3.0,
                    "average_duration": 2.0,
                    "success_rate": 80.0,
                    "errors_by_type": {"ERROR_A": 1},
                    "recent_errors": [],
                    "connections_created": 2,
                    "connections_failed": 0,
                    "connections_active": 1,
                    "total_bars_fetched": 100,
                    "total_symbols_processed": 5,
                    "cache_hits": 10,
                    "cache_misses": 2,
                    "pace_violations": 0,
                    "pace_waits": 1,
                    "total_pace_wait_time": 5.0,
                }
            },
        }

        # Save test data
        with open(temp_metrics_file, "w") as f:
            json.dump(test_data, f)

        # Create collector - should load existing data
        collector = IbMetricsCollector(
            persist_to_disk=True, metrics_file=temp_metrics_file
        )

        # Verify data was loaded
        assert collector._global_metrics["total_operations"] == 5
        assert "component1" in collector._component_metrics
        component_metrics = collector._component_metrics["component1"]
        assert component_metrics.total_operations == 5
        assert component_metrics.success_rate == 80.0


class TestGlobalMetricsCollector:
    """Test global metrics collector functions."""

    def test_get_metrics_collector_singleton(self):
        """Test global metrics collector singleton."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        assert collector1 is collector2

    def test_convenience_functions(self):
        """Test convenience functions."""
        # Test operation recording
        operation_id = record_operation_start("test_component", "test_operation")
        assert operation_id is not None

        record_operation_end(operation_id, "test_component", "test_operation", True)

        # Test counter recording
        record_counter("test_component", "test_counter", 5)

        # Test gauge recording
        record_gauge("test_component", "test_gauge", 10.5)

        # Verify in global collector
        collector = get_metrics_collector()
        component_metrics = collector.get_component_metrics("test_component")
        assert component_metrics is not None
        assert component_metrics.total_operations == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

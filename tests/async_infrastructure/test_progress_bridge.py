"""
Unit tests for ProgressBridge base class (pull-based architecture).

Tests verify:
- Pull-based interface (get_status, get_metrics)
- Thread safety with RLock
- Incremental metrics with cursor
- Generic state/metrics storage
- Protected helpers for subclasses
"""

import threading
import time
from datetime import datetime

from ktrdr.async_infrastructure.progress_bridge import ProgressBridge


class TestProgressBridgeConstruction:
    """Test ProgressBridge can be constructed directly (concrete class)."""

    def test_can_instantiate_directly(self):
        """ProgressBridge is concrete, not abstract - can instantiate directly."""
        bridge = ProgressBridge()

        assert bridge is not None
        assert isinstance(bridge, ProgressBridge)

    def test_initial_state_is_empty(self):
        """Newly created bridge has empty state."""
        bridge = ProgressBridge()

        status = bridge.get_status()

        assert status == {}

    def test_initial_metrics_is_empty(self):
        """Newly created bridge has no metrics."""
        bridge = ProgressBridge()

        metrics, cursor = bridge.get_metrics(cursor=0)

        assert metrics == []
        assert cursor == 0


class TestProgressBridgeGetStatus:
    """Test get_status() returns current state snapshot."""

    def test_get_status_returns_snapshot(self):
        """get_status() returns a snapshot of current state."""
        bridge = ProgressBridge()

        # Update state via protected helper
        bridge._update_state(
            percentage=50.0, message="Halfway there", custom_field="custom_value"
        )

        status = bridge.get_status()

        assert status["percentage"] == 50.0
        assert status["message"] == "Halfway there"
        assert status["custom_field"] == "custom_value"
        assert "timestamp" in status

    def test_get_status_returns_copy_not_reference(self):
        """get_status() returns a copy, not a reference to internal state."""
        bridge = ProgressBridge()
        bridge._update_state(percentage=50.0, message="Test")

        status1 = bridge.get_status()
        status1["percentage"] = 999.0  # Mutate the returned dict

        status2 = bridge.get_status()

        # Internal state should not be affected
        assert status2["percentage"] == 50.0

    def test_get_status_includes_timestamp(self):
        """get_status() always includes a timestamp."""
        bridge = ProgressBridge()
        bridge._update_state(percentage=25.0, message="Quarter")

        status = bridge.get_status()

        assert "timestamp" in status
        # Timestamp should be ISO format string
        assert isinstance(status["timestamp"], str)
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(status["timestamp"])
        assert isinstance(parsed, datetime)


class TestProgressBridgeGetMetrics:
    """Test get_metrics(cursor) returns incremental metrics."""

    def test_get_metrics_returns_all_when_cursor_zero(self):
        """get_metrics(0) returns all metrics from beginning."""
        bridge = ProgressBridge()

        # Append some metrics
        bridge._append_metric({"epoch": 1, "loss": 2.5})
        bridge._append_metric({"epoch": 2, "loss": 2.3})
        bridge._append_metric({"epoch": 3, "loss": 2.1})

        metrics, new_cursor = bridge.get_metrics(cursor=0)

        assert len(metrics) == 3
        assert metrics[0]["epoch"] == 1
        assert metrics[1]["epoch"] == 2
        assert metrics[2]["epoch"] == 3
        assert new_cursor == 3

    def test_get_metrics_incremental_cursor_based(self):
        """get_metrics() supports incremental reading with cursor."""
        bridge = ProgressBridge()

        # First batch
        bridge._append_metric({"epoch": 1, "loss": 2.5})
        bridge._append_metric({"epoch": 2, "loss": 2.3})

        metrics1, cursor1 = bridge.get_metrics(cursor=0)
        assert len(metrics1) == 2
        assert cursor1 == 2

        # Second batch
        bridge._append_metric({"epoch": 3, "loss": 2.1})
        bridge._append_metric({"epoch": 4, "loss": 1.9})

        metrics2, cursor2 = bridge.get_metrics(cursor=cursor1)
        assert len(metrics2) == 2  # Only new metrics
        assert metrics2[0]["epoch"] == 3
        assert metrics2[1]["epoch"] == 4
        assert cursor2 == 4

    def test_get_metrics_returns_empty_when_no_new_metrics(self):
        """get_metrics() returns empty list when cursor is up to date."""
        bridge = ProgressBridge()

        bridge._append_metric({"epoch": 1, "loss": 2.5})

        _, cursor = bridge.get_metrics(cursor=0)

        # Query again with same cursor
        metrics, new_cursor = bridge.get_metrics(cursor=cursor)

        assert metrics == []
        assert new_cursor == cursor  # Cursor unchanged

    def test_get_metrics_with_cursor_beyond_length(self):
        """get_metrics() handles cursor beyond current length gracefully."""
        bridge = ProgressBridge()

        bridge._append_metric({"epoch": 1, "loss": 2.5})
        bridge._append_metric({"epoch": 2, "loss": 2.3})

        # Cursor beyond length
        metrics, new_cursor = bridge.get_metrics(cursor=100)

        assert metrics == []
        assert new_cursor == 2  # Returns actual length


class TestProgressBridgeProtectedHelpers:
    """Test protected helpers for subclasses."""

    def test_update_state_creates_state_dict(self):
        """_update_state() creates state dict with provided fields."""
        bridge = ProgressBridge()

        bridge._update_state(
            percentage=75.0,
            message="Almost done",
            epoch=75,
            total_epochs=100,
            custom="value",
        )

        status = bridge.get_status()

        assert status["percentage"] == 75.0
        assert status["message"] == "Almost done"
        assert status["epoch"] == 75
        assert status["total_epochs"] == 100
        assert status["custom"] == "value"

    def test_update_state_replaces_previous_state(self):
        """_update_state() replaces entire state (not incremental)."""
        bridge = ProgressBridge()

        bridge._update_state(percentage=25.0, message="First", field1="a")
        bridge._update_state(percentage=50.0, message="Second", field2="b")

        status = bridge.get_status()

        assert status["percentage"] == 50.0
        assert status["message"] == "Second"
        assert "field1" not in status  # Previous field removed
        assert status["field2"] == "b"

    def test_append_metric_adds_to_history(self):
        """_append_metric() appends to metrics history."""
        bridge = ProgressBridge()

        bridge._append_metric({"epoch": 1, "loss": 2.5})
        bridge._append_metric({"epoch": 2, "loss": 2.3})

        metrics, _ = bridge.get_metrics(cursor=0)

        assert len(metrics) == 2

    def test_append_metric_preserves_order(self):
        """_append_metric() preserves insertion order."""
        bridge = ProgressBridge()

        for i in range(10):
            bridge._append_metric({"index": i})

        metrics, _ = bridge.get_metrics(cursor=0)

        for i, metric in enumerate(metrics):
            assert metric["index"] == i


class TestProgressBridgeThreadSafety:
    """Test thread safety with concurrent access."""

    def test_thread_safety_concurrent_access(self):
        """Bridge handles concurrent reads and writes safely."""
        bridge = ProgressBridge()
        errors = []

        def writer_thread():
            """Writer thread updates state and appends metrics."""
            try:
                for i in range(100):
                    bridge._update_state(percentage=float(i), message=f"Update {i}")
                    bridge._append_metric({"iteration": i})
            except Exception as e:
                errors.append(f"Writer error: {e}")

        def reader_thread():
            """Reader thread queries state and metrics."""
            try:
                cursor = 0
                for _ in range(100):
                    status = bridge.get_status()
                    metrics, cursor = bridge.get_metrics(cursor=cursor)
                    # Validate data integrity
                    assert isinstance(status, dict)
                    assert isinstance(metrics, list)
            except Exception as e:
                errors.append(f"Reader error: {e}")

        # Create multiple writer and reader threads
        writers = [threading.Thread(target=writer_thread) for _ in range(3)]
        readers = [threading.Thread(target=reader_thread) for _ in range(5)]

        # Start all threads
        for t in writers + readers:
            t.start()

        # Wait for all threads
        for t in writers + readers:
            t.join()

        # No errors should have occurred
        assert errors == []

    def test_concurrent_metric_appends_no_loss(self):
        """Concurrent metric appends don't lose any metrics."""
        bridge = ProgressBridge()
        num_threads = 10
        metrics_per_thread = 50

        def append_metrics(thread_id: int):
            for i in range(metrics_per_thread):
                bridge._append_metric({"thread_id": thread_id, "index": i})

        threads = [
            threading.Thread(target=append_metrics, args=(tid,))
            for tid in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have all metrics
        metrics, cursor = bridge.get_metrics(cursor=0)

        assert len(metrics) == num_threads * metrics_per_thread
        assert cursor == num_threads * metrics_per_thread

    def test_no_race_condition_on_get_status(self):
        """get_status() never returns partial/corrupted state."""
        bridge = ProgressBridge()
        corrupted_states = []

        def update_state_repeatedly():
            for i in range(1000):
                # Always update with matching values
                bridge._update_state(
                    percentage=float(i), message=f"Iteration {i}", iteration=i
                )

        def check_state_consistency():
            for _ in range(1000):
                status = bridge.get_status()
                if status:
                    # If state exists, percentage and iteration should match
                    pct = status.get("percentage", 0)
                    iteration = status.get("iteration", 0)
                    msg = status.get("message", "")

                    # All three should be consistent
                    if int(pct) != iteration or f"Iteration {iteration}" != msg:
                        corrupted_states.append(status)

        updater = threading.Thread(target=update_state_repeatedly)
        checker = threading.Thread(target=check_state_consistency)

        updater.start()
        checker.start()
        updater.join()
        checker.join()

        # Should never see inconsistent state
        assert corrupted_states == []


class TestProgressBridgePerformance:
    """Test performance targets (<1μs worker overhead)."""

    def test_update_state_performance(self):
        """_update_state() completes in <1.5μs average (10k iterations)."""
        bridge = ProgressBridge()
        iterations = 10000

        start = time.perf_counter()
        for i in range(iterations):
            bridge._update_state(percentage=float(i % 100), message=f"Update {i}")
        end = time.perf_counter()

        avg_time = (end - start) / iterations

        # Target: <1.5μs average (allows for timestamp generation + machine variance)
        # Typical: ~1.0-1.2μs depending on machine
        assert (
            avg_time < 0.0000015
        ), f"Average time {avg_time*1e6:.2f}μs exceeds 1.5μs target"

    def test_append_metric_performance(self):
        """_append_metric() completes in <1μs average."""
        bridge = ProgressBridge()
        iterations = 10000

        start = time.perf_counter()
        for i in range(iterations):
            bridge._append_metric({"index": i})
        end = time.perf_counter()

        avg_time = (end - start) / iterations

        assert (
            avg_time < 0.000001
        ), f"Average time {avg_time*1e6:.2f}μs exceeds 1μs target"


class TestProgressBridgeSubclassing:
    """Test that ProgressBridge can be subclassed properly."""

    def test_can_subclass_progress_bridge(self):
        """Can create subclasses of ProgressBridge."""

        class CustomBridge(ProgressBridge):
            """Custom bridge for testing."""

            def on_custom_event(self, value: int):
                """Domain-specific callback."""
                self._update_state(
                    percentage=value,
                    message=f"Custom event: {value}",
                    custom_value=value,
                )

        bridge = CustomBridge()
        bridge.on_custom_event(42)

        status = bridge.get_status()

        assert status["percentage"] == 42
        assert status["message"] == "Custom event: 42"
        assert status["custom_value"] == 42

    def test_subclass_can_use_protected_helpers(self):
        """Subclasses can access protected helpers."""

        class TrainingBridge(ProgressBridge):
            """Training-specific bridge."""

            def on_epoch(self, epoch: int, total: int, loss: float):
                """Training epoch callback."""
                percentage = (epoch / total) * 100.0
                self._update_state(
                    percentage=percentage,
                    message=f"Epoch {epoch}/{total}",
                    epoch=epoch,
                    total=total,
                )
                self._append_metric({"epoch": epoch, "loss": loss})

        bridge = TrainingBridge()

        bridge.on_epoch(5, 100, 1.5)
        bridge.on_epoch(10, 100, 1.2)

        status = bridge.get_status()
        assert status["epoch"] == 10

        metrics, _ = bridge.get_metrics(0)
        assert len(metrics) == 2
        assert metrics[0]["loss"] == 1.5
        assert metrics[1]["loss"] == 1.2

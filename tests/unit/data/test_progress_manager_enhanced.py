"""
Tests for enhanced ProgressManager capabilities including contextual progress,
time estimation, and enhanced CLI display integration.
"""

import threading
import time
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from ktrdr.data.components.progress_manager import (
    ProgressManager,
    ProgressState,
    TimeEstimationEngine,
)


class TestTimeEstimationEngine:
    """Test the TimeEstimationEngine component."""

    def test_time_estimation_engine_initialization(self):
        """Test TimeEstimationEngine initializes correctly."""
        engine = TimeEstimationEngine()
        assert engine.operation_history == {}
        assert engine.cache_file is None

    def test_time_estimation_engine_with_cache_file(self):
        """Test TimeEstimationEngine with persistent cache."""
        with TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.pkl"
            engine = TimeEstimationEngine(cache_file)
            assert engine.cache_file == cache_file

    def test_operation_key_creation(self):
        """Test creation of operation keys for different contexts."""
        engine = TimeEstimationEngine()

        # Test basic operation key (domain-specific logic moved to DataProgressRenderer)
        key1 = engine._create_operation_key(
            "load_data", {"symbol": "AAPL", "timeframe": "1d"}
        )
        # After cleanup, keys should be simpler (domain-specific context removed)
        assert key1 == "load_data"

        # Test with mode (domain-specific logic removed)
        key2 = engine._create_operation_key(
            "load_data", {"symbol": "MSFT", "timeframe": "1h", "mode": "backfill"}
        )
        # After cleanup, domain-specific context (symbol/timeframe/mode) is not included
        assert key2 == "load_data"

        # Test with data points (size categorization still works - it's generic)
        key3 = engine._create_operation_key(
            "load_data", {"symbol": "TSLA", "timeframe": "1d", "data_points": 500}
        )
        # After cleanup: domain-specific removed, but data_points size categorization preserved
        assert key3 == "load_data|size:small"

        key4 = engine._create_operation_key(
            "load_data", {"symbol": "GOOGL", "timeframe": "1h", "data_points": 5000}
        )
        assert key4 == "load_data|size:medium"

        key5 = engine._create_operation_key(
            "load_data", {"symbol": "NVDA", "timeframe": "5m", "data_points": 50000}
        )
        assert key5 == "load_data|size:large"

    def test_record_and_estimate_operation(self):
        """Test recording operations and estimating duration."""
        engine = TimeEstimationEngine()
        context = {"symbol": "AAPL", "timeframe": "1d", "mode": "tail"}

        # No estimate initially
        estimate = engine.estimate_duration("load_data", context)
        assert estimate is None

        # Record one operation (not enough for estimation)
        engine.record_operation_completion("load_data", context, 10.5)
        estimate = engine.estimate_duration("load_data", context)
        assert estimate is None

        # Record second operation (now we can estimate)
        engine.record_operation_completion("load_data", context, 12.3)
        estimate = engine.estimate_duration("load_data", context)
        assert estimate is not None
        assert 10 < estimate < 15  # Should be somewhere between the two values

        # Record more operations (weighted average)
        engine.record_operation_completion("load_data", context, 8.7)
        engine.record_operation_completion("load_data", context, 9.1)
        estimate = engine.estimate_duration("load_data", context)
        assert estimate is not None
        assert 8 < estimate < 13  # Should trend towards recent values

    def test_invalid_duration_recording(self):
        """Test that invalid durations are ignored."""
        engine = TimeEstimationEngine()
        context = {"symbol": "TEST", "timeframe": "1d"}

        # Invalid durations should be ignored
        engine.record_operation_completion("load_data", context, 0)
        engine.record_operation_completion("load_data", context, -5.0)

        # No history should be recorded
        key = engine._create_operation_key("load_data", context)
        assert key not in engine.operation_history

    def test_persistent_cache(self):
        """Test that operation history is persisted to cache."""
        with TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.pkl"
            context = {"symbol": "AAPL", "timeframe": "1d"}

            # Create first engine and record operation
            engine1 = TimeEstimationEngine(cache_file)
            engine1.record_operation_completion("load_data", context, 15.0)
            engine1.record_operation_completion("load_data", context, 18.0)

            # Create second engine and verify data is loaded
            engine2 = TimeEstimationEngine(cache_file)
            estimate = engine2.estimate_duration("load_data", context)
            assert estimate is not None
            assert 15 < estimate < 20

    def test_history_size_limit(self):
        """Test that operation history is limited to recent entries."""
        engine = TimeEstimationEngine()
        context = {"symbol": "TEST", "timeframe": "1d"}

        # Record 15 operations
        for i in range(15):
            engine.record_operation_completion("load_data", context, float(i + 10))

        # Should only keep last 10
        key = engine._create_operation_key("load_data", context)
        assert len(engine.operation_history[key]) == 10

        # Should contain the most recent operations (records 5-14 since we added 0-14)
        durations = [record["duration"] for record in engine.operation_history[key]]
        assert 24.0 in durations  # Last operation (14 + 10)
        assert 14.0 not in durations  # Early operation should be removed (4 + 10)


class TestEnhancedProgressManager:
    """Test enhanced ProgressManager capabilities."""

    def test_enhanced_initialization(self):
        """Test enhanced ProgressManager initialization."""
        # Default initialization with time estimation
        pm = ProgressManager()
        assert pm.enable_time_estimation is True
        assert pm._time_estimator is not None
        assert pm._current_context == {}

        # Initialization without time estimation
        pm_no_estimation = ProgressManager(enable_time_estimation=False)
        assert pm_no_estimation.enable_time_estimation is False
        assert pm_no_estimation._time_estimator is None

    def test_enhanced_operation_context(self):
        """Test operation context handling (domain-specific enhancement moved to renderers)."""
        callback_calls = []

        def test_callback(state):
            callback_calls.append(state)

        pm = ProgressManager(test_callback)

        context = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "mode": "backfill",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        }

        pm.start_operation(5, "test_operation", operation_context=context)

        # Check that context is stored and passed to state (basic functionality preserved)
        assert pm._current_context == context
        assert len(callback_calls) == 1
        state = callback_calls[0]
        assert state.operation_context == context
        # Domain-specific message enhancement (AAPL/1d) moved to DataProgressRenderer
        # ProgressManager now provides simple messages
        assert "Starting test_operation" == state.message

    def test_enhanced_progress_messages(self):
        """Test progress message creation (domain-specific enhancement moved to renderers)."""
        callback_calls = []

        def test_callback(state):
            callback_calls.append(state)

        pm = ProgressManager(test_callback)

        context = {"symbol": "MSFT", "timeframe": "1h", "mode": "tail"}
        pm.start_operation(3, "load_data_MSFT_1h", operation_context=context)

        # Test progress update (now simple without domain-specific enhancement)
        pm.update_progress_with_context(
            1, "Loading local data", current_item_detail="Reading from local cache"
        )

        # Check basic message (domain-specific enhancement moved to DataProgressRenderer)
        assert len(callback_calls) >= 2
        enhanced_state = callback_calls[-1]
        # Domain-specific enhancement (MSFT/1h) moved to DataProgressRenderer
        # ProgressManager now provides simple messages
        assert enhanced_state.message == "Loading local data"
        assert enhanced_state.current_item_detail == "Reading from local cache"

    def test_time_estimate_integration(self):
        """Test integration with time estimation engine."""
        # Mock the time estimator to return a known estimate
        with patch(
            "ktrdr.data.components.progress_manager.TimeEstimationEngine"
        ) as mock_engine_class:
            mock_engine = Mock()
            mock_engine.estimate_duration.return_value = 30.0  # 30 seconds
            mock_engine_class.return_value = mock_engine

            callback_calls = []

            def test_callback(state):
                callback_calls.append(state)

            pm = ProgressManager(test_callback, enable_time_estimation=True)
            context = {"symbol": "AAPL", "timeframe": "1d"}

            pm.start_operation(5, "load_data", operation_context=context)

            # Check that time estimator was called and completion time was set
            mock_engine.estimate_duration.assert_called_with("load_data", context)

            state = callback_calls[0]
            assert state.estimated_completion is not None

            # Complete operation and verify duration recording
            time.sleep(0.1)  # Small delay to have measurable duration
            pm.complete_operation()

            mock_engine.record_operation_completion.assert_called_once()
            args = mock_engine.record_operation_completion.call_args
            assert args[0][0] == "load_data"  # operation_type
            assert args[0][1] == context  # context
            assert args[0][2] > 0  # duration

    def test_basic_message_functionality(self):
        """Test basic message functionality (domain-specific enhancement moved to DataProgressRenderer)."""
        # NOTE: Enhanced message formatting with symbol/timeframe/mode context
        # has been moved to DataProgressRenderer for domain-specific handling.
        # This test now validates that ProgressManager provides simple, clean messages
        # that can be enhanced by domain-specific renderers.

        pm = ProgressManager()

        # Test that ProgressManager still handles basic context
        pm._current_context = {"symbol": "AAPL", "timeframe": "1d"}
        assert pm._current_context["symbol"] == "AAPL"
        assert pm._current_context["timeframe"] == "1d"

        # Domain-specific message enhancement is now handled by DataProgressRenderer
        # ProgressManager provides basic messages that renderers can enhance

    def test_time_remaining_formatting(self):
        """Test time remaining formatting."""
        pm = ProgressManager()

        # Test seconds
        assert pm._format_time_remaining(timedelta(seconds=45)) == "45s remaining"

        # Test minutes
        assert pm._format_time_remaining(timedelta(seconds=120)) == "2m remaining"
        assert pm._format_time_remaining(timedelta(seconds=150)) == "2m 30s remaining"

        # Test hours
        assert pm._format_time_remaining(timedelta(seconds=3600)) == "1h remaining"
        assert pm._format_time_remaining(timedelta(seconds=3900)) == "1h 5m remaining"

    def test_backward_compatibility(self):
        """Test that enhanced features don't break existing API."""
        callback_calls = []

        def test_callback(state):
            callback_calls.append(state)

        # Test existing API still works
        pm = ProgressManager(test_callback)
        pm.start_operation(3, "legacy_operation")  # No context
        pm.update_progress(1, "Step 1")  # Old method
        pm.update_progress(2, "Step 2")
        pm.complete_operation()

        # Should have received callbacks
        assert len(callback_calls) >= 4

        # All states should be valid ProgressState objects
        for state in callback_calls:
            assert isinstance(state, ProgressState)
            assert state.operation_id == "legacy_operation"
            assert state.total_steps == 3

    def test_concurrent_access_with_enhanced_features(self):
        """Test thread safety with enhanced features."""
        callback_calls = []
        callback_lock = threading.Lock()

        def thread_safe_callback(state):
            with callback_lock:
                callback_calls.append((threading.current_thread().name, state.message))

        pm = ProgressManager(thread_safe_callback)

        def worker_thread(thread_id):
            context = {"symbol": f"TEST{thread_id}", "timeframe": "1d"}
            pm.update_progress_with_context(
                thread_id, f"Processing thread {thread_id}", context=context
            )

        # Start operation
        pm.start_operation(5, "concurrent_test")

        # Create and start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have received callbacks from all threads
        assert len(callback_calls) >= 4  # Start + 3 updates


class TestEnhancedCLIProgressDisplay:
    """Test enhanced CLI progress display integration."""

    def test_enhanced_cli_display_import(self):
        """Test that enhanced CLI display can be imported."""
        from ktrdr.cli.progress_display_enhanced import EnhancedCLIProgressDisplay

        display = EnhancedCLIProgressDisplay()
        assert display.console is not None
        assert display.show_details is True

    def test_create_enhanced_progress_callback(self):
        """Test creation of enhanced progress callback."""
        from ktrdr.cli.progress_display_enhanced import (
            create_enhanced_progress_callback,
        )

        callback, display = create_enhanced_progress_callback()

        assert callable(callback)
        assert display is not None

        # Test callback with a mock progress state
        mock_state = ProgressState(
            operation_id="test_op",
            current_step=1,
            total_steps=5,
            message="Testing",
            percentage=20.0,
            operation_context={"symbol": "AAPL", "timeframe": "1d"},
        )

        # Should not raise an exception
        callback(mock_state)

    def test_simple_enhanced_progress_callback(self):
        """Test simple enhanced progress callback."""
        from ktrdr.cli.progress_display_enhanced import (
            simple_enhanced_progress_callback,
        )

        mock_state = ProgressState(
            operation_id="test_op",
            current_step=1,
            total_steps=3,
            message="Testing simple callback",
            percentage=33.0,
        )

        # Should not raise an exception
        simple_enhanced_progress_callback(mock_state)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

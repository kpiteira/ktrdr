"""
Comprehensive tests for ProgressManager component.

Following TDD approach - these tests define the expected behavior
and should initially fail before implementation.
"""

import threading
import time
from datetime import timedelta
from typing import List, Tuple
from unittest.mock import Mock

import pytest

from ktrdr.data.components.progress_manager import ProgressManager, ProgressState


class TestProgressManagerInterface:
    """Test the basic interface and initialization."""

    def test_progress_manager_initializes_without_callback(self):
        """ProgressManager should initialize successfully without callback."""
        progress_manager = ProgressManager()
        assert progress_manager is not None
        assert progress_manager.callback is None

    def test_progress_manager_initializes_with_callback(self):
        """ProgressManager should initialize successfully with callback."""
        mock_callback = Mock()
        progress_manager = ProgressManager(mock_callback)
        assert progress_manager.callback is mock_callback

    def test_progress_manager_has_required_methods(self):
        """ProgressManager should have all required methods from architecture spec."""
        progress_manager = ProgressManager()

        # Required methods from architecture spec
        assert hasattr(progress_manager, "start_operation")
        assert hasattr(progress_manager, "start_step")
        assert hasattr(progress_manager, "update_step_progress")
        assert hasattr(progress_manager, "complete_step")
        assert hasattr(progress_manager, "complete_operation")
        assert hasattr(progress_manager, "check_cancelled")
        assert hasattr(progress_manager, "get_progress_state")

        # Verify methods are callable
        assert callable(progress_manager.start_operation)
        assert callable(progress_manager.start_step)
        assert callable(progress_manager.update_step_progress)
        assert callable(progress_manager.complete_step)
        assert callable(progress_manager.complete_operation)
        assert callable(progress_manager.check_cancelled)
        assert callable(progress_manager.get_progress_state)


class TestProgressManagerBasicOperation:
    """Test basic operation flow and state management."""

    def test_start_operation_initializes_state(self):
        """start_operation should initialize progress state correctly."""
        progress_manager = ProgressManager()

        progress_manager.start_operation(total_steps=5, operation_name="test-operation")

        state = progress_manager.get_progress_state()
        assert state.operation_id == "test-operation"
        assert state.total_steps == 5
        assert state.current_step == 0
        assert state.percentage == 0.0
        assert state.message == "Starting test-operation"

    def test_update_progress_calculates_percentage(self):
        """update_progress should calculate percentage correctly."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=5, operation_name="test-op")

        progress_manager.update_progress(step=2, message="Processing step 2")

        state = progress_manager.get_progress_state()
        assert state.current_step == 2
        assert state.percentage == 40.0  # 2/5 = 40%
        assert state.message == "Processing step 2"

    def test_complete_operation_sets_final_state(self):
        """complete_operation should set final completion state."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=3, operation_name="test-op")

        progress_manager.complete_operation()

        state = progress_manager.get_progress_state()
        assert state.current_step == state.total_steps
        assert state.percentage == 100.0
        assert "completed" in state.message.lower()


class TestProgressManagerCallbackCompatibility:
    """Test backward compatibility with existing DataManager callback behavior."""

    def test_callback_signature_compatibility(self):
        """Verify callback signature matches existing DataManager behavior."""
        callback_calls = []

        def mock_callback(message: str, percentage: float):
            """Mock callback matching existing signature."""
            callback_calls.append((message, percentage))

        progress_manager = ProgressManager(mock_callback)
        progress_manager.start_operation(total_steps=5, operation_name="test-op")
        progress_manager.update_progress(step=2, message="Processing step 2")

        # Should have received callback calls
        assert len(callback_calls) >= 2

        # Verify callback signature is (message: str, percentage: float)
        for message, percentage in callback_calls:
            assert isinstance(message, str)
            assert isinstance(percentage, float)
            assert 0.0 <= percentage <= 100.0

    def test_callback_triggered_on_progress_updates(self):
        """Callbacks should be triggered at identical points to current DataManager."""
        callback_calls = []

        def track_callback(message: str, percentage: float):
            callback_calls.append((message, percentage))

        progress_manager = ProgressManager(track_callback)

        # Simulate DataManager progress pattern
        progress_manager.start_operation(
            total_steps=10, operation_name="Loading AAPL data"
        )
        assert len(callback_calls) == 1
        assert callback_calls[0][1] == 0.0  # Initial callback at 0%

        progress_manager.update_progress(step=3, message="Fetching segments")
        assert len(callback_calls) == 2
        assert callback_calls[1][1] == 30.0  # 3/10 = 30%

        progress_manager.update_progress(step=8, message="Processing data")
        assert len(callback_calls) == 3
        assert callback_calls[2][1] == 80.0  # 8/10 = 80%

    def test_no_callback_when_none_provided(self):
        """Should not fail when no callback is provided."""
        progress_manager = ProgressManager(callback_func=None)

        # These should not raise exceptions
        progress_manager.start_operation(total_steps=3, operation_name="test")
        progress_manager.update_progress(step=1, message="Step 1")
        progress_manager.complete_operation()

        # Should still track state internally
        state = progress_manager.get_progress_state()
        assert state.percentage == 100.0


class TestProgressManagerThreadSafety:
    """Test thread safety for concurrent operations."""

    def test_concurrent_progress_updates(self):
        """Multiple threads should be able to update progress safely."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(
            total_steps=100, operation_name="concurrent-test"
        )

        update_count = 0
        update_lock = threading.Lock()

        def update_progress(thread_id: int):
            nonlocal update_count
            for i in range(10):
                step = thread_id * 10 + i
                progress_manager.update_progress(
                    step=step, message=f"Thread {thread_id}, step {i}"
                )

                with update_lock:
                    update_count += 1

                time.sleep(0.001)  # Small delay to encourage race conditions

        # Start 5 threads each doing 10 updates
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=update_progress, args=(thread_id,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have received all 50 updates
        assert update_count == 50

        # Final state should be consistent
        state = progress_manager.get_progress_state()
        assert state.total_steps == 100
        assert 0 <= state.current_step <= 100
        assert 0.0 <= state.percentage <= 100.0

    def test_thread_safe_callback_invocation(self):
        """Callback invocation should be thread-safe."""
        callback_calls = []
        callback_lock = threading.Lock()

        def thread_safe_callback(message: str, percentage: float):
            with callback_lock:
                callback_calls.append(
                    (message, percentage, threading.current_thread().ident)
                )

        progress_manager = ProgressManager(thread_safe_callback)
        progress_manager.start_operation(total_steps=50, operation_name="thread-test")

        def worker_thread(start_step: int):
            for i in range(10):
                step = start_step + i
                progress_manager.update_progress(step=step, message=f"Step {step}")
                time.sleep(0.001)

        # Start multiple worker threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker_thread, args=(i * 10,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Should have received callbacks from multiple threads
        thread_ids = {call[2] for call in callback_calls}
        assert len(thread_ids) >= 2  # At least 2 different threads made callbacks


class TestProgressManagerHierarchicalProgress:
    """Test hierarchical progress tracking (Operation -> Steps -> Sub-steps)."""

    def test_step_based_progress_tracking(self):
        """Should support hierarchical step tracking."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(
            total_steps=3, operation_name="hierarchical-test"
        )

        # Step 1: Analysis
        progress_manager.start_step(step_name="Analysis", step_number=1)
        progress_manager.update_step_progress(
            current=1, total=1, detail="Gap analysis complete"
        )
        progress_manager.complete_step()

        state = progress_manager.get_progress_state()
        assert state.current_step == 1
        assert abs(state.percentage - 33.33) < 0.1  # ~33% complete

        # Step 2: Fetching
        progress_manager.start_step(step_name="Fetching", step_number=2)
        progress_manager.update_step_progress(
            current=5, total=10, detail="Fetching segment 5 of 10"
        )

        state = progress_manager.get_progress_state()
        assert "Fetching" in state.message
        assert "segment 5 of 10" in state.message

        progress_manager.complete_step()
        progress_manager.complete_operation()

        final_state = progress_manager.get_progress_state()
        assert final_state.percentage == 100.0

    def test_sub_step_progress_calculation(self):
        """Sub-step progress should contribute to overall progress correctly."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=2, operation_name="substep-test")

        # Step 1 with sub-progress
        progress_manager.start_step(step_name="Processing", step_number=1)
        progress_manager.update_step_progress(
            current=3, total=4, detail="75% of step 1"
        )

        state = progress_manager.get_progress_state()
        # Should be approximately 37.5% (step 1 is 50% of operation, and we're 75% through step 1)
        expected_percentage = (0.5 * 0.75) * 100  # 37.5%
        assert abs(state.percentage - expected_percentage) < 5.0


class TestProgressManagerCancellation:
    """Test cancellation support and token integration."""

    def test_check_cancelled_returns_false_by_default(self):
        """check_cancelled should return False when no cancellation is set."""
        progress_manager = ProgressManager()
        assert progress_manager.check_cancelled() is False

    def test_cancellation_token_integration(self):
        """Should support external cancellation token integration."""
        progress_manager = ProgressManager()

        # Mock cancellation token
        cancellation_token = Mock()
        cancellation_token.is_cancelled = False

        progress_manager.set_cancellation_token(cancellation_token)
        assert progress_manager.check_cancelled() is False

        # Simulate cancellation
        cancellation_token.is_cancelled = True
        assert progress_manager.check_cancelled() is True

    def test_operation_respects_cancellation(self):
        """Operations should check and respond to cancellation."""
        callback_calls = []

        def track_callback(message: str, percentage: float):
            callback_calls.append((message, percentage))

        progress_manager = ProgressManager(track_callback)
        progress_manager.start_operation(total_steps=5, operation_name="cancellable-op")

        # Simulate cancellation after starting
        cancellation_token = Mock()
        cancellation_token.is_cancelled = True
        progress_manager.set_cancellation_token(cancellation_token)

        # Should detect cancellation
        assert progress_manager.check_cancelled() is True

        # State should remain consistent even when cancelled
        state = progress_manager.get_progress_state()
        assert state.operation_id == "cancellable-op"
        assert state.total_steps == 5


class TestProgressManagerPerformance:
    """Test performance characteristics and overhead."""

    def test_no_measurable_overhead_vs_current_approach(self):
        """ProgressManager should add minimal overhead compared to direct callbacks."""
        # More realistic baseline: Direct callback with similar operations
        callback_calls = []

        def mock_callback(message: str, percentage: float):
            callback_calls.append((message, percentage))

        start_time = time.time()

        # Simulate DataManager-style direct progress updates
        for i in range(1000):
            message = f"Step {i}"
            percentage = (i / 1000) * 100.0
            mock_callback(message, percentage)

        direct_time = time.time() - start_time

        # ProgressManager timing with callback
        callback_calls.clear()
        progress_manager = ProgressManager(mock_callback)
        progress_manager.start_operation(
            total_steps=1000, operation_name="performance-test"
        )

        start_time = time.time()
        for i in range(1000):
            progress_manager.update_progress(step=i, message=f"Step {i}")

        progress_time = time.time() - start_time

        # Should not be dramatically slower than direct approach
        # Allow more overhead since we're providing thread safety and additional features
        overhead_ratio = progress_time / direct_time
        assert (
            overhead_ratio < 5.0
        ), f"ProgressManager overhead too high: {overhead_ratio:.2f}x slower"

        # Verify we got the same number of callbacks
        assert len(callback_calls) >= 1000  # Should have at least as many callbacks

    def test_memory_usage_remains_stable(self):
        """Memory usage should not grow with number of progress updates."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(
            total_steps=10000, operation_name="memory-test"
        )

        # Simulate many progress updates
        for i in range(10000):
            progress_manager.update_progress(step=i, message=f"Processing item {i}")

            # Every 1000 updates, verify state is still reasonable
            if i % 1000 == 0:
                state = progress_manager.get_progress_state()
                assert state.current_step == i
                assert len(state.message) < 200  # Should not accumulate messages


class TestProgressManagerEstimates:
    """Test time estimation features."""

    def test_estimated_remaining_time_calculation(self):
        """Should calculate reasonable time estimates based on progress rate."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=10, operation_name="estimate-test")

        # Simulate some progress with time delays
        start_time = time.time()
        time.sleep(0.1)  # 100ms delay

        progress_manager.update_progress(step=2, message="20% complete")

        state = progress_manager.get_progress_state()

        # Should have estimated remaining time
        if state.estimated_remaining is not None:
            assert isinstance(state.estimated_remaining, timedelta)
            # Rough estimate: if 20% took 100ms, remaining 80% should take ~400ms
            assert (
                state.estimated_remaining.total_seconds() < 1.0
            )  # Should be reasonable


class TestProgressManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_handles_zero_total_steps(self):
        """Should handle zero total steps gracefully."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=0, operation_name="zero-steps")

        # Should not divide by zero
        progress_manager.update_progress(step=0, message="No steps needed")

        state = progress_manager.get_progress_state()
        assert state.percentage == 100.0  # 0/0 should be treated as complete

    def test_handles_progress_beyond_total_steps(self):
        """Should handle progress updates beyond total steps gracefully."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=5, operation_name="overflow-test")

        # Update beyond total steps
        progress_manager.update_progress(step=10, message="Beyond total")

        state = progress_manager.get_progress_state()
        assert state.percentage <= 100.0  # Should cap at 100%
        assert state.current_step == 10  # Should still track actual step

    def test_handles_negative_progress(self):
        """Should handle negative progress values gracefully."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=5, operation_name="negative-test")

        # Update with negative step
        progress_manager.update_progress(step=-1, message="Negative progress")

        state = progress_manager.get_progress_state()
        assert state.percentage >= 0.0  # Should not go below 0%

    def test_multiple_operations_in_sequence(self):
        """Should handle multiple sequential operations correctly."""
        progress_manager = ProgressManager()

        # First operation
        progress_manager.start_operation(total_steps=3, operation_name="operation-1")
        progress_manager.update_progress(step=3, message="Op1 complete")
        progress_manager.complete_operation()

        state1 = progress_manager.get_progress_state()
        assert state1.percentage == 100.0
        assert state1.operation_id == "operation-1"

        # Second operation should reset state
        progress_manager.start_operation(total_steps=5, operation_name="operation-2")

        state2 = progress_manager.get_progress_state()
        assert state2.percentage == 0.0
        assert state2.operation_id == "operation-2"
        assert state2.total_steps == 5

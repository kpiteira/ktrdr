"""
Tests for ProgressManager component.

This test suite covers the core ProgressManager functionality after the
complete integration with DataManager, focusing on the current API.
"""

import threading
import time
from unittest.mock import Mock

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
        """ProgressManager should have all required methods."""
        progress_manager = ProgressManager()

        # Required methods
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


class TestProgressManagerCallbacks:
    """Test callback behavior with ProgressState objects."""

    def test_callback_receives_progress_state(self):
        """Verify callback receives ProgressState objects."""
        callback_calls = []

        def progress_state_callback(progress_state: ProgressState):
            """Callback that receives ProgressState objects."""
            callback_calls.append(progress_state)

        progress_manager = ProgressManager(progress_state_callback)
        progress_manager.start_operation(total_steps=5, operation_name="test-op")
        progress_manager.update_progress(step=2, message="Processing step 2")

        # Should have received callback calls
        assert len(callback_calls) >= 2

        # Verify callback receives ProgressState objects
        for progress_state in callback_calls:
            assert isinstance(progress_state, ProgressState)
            assert hasattr(progress_state, "percentage")
            assert hasattr(progress_state, "message")
            assert hasattr(progress_state, "current_step")
            assert 0.0 <= progress_state.percentage <= 100.0

    def test_no_callback_when_none_provided(self):
        """No errors should occur when no callback is provided."""
        progress_manager = ProgressManager()  # No callback
        progress_manager.start_operation(total_steps=3, operation_name="test-op")
        progress_manager.update_progress(step=1, message="Step 1")
        progress_manager.complete_operation()

        # Should complete without error
        state = progress_manager.get_progress_state()
        assert state.percentage == 100.0


class TestProgressManagerThreadSafety:
    """Test thread safety of ProgressManager."""

    def test_concurrent_progress_updates(self):
        """Multiple threads should be able to update progress safely."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(
            total_steps=100, operation_name="concurrent-test"
        )

        results = []
        errors = []

        def update_progress_worker(thread_id: int):
            """Worker function for concurrent updates."""
            try:
                for i in range(10):
                    step = thread_id * 10 + i
                    progress_manager.update_progress(
                        step=step, message=f"Thread {thread_id} step {i}"
                    )
                    time.sleep(0.001)  # Small delay to encourage race conditions
                results.append(f"Thread {thread_id} completed")
            except Exception as e:
                errors.append(f"Thread {thread_id} error: {e}")

        # Start multiple threads
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=update_progress_worker, args=(thread_id,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)

        # Should complete without errors
        assert len(errors) == 0, f"Encountered errors: {errors}"
        assert len(results) == 5


class TestProgressManagerHierarchicalProgress:
    """Test hierarchical progress tracking with steps and sub-steps."""

    def test_step_based_progress_tracking(self):
        """Test step-based progress tracking functionality."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(
            total_steps=3, operation_name="hierarchical-test"
        )

        # Step 1
        progress_manager.start_step("Step 1", step_number=1)
        state = progress_manager.get_progress_state()
        assert state.current_step == 1
        assert state.current_step_name == "Step 1"
        assert 0.0 <= state.percentage <= 100.0

        # Step 2
        progress_manager.start_step("Step 2", step_number=2)
        state = progress_manager.get_progress_state()
        assert state.current_step == 2
        assert state.current_step_name == "Step 2"

        # Complete operation
        progress_manager.complete_operation()
        state = progress_manager.get_progress_state()
        assert state.percentage == 100.0

    def test_sub_step_progress_with_items(self):
        """Test sub-step progress with item tracking."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(
            total_steps=2, operation_name="item-test", expected_items=100
        )

        # Start step with item processing
        progress_manager.start_step(
            "Processing items", step_number=1, expected_items=50
        )

        # Update with item progress
        progress_manager.update_step_progress(
            current=25, total=50, items_processed=25, detail="Processing batch 1"
        )

        state = progress_manager.get_progress_state()
        assert state.step_current == 25
        assert state.step_total == 50
        assert state.items_processed == 25
        assert state.step_detail == "Processing batch 1"


class TestProgressManagerCancellation:
    """Test cancellation token integration."""

    def test_check_cancelled_returns_false_by_default(self):
        """check_cancelled should return False when no token is set."""
        progress_manager = ProgressManager()
        assert progress_manager.check_cancelled() is False

    def test_cancellation_token_integration(self):
        """Test cancellation token with unified is_cancelled() method."""
        progress_manager = ProgressManager()

        # Mock cancellation token with unified protocol
        mock_token = Mock()
        mock_token.is_cancelled.return_value = False

        progress_manager.set_cancellation_token(mock_token)
        assert progress_manager.check_cancelled() is False

        mock_token.is_cancelled.return_value = True
        assert progress_manager.check_cancelled() is True


class TestProgressManagerEdgeCases:
    """Test edge cases and error scenarios."""

    def test_handles_zero_total_steps(self):
        """Should handle zero total steps gracefully."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=0, operation_name="zero-steps")

        state = progress_manager.get_progress_state()
        assert state.total_steps == 0
        assert state.percentage == 0.0

        # Complete operation should work
        progress_manager.complete_operation()
        final_state = progress_manager.get_progress_state()
        assert final_state.percentage == 100.0

    def test_handles_negative_progress(self):
        """Should handle negative progress values gracefully."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=5, operation_name="negative-test")

        # Negative step should be clamped to non-negative
        progress_manager.update_progress(step=-1, message="Negative step")
        state = progress_manager.get_progress_state()
        assert state.percentage >= 0.0

    def test_get_progress_state_without_operation(self):
        """get_progress_state should work even without active operation."""
        progress_manager = ProgressManager()

        state = progress_manager.get_progress_state()
        assert isinstance(state, ProgressState)
        assert state.operation_id == ""
        assert state.total_steps == 0
        assert state.percentage == 0.0
        assert state.message == "No active operation"

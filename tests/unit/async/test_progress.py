"""
Comprehensive test suite for generic progress infrastructure.

This test suite covers:
- GenericProgressState data class validation
- ProgressRenderer abstract base class contract
- GenericProgressManager with TimeEstimationEngine integration
- Thread safety validation with RLock usage
- Callback failure handling and recovery
- Progress state transitions and validation
"""

import threading
import time
from abc import ABC
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from ktrdr.async_infrastructure.progress import (
    GenericProgressManager,
    GenericProgressState,
    ProgressRenderer,
)


class TestGenericProgressState:
    """Test suite for GenericProgressState data class."""

    def test_generic_progress_state_required_fields(self):
        """Test that GenericProgressState has all required fields."""
        # This test will fail until we implement GenericProgressState
        state = GenericProgressState(
            operation_id="test_op",
            current_step=1,
            total_steps=5,
            percentage=20.0,
            message="Testing progress",
        )

        assert state.operation_id == "test_op"
        assert state.current_step == 1
        assert state.total_steps == 5
        assert state.percentage == 20.0
        assert state.message == "Testing progress"

    def test_generic_progress_state_default_fields(self):
        """Test that GenericProgressState has proper default values."""
        state = GenericProgressState(
            operation_id="test_op",
            current_step=0,
            total_steps=1,
            percentage=0.0,
            message="Starting",
        )

        # Test default fields
        assert isinstance(state.start_time, datetime)
        assert state.context == {}
        assert state.estimated_remaining is None
        assert state.items_processed == 0
        assert state.total_items is None

    def test_generic_progress_state_context_updates(self):
        """Test that context can be updated and preserved."""
        state = GenericProgressState(
            operation_id="test_op",
            current_step=1,
            total_steps=5,
            percentage=20.0,
            message="Processing",
            context={"symbol": "AAPL", "timeframe": "1h"},
        )

        assert state.context["symbol"] == "AAPL"
        assert state.context["timeframe"] == "1h"

        # Context should be mutable
        state.context["mode"] = "backfill"
        assert state.context["mode"] == "backfill"

    def test_generic_progress_state_timing_fields(self):
        """Test timing-related fields work correctly."""
        start_time = datetime.now()
        estimated_remaining = timedelta(minutes=5)

        state = GenericProgressState(
            operation_id="test_op",
            current_step=2,
            total_steps=10,
            percentage=20.0,
            message="Processing",
            start_time=start_time,
            estimated_remaining=estimated_remaining,
        )

        assert state.start_time == start_time
        assert state.estimated_remaining == estimated_remaining

    def test_generic_progress_state_item_tracking(self):
        """Test item processing tracking fields."""
        state = GenericProgressState(
            operation_id="test_op",
            current_step=3,
            total_steps=5,
            percentage=60.0,
            message="Processing items",
            items_processed=150,
            total_items=250,
        )

        assert state.items_processed == 150
        assert state.total_items == 250


class TestProgressRenderer:
    """Test suite for ProgressRenderer abstract base class."""

    def test_progress_renderer_is_abstract(self):
        """Test that ProgressRenderer cannot be instantiated directly."""
        # This test will fail until we implement ProgressRenderer
        with pytest.raises(TypeError):
            ProgressRenderer()

    def test_progress_renderer_abstract_methods(self):
        """Test that ProgressRenderer has required abstract methods."""
        # Verify abstract methods are defined
        assert hasattr(ProgressRenderer, "render_message")
        assert hasattr(ProgressRenderer, "enhance_state")

        # Check they are abstract
        assert getattr(ProgressRenderer.render_message, "__isabstractmethod__", False)
        assert getattr(ProgressRenderer.enhance_state, "__isabstractmethod__", False)

    def test_progress_renderer_subclass_implementation(self):
        """Test that concrete ProgressRenderer subclass works correctly."""

        class TestProgressRenderer(ProgressRenderer):
            def render_message(self, state: GenericProgressState) -> str:
                return f"Test: {state.message} ({state.percentage:.1f}%)"

            def enhance_state(
                self, state: GenericProgressState
            ) -> GenericProgressState:
                state.context["enhanced"] = True
                return state

        renderer = TestProgressRenderer()
        state = GenericProgressState(
            operation_id="test",
            current_step=1,
            total_steps=2,
            percentage=50.0,
            message="Testing",
        )

        # Test render_message
        message = renderer.render_message(state)
        assert message == "Test: Testing (50.0%)"

        # Test enhance_state
        enhanced_state = renderer.enhance_state(state)
        assert enhanced_state.context["enhanced"] is True

    def test_progress_renderer_inheritance_check(self):
        """Test that ProgressRenderer is properly abstract."""
        assert issubclass(ProgressRenderer, ABC)


class TestGenericProgressManager:
    """Test suite for GenericProgressManager core functionality."""

    def test_generic_progress_manager_initialization(self):
        """Test GenericProgressManager initializes correctly."""
        callback = Mock()
        renderer = Mock(spec=ProgressRenderer)

        # This test will fail until we implement GenericProgressManager
        manager = GenericProgressManager(callback=callback, renderer=renderer)

        assert manager.callback == callback
        assert manager.renderer == renderer

    def test_generic_progress_manager_no_callback_renderer(self):
        """Test GenericProgressManager works without callback or renderer."""
        manager = GenericProgressManager()

        assert manager.callback is None
        assert manager.renderer is None

    def test_generic_progress_manager_start_operation(self):
        """Test starting an operation updates state correctly."""
        callback = Mock()
        renderer = Mock(spec=ProgressRenderer)
        renderer.enhance_state.return_value = GenericProgressState(
            operation_id="test_op",
            current_step=0,
            total_steps=5,
            percentage=0.0,
            message="Starting test_op",
        )
        renderer.render_message.return_value = "Starting test_op"

        manager = GenericProgressManager(callback=callback, renderer=renderer)
        manager.start_operation(
            operation_id="test_op", total_steps=5, context={"symbol": "AAPL"}
        )

        # Verify renderer was called
        renderer.enhance_state.assert_called_once()
        renderer.render_message.assert_called_once()

        # Verify callback was triggered
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args.operation_id == "test_op"
        assert call_args.total_steps == 5

    def test_generic_progress_manager_update_progress(self):
        """Test updating progress works correctly."""
        callback = Mock()
        renderer = Mock(spec=ProgressRenderer)

        # Mock renderer responses for different calls
        def mock_enhance_state(state):
            return state

        def mock_render_message(state):
            return f"Step {state.current_step}: {state.message}"

        renderer.enhance_state.side_effect = mock_enhance_state
        renderer.render_message.side_effect = mock_render_message

        manager = GenericProgressManager(callback=callback, renderer=renderer)
        manager.start_operation("test_op", 10)
        callback.reset_mock()  # Reset after start_operation

        manager.update_progress(
            step=3,
            message="Processing data",
            items_processed=150,
            context={"current_segment": 2},
        )

        # Verify callback was called with updated state
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args.current_step == 3
        assert call_args.percentage == 30.0  # 3/10 * 100
        assert call_args.items_processed == 150

    def test_generic_progress_manager_complete_operation(self):
        """Test completing operation sets state to 100%."""
        callback = Mock()
        renderer = Mock(spec=ProgressRenderer)
        renderer.enhance_state.side_effect = lambda state: state
        renderer.render_message.side_effect = lambda state: state.message

        manager = GenericProgressManager(callback=callback, renderer=renderer)
        manager.start_operation("test_op", 5)
        callback.reset_mock()

        manager.complete_operation()

        # Verify final callback with completion
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args.current_step == 5
        assert call_args.percentage == 100.0

    def test_generic_progress_manager_without_renderer(self):
        """Test GenericProgressManager works without renderer."""
        callback = Mock()
        manager = GenericProgressManager(callback=callback)

        manager.start_operation("test_op", 3)
        manager.update_progress(1, "Step 1")
        manager.complete_operation()

        # Should have been called 3 times (start, update, complete)
        assert callback.call_count == 3


class TestGenericProgressManagerThreadSafety:
    """Test suite for GenericProgressManager thread safety."""

    def test_generic_progress_manager_has_rlock(self):
        """Test GenericProgressManager uses RLock for thread safety."""
        manager = GenericProgressManager()

        # Should have _lock attribute that is an RLock
        assert hasattr(manager, "_lock")
        assert type(manager._lock).__name__ == "RLock"

    def test_concurrent_progress_updates(self):
        """Test concurrent progress updates are thread-safe."""
        callback = Mock()
        manager = GenericProgressManager(callback=callback)
        manager.start_operation("concurrent_test", 100)

        results = []
        exceptions = []

        def update_progress_worker(start_step: int, count: int):
            """Worker function to update progress concurrently."""
            try:
                for i in range(count):
                    step = start_step + i
                    manager.update_progress(step, f"Step {step}")
                    results.append(step)
                    time.sleep(
                        0.001
                    )  # Small delay to increase chance of race conditions
            except Exception as e:
                exceptions.append(e)

        # Start multiple threads updating progress
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_progress_worker, args=(i * 10, 10))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no exceptions occurred
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"

        # Verify all updates were recorded
        assert len(results) == 50  # 5 threads * 10 updates each

    def test_concurrent_start_operations(self):
        """Test concurrent start operations are handled safely."""
        callback = Mock()
        manager = GenericProgressManager(callback=callback)

        exceptions = []

        def start_operation_worker(operation_id: str):
            """Worker function to start operations concurrently."""
            try:
                manager.start_operation(operation_id, 10)
                time.sleep(0.01)
            except Exception as e:
                exceptions.append(e)

        # Start multiple threads starting operations
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=start_operation_worker, args=(f"operation_{i}",)
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no exceptions occurred
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"


class TestGenericProgressManagerCallbackHandling:
    """Test suite for GenericProgressManager callback failure handling."""

    def test_callback_failure_handling(self):
        """Test that callback failures are handled gracefully."""

        def failing_callback(state):
            raise ValueError("Callback failed")

        # This should not raise an exception
        manager = GenericProgressManager(callback=failing_callback)

        # These operations should complete despite callback failures
        manager.start_operation("test_op", 5)
        manager.update_progress(1, "Step 1")
        manager.complete_operation()

    def test_callback_failure_logging(self):
        """Test that callback failures are logged appropriately."""

        def failing_callback(state):
            raise RuntimeError("Test callback failure")

        manager = GenericProgressManager(callback=failing_callback)

        with patch("ktrdr.async_infrastructure.progress.logger") as mock_logger:
            manager.start_operation("test_op", 3)

            # Should have logged the callback failure
            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args[0][0]
            assert "callback failed" in call_args.lower()

    def test_none_callback_handling(self):
        """Test that None callback is handled without errors."""
        manager = GenericProgressManager(callback=None)

        # Should work without any issues
        manager.start_operation("test_op", 2)
        manager.update_progress(1, "Step 1")
        manager.complete_operation()

    def test_callback_receives_correct_state_type(self):
        """Test that callback receives GenericProgressState instances."""
        received_states = []

        def capturing_callback(state):
            received_states.append(state)
            assert isinstance(state, GenericProgressState)

        manager = GenericProgressManager(callback=capturing_callback)
        manager.start_operation("test_op", 2, context={"test": "value"})
        manager.update_progress(1, "Step 1", items_processed=50)
        manager.complete_operation()

        assert len(received_states) == 3  # start, update, complete

        # Check start state
        start_state = received_states[0]
        assert start_state.operation_id == "test_op"
        assert start_state.current_step == 0
        assert start_state.percentage == 0.0
        assert start_state.context["test"] == "value"

        # Check update state
        update_state = received_states[1]
        assert update_state.current_step == 1
        assert update_state.percentage == 50.0  # 1/2 * 100
        assert update_state.items_processed == 50

        # Check completion state
        complete_state = received_states[2]
        assert complete_state.current_step == 2
        assert complete_state.percentage == 100.0


class TestGenericProgressManagerIntegration:
    """Integration tests for GenericProgressManager with existing patterns."""

    def test_time_estimation_engine_integration(self):
        """Test integration with TimeEstimationEngine from existing ProgressManager."""
        # Import existing TimeEstimationEngine
        from ktrdr.data.components.progress_manager import TimeEstimationEngine

        callback = Mock()

        # Create a test renderer that works with TimeEstimationEngine
        class TestRenderer(ProgressRenderer):
            def __init__(self, time_estimator: TimeEstimationEngine):
                self.time_estimator = time_estimator

            def render_message(self, state: GenericProgressState) -> str:
                return f"{state.message} [{state.current_step}/{state.total_steps}]"

            def enhance_state(
                self, state: GenericProgressState
            ) -> GenericProgressState:
                # Add time estimation logic similar to existing ProgressManager
                if state.current_step > 0 and state.percentage > 0:
                    # Simple estimation for testing
                    estimated_seconds = (
                        100 - state.percentage
                    ) * 2  # 2 seconds per percent
                    state.estimated_remaining = timedelta(seconds=estimated_seconds)
                return state

        # Create time estimator
        time_estimator = TimeEstimationEngine()
        renderer = TestRenderer(time_estimator)

        manager = GenericProgressManager(callback=callback, renderer=renderer)
        manager.start_operation(
            "data_load_test", 10, context={"symbol": "AAPL", "timeframe": "1h"}
        )

        # Simulate progress updates
        for step in range(1, 11):
            manager.update_progress(step, f"Processing step {step}")

        manager.complete_operation()

        # Verify callback was called appropriately
        assert callback.call_count >= 11  # start + 10 updates + complete

    def test_backwards_compatibility_with_progress_state(self):
        """Test backwards compatibility with existing ProgressState patterns."""
        from ktrdr.data.components.progress_manager import ProgressState

        # Test that we can convert between GenericProgressState and ProgressState
        generic_state = GenericProgressState(
            operation_id="test_op",
            current_step=3,
            total_steps=10,
            percentage=30.0,
            message="Processing data",
            items_processed=150,
            total_items=500,
            context={"symbol": "AAPL", "timeframe": "1h"},
        )

        # A renderer should be able to create legacy ProgressState for backward compatibility
        class BackwardCompatibleRenderer(ProgressRenderer):
            def render_message(self, state: GenericProgressState) -> str:
                return state.message

            def enhance_state(
                self, state: GenericProgressState
            ) -> GenericProgressState:
                return state

            def create_legacy_compatible_state(
                self, generic_state: GenericProgressState
            ) -> ProgressState:
                """Convert generic state to legacy ProgressState."""
                return ProgressState(
                    operation_id=generic_state.operation_id,
                    current_step=generic_state.current_step,
                    total_steps=generic_state.total_steps,
                    message=generic_state.message,
                    percentage=generic_state.percentage,
                    estimated_remaining=generic_state.estimated_remaining,
                    start_time=generic_state.start_time,
                    steps_completed=generic_state.current_step,
                    steps_total=generic_state.total_steps,
                    expected_items=generic_state.total_items,
                    items_processed=generic_state.items_processed,
                    operation_context=generic_state.context,
                )

        renderer = BackwardCompatibleRenderer()
        legacy_state = renderer.create_legacy_compatible_state(generic_state)

        # Verify legacy state has expected fields
        assert isinstance(legacy_state, ProgressState)
        assert legacy_state.operation_id == "test_op"
        assert legacy_state.current_step == 3
        assert legacy_state.percentage == 30.0
        assert legacy_state.items_processed == 150
        assert legacy_state.operation_context["symbol"] == "AAPL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

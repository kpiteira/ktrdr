"""
Test backward compatibility with existing DataManager progress patterns.

This test verifies that ProgressManager can replace the embedded progress
logic in DataManager without breaking existing code.
"""

import pytest
from unittest.mock import Mock

from ktrdr.data.components.progress_manager import ProgressManager
from ktrdr.data.data_manager import DataLoadingProgress


class TestDataManagerCompatibility:
    """Test compatibility with existing DataManager progress patterns."""

    def test_datamanager_progress_pattern_simulation(self):
        """Simulate the exact progress pattern used in DataManager.load_data()."""
        callback_calls = []

        def datamanager_style_callback(message: str, percentage: float):
            """Simulate existing DataManager callback."""
            callback_calls.append({"message": message, "percentage": percentage})

        # Simulate DataManager progress pattern using ProgressManager
        progress_manager = ProgressManager(datamanager_style_callback)

        # DataManager pattern: Start with operation name
        progress_manager.start_operation(
            total_steps=10, operation_name="Loading AAPL data"
        )

        # Simulate key progress points from actual DataManager
        progress_manager.update_progress(step=0, message="Starting data load for AAPL")
        assert callback_calls[-1]["percentage"] == 0.0

        progress_manager.update_progress(step=2, message="Analyzing gaps")
        assert callback_calls[-1]["percentage"] == 20.0

        progress_manager.update_progress(step=3, message="Fetching segments")
        assert callback_calls[-1]["percentage"] == 30.0

        progress_manager.update_progress(step=8, message="Processing data")
        assert callback_calls[-1]["percentage"] == 80.0

        progress_manager.complete_operation()
        assert callback_calls[-1]["percentage"] == 100.0

        # Verify we got the expected number of callbacks
        assert len(callback_calls) >= 5

        # Verify all callback messages are strings and percentages are floats
        for call in callback_calls:
            assert isinstance(call["message"], str)
            assert isinstance(call["percentage"], float)
            assert 0.0 <= call["percentage"] <= 100.0

    def test_progress_state_compatibility_with_dataloadingprogress(self):
        """Verify ProgressState has similar structure to DataLoadingProgress."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=5, operation_name="test-op")
        progress_manager.update_progress(step=2, message="Processing")

        state = progress_manager.get_progress_state()

        # Check compatibility fields exist
        assert hasattr(state, "percentage")
        assert hasattr(state, "current_step")
        assert hasattr(state, "steps_completed")
        assert hasattr(state, "steps_total")
        assert hasattr(state, "operation_id")  # Similar to operation name

        # Check values are reasonable
        assert state.percentage == 40.0  # 2/5 = 40%
        assert state.current_step == 2
        assert state.steps_completed == 2
        assert state.steps_total == 5

    def test_hierarchical_progress_compatibility(self):
        """Test that hierarchical progress works like DataManager segment progress."""
        callback_calls = []

        def track_callback(message: str, percentage: float):
            callback_calls.append((message, percentage))

        progress_manager = ProgressManager(track_callback)

        # Simulate DataManager segment fetching pattern
        progress_manager.start_operation(
            total_steps=3, operation_name="Loading MSFT 1h"
        )

        # Step 1: Gap analysis
        progress_manager.start_step("Gap Analysis", 1)
        progress_manager.update_step_progress(1, 1, "Found 5 gaps")
        progress_manager.complete_step()

        # Step 2: Segment fetching (with sub-progress)
        progress_manager.start_step("Fetching segments", 2)

        # Simulate fetching multiple segments
        for i in range(1, 6):  # 5 segments
            progress_manager.update_step_progress(
                i, 5, f"Segment {i}/5: 2023-01-{i:02d}"
            )

        progress_manager.complete_step()

        # Step 3: Data processing
        progress_manager.start_step("Processing data", 3)
        progress_manager.complete_step()
        progress_manager.complete_operation()

        # Should have received progress callbacks throughout
        assert len(callback_calls) > 10  # Multiple updates

        # Final callback should be 100%
        assert callback_calls[-1][1] == 100.0

        # Should have detailed messages about segments
        segment_messages = [call[0] for call in callback_calls if "Segment" in call[0]]
        assert len(segment_messages) >= 5

    def test_no_callback_compatibility(self):
        """Test behavior when no callback is provided (like some DataManager calls)."""
        progress_manager = ProgressManager(callback_func=None)

        # Should not fail when no callback is set
        progress_manager.start_operation(total_steps=3, operation_name="silent-op")
        progress_manager.update_progress(step=1, message="Step 1")
        progress_manager.update_progress(step=2, message="Step 2")
        progress_manager.complete_operation()

        # Should still track state internally
        state = progress_manager.get_progress_state()
        assert state.percentage == 100.0
        assert state.operation_id == "silent-op"

    def test_cancellation_compatibility(self):
        """Test cancellation integration similar to DataManager patterns."""
        progress_manager = ProgressManager()
        progress_manager.start_operation(total_steps=5, operation_name="cancellable-op")

        # Initially not cancelled
        assert progress_manager.check_cancelled() is False

        # Simulate external cancellation token
        cancellation_token = Mock()
        cancellation_token.is_cancelled = False

        progress_manager.set_cancellation_token(cancellation_token)
        assert progress_manager.check_cancelled() is False

        # Simulate cancellation
        cancellation_token.is_cancelled = True
        assert progress_manager.check_cancelled() is True

        # State should remain consistent
        state = progress_manager.get_progress_state()
        assert state.operation_id == "cancellable-op"

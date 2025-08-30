"""
Tests for enhanced CLI progress display integration.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from ktrdr.cli.progress_display_enhanced import (
    EnhancedCLIProgressDisplay,
    create_enhanced_progress_callback,
    simple_enhanced_progress_callback,
)
from ktrdr.data.components.progress_manager import ProgressState


class TestEnhancedCLIProgressDisplay:
    """Test the EnhancedCLIProgressDisplay class."""

    def test_initialization(self):
        """Test EnhancedCLIProgressDisplay initialization."""
        # Default initialization
        display = EnhancedCLIProgressDisplay()
        assert display.console is not None
        assert display.show_details is True
        assert display.progress is None
        assert display.current_task is None

        # Custom console
        console = Console(file=StringIO(), width=80)
        display_custom = EnhancedCLIProgressDisplay(console=console, show_details=False)
        assert display_custom.console == console
        assert display_custom.show_details is False

    def test_operation_title_creation(self):
        """Test creation of enhanced operation titles."""
        display = EnhancedCLIProgressDisplay()

        # Basic title
        title1 = display._create_operation_title("Load Data", None)
        assert title1 == "Load Data"

        # Title with symbol and timeframe
        context1 = {"symbol": "AAPL", "timeframe": "1d"}
        title2 = display._create_operation_title("Load Data", context1)
        assert title2 == "Load Data (AAPL 1d)"

        # Title with symbol only
        context2 = {"symbol": "MSFT"}
        title3 = display._create_operation_title("Validate Symbol", context2)
        assert title3 == "Validate Symbol (MSFT)"

    def test_step_description_creation(self):
        """Test creation of enhanced step descriptions."""
        display = EnhancedCLIProgressDisplay()

        # Basic progress state
        state1 = ProgressState(
            operation_id="test_op",
            current_step=2,
            total_steps=5,
            message="Loading data from cache",
            percentage=40.0,
        )
        desc1 = display._create_step_description(state1)
        assert desc1 == "Loading data from cache"

        # Progress state with step name and detail
        state2 = ProgressState(
            operation_id="test_op",
            current_step=3,
            total_steps=5,
            message="Processing segments",
            percentage=60.0,
            current_step_name="Gap Analysis",
            step_detail="Found 2 gaps to fill",
        )
        desc2 = display._create_step_description(state2)
        assert desc2 == "[3/5] Gap Analysis: Found 2 gaps to fill"

    def test_details_text_creation(self):
        """Test creation of details text."""
        display = EnhancedCLIProgressDisplay()

        # Basic state with no details
        state1 = ProgressState(
            operation_id="test_op",
            current_step=1,
            total_steps=3,
            message="Starting",
            percentage=0.0,
        )
        details1 = display._create_details_text(state1)
        assert details1 == ""

        # State with current item detail
        state2 = ProgressState(
            operation_id="test_op",
            current_step=2,
            total_steps=3,
            message="Processing",
            percentage=50.0,
            current_item_detail="Segment 3 of 10",
        )
        details2 = display._create_details_text(state2)
        assert "Segment 3 of 10" in details2

        # State with items processed
        state3 = ProgressState(
            operation_id="test_op",
            current_step=2,
            total_steps=3,
            message="Processing",
            percentage=66.0,
            items_processed=150,
            expected_items=300,
        )
        details3 = display._create_details_text(state3)
        assert "150/300 items" in details3

        # State with time estimate
        state4 = ProgressState(
            operation_id="test_op",
            current_step=2,
            total_steps=3,
            message="Processing",
            percentage=75.0,
            estimated_remaining=timedelta(seconds=45),
        )
        details4 = display._create_details_text(state4)
        assert "ETA: 45s" in details4

        # State with multiple details
        state5 = ProgressState(
            operation_id="test_op",
            current_step=3,
            total_steps=3,
            message="Final processing",
            percentage=90.0,
            current_item_detail="Last segment",
            items_processed=90,
            expected_items=100,
            estimated_remaining=timedelta(seconds=120),
        )
        details5 = display._create_details_text(state5)
        assert "Last segment" in details5
        assert "90/100 items" in details5
        assert "ETA: 2m" in details5

    def test_time_estimate_formatting(self):
        """Test time estimate formatting."""
        display = EnhancedCLIProgressDisplay()

        # Test various time formats
        assert display._format_time_estimate(timedelta(seconds=30)) == "30s"
        assert display._format_time_estimate(timedelta(seconds=90)) == "1m"
        assert display._format_time_estimate(timedelta(seconds=150)) == "2m"
        assert display._format_time_estimate(timedelta(seconds=3600)) == "1h00m"
        assert display._format_time_estimate(timedelta(seconds=3900)) == "1h05m"

    def test_error_reporting(self):
        """Test error reporting with context."""
        console_output = StringIO()
        console = Console(file=console_output, width=80)
        display = EnhancedCLIProgressDisplay(console=console)

        # Basic error
        display.report_error("Connection failed")
        output = console_output.getvalue()
        assert "❌ Error: Connection failed" in output

        # Error with context
        console_output = StringIO()
        console = Console(file=console_output, width=80)
        display = EnhancedCLIProgressDisplay(console=console)

        context = {"symbol": "AAPL", "timeframe": "1d", "current_item": "segment_3"}
        display.report_error("Fetch failed", context=context)
        output = console_output.getvalue()
        assert "❌ Error: Fetch failed" in output
        assert "Symbol: AAPL" in output
        assert "Timeframe: 1d" in output
        assert "Item: segment_3" in output

    @patch("ktrdr.cli.progress_display_enhanced.Live")
    @patch("ktrdr.cli.progress_display_enhanced.Progress")
    def test_operation_lifecycle(self, mock_progress_class, mock_live_class):
        """Test complete operation lifecycle."""
        # Setup mocks
        mock_progress = Mock()
        mock_live = Mock()
        mock_progress_class.return_value = mock_progress
        mock_live_class.return_value = mock_live
        mock_progress.add_task.return_value = "task_id"

        display = EnhancedCLIProgressDisplay()

        # Start operation
        context = {"symbol": "AAPL", "timeframe": "1d"}
        display.start_operation("Load Data", 5, context)

        # Verify initialization
        mock_progress_class.assert_called_once()
        mock_live_class.assert_called_once()
        mock_live.start.assert_called_once()
        mock_progress.add_task.assert_called_once()

        # Update progress
        progress_state = ProgressState(
            operation_id="Load Data",
            current_step=2,
            total_steps=5,
            message="Processing segments",
            percentage=40.0,
            operation_context=context,
        )
        display.update_progress(progress_state)

        # Verify update
        mock_progress.update.assert_called()
        mock_live.update.assert_called()

        # Complete operation
        display.complete_operation(success=True, summary="All data loaded")

        # Verify completion
        mock_live.stop.assert_called_once()


class TestEnhancedProgressCallbacks:
    """Test enhanced progress callback functions."""

    def test_create_enhanced_progress_callback(self):
        """Test creation of enhanced progress callback."""
        callback, display = create_enhanced_progress_callback()

        assert callable(callback)
        assert isinstance(display, EnhancedCLIProgressDisplay)

        # Test with custom parameters
        console_output = StringIO()
        console = Console(file=console_output, width=80)
        callback2, display2 = create_enhanced_progress_callback(
            console=console, show_details=False
        )

        assert callable(callback2)
        assert display2.console == console
        assert display2.show_details is False

    @patch("ktrdr.cli.progress_display_enhanced.EnhancedCLIProgressDisplay")
    def test_enhanced_progress_callback_flow(self, mock_display_class):
        """Test enhanced progress callback operational flow."""
        mock_display = Mock()
        mock_display_class.return_value = mock_display

        callback, display = create_enhanced_progress_callback()

        # First callback should start operation
        state1 = ProgressState(
            operation_id="test_operation",
            current_step=0,
            total_steps=3,
            message="Starting",
            percentage=0.0,
            operation_context={"symbol": "AAPL", "timeframe": "1d"},
        )
        callback(state1)
        mock_display.start_operation.assert_called_once_with(
            "test_operation", 3, {"symbol": "AAPL", "timeframe": "1d"}
        )

        # Subsequent callbacks should update progress
        state2 = ProgressState(
            operation_id="test_operation",
            current_step=1,
            total_steps=3,
            message="Processing",
            percentage=33.0,
        )
        callback(state2)
        mock_display.update_progress.assert_called_with(state2)

        # Completion callback should complete operation
        state3 = ProgressState(
            operation_id="test_operation",
            current_step=3,
            total_steps=3,
            message="Complete",
            percentage=100.0,
        )
        callback(state3)
        mock_display.update_progress.assert_called_with(state3)
        mock_display.complete_operation.assert_called_once_with(success=True)

    def test_simple_enhanced_progress_callback_singleton(self):
        """Test that simple enhanced progress callback maintains singleton behavior."""
        # First call should create display manager
        state1 = ProgressState(
            operation_id="test_op",
            current_step=1,
            total_steps=2,
            message="Testing",
            percentage=50.0,
        )

        # Should not raise an exception
        simple_enhanced_progress_callback(state1)

        # Should have created singleton attributes
        assert hasattr(simple_enhanced_progress_callback, "_display_manager")
        assert hasattr(simple_enhanced_progress_callback, "_callback")

        # Second call should reuse the same manager
        first_manager = simple_enhanced_progress_callback._display_manager

        state2 = ProgressState(
            operation_id="test_op",
            current_step=2,
            total_steps=2,
            message="Complete",
            percentage=100.0,
        )
        simple_enhanced_progress_callback(state2)

        # Should be the same manager instance
        assert simple_enhanced_progress_callback._display_manager is first_manager


class TestEnhancedProgressIntegration:
    """Test integration between enhanced progress components."""

    def test_progress_manager_with_enhanced_cli_display(self):
        """Test ProgressManager integration with EnhancedCLIProgressDisplay."""
        from ktrdr.data.components.progress_manager import ProgressManager

        # Create enhanced callback
        callback, display = create_enhanced_progress_callback()

        # Use callback with ProgressManager
        pm = ProgressManager(callback)

        context = {"symbol": "AAPL", "timeframe": "1d", "mode": "backfill"}

        # This should work without errors and trigger the enhanced display
        pm.start_operation(3, "integration_test", operation_context=context)
        pm.update_progress_with_context(
            1, "Loading local data", current_item_detail="Reading cache files"
        )
        pm.update_progress_with_context(
            2, "Analyzing gaps", current_item_detail="Found 5 gaps to fill"
        )
        pm.complete_operation()

    def test_time_estimation_with_cli_display(self):
        """Test time estimation integration with CLI display."""
        from ktrdr.data.components.progress_manager import ProgressManager

        # Mock time estimator to return known estimate
        with patch(
            "ktrdr.data.components.progress_manager.TimeEstimationEngine"
        ) as mock_engine_class:
            mock_engine = Mock()
            mock_engine.estimate_duration.return_value = 25.0  # 25 seconds
            mock_engine_class.return_value = mock_engine

            callback, display = create_enhanced_progress_callback()
            pm = ProgressManager(callback, enable_time_estimation=True)

            context = {"symbol": "MSFT", "timeframe": "1h"}
            pm.start_operation(5, "timed_operation", operation_context=context)

            # Should have called time estimation
            mock_engine.estimate_duration.assert_called_with("timed_operation", context)

            # Complete the operation
            pm.complete_operation()

            # Should have recorded the completion
            mock_engine.record_operation_completion.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

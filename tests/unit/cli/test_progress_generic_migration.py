"""
Tests for CLI migration from ProgressState to GenericProgressState.

This test file verifies that CLI components can work with GenericProgressState
instead of the domain-specific ProgressState, ensuring the migration preserves
all functionality while using generic infrastructure.
"""

from datetime import timedelta
from io import StringIO

import pytest
from rich.console import Console

from ktrdr.async_infrastructure.progress import GenericProgressState
from ktrdr.cli.progress_display_enhanced import (
    EnhancedCLIProgressDisplay,
    create_enhanced_progress_callback,
)


class TestCLIGenericProgressMigration:
    """Test CLI components working with GenericProgressState."""

    def test_enhanced_cli_with_generic_progress_state(self):
        """Test EnhancedCLIProgressDisplay works with GenericProgressState."""
        console_output = StringIO()
        console = Console(file=console_output, width=80)
        display = EnhancedCLIProgressDisplay(console=console)

        # Create GenericProgressState that mimics ProgressState behavior
        generic_state = GenericProgressState(
            operation_id="test_operation",
            current_step=2,
            total_steps=5,
            percentage=40.0,
            message="Processing segments",
            context={
                "current_step_name": "Gap Analysis",
                "step_detail": "Found 2 gaps to fill",
                "symbol": "AAPL",
                "timeframe": "1d",
            },
            items_processed=150,
            total_items=300,
        )

        # Should work without errors
        display.update_progress(generic_state)

    def test_generic_progress_state_field_mapping(self):
        """Test that GenericProgressState fields map correctly to ProgressState expectations."""
        # Fields that must be preserved for CLI compatibility
        generic_state = GenericProgressState(
            operation_id="test_op",
            current_step=3,
            total_steps=10,
            percentage=75.5,
            message="Processing data",
            items_processed=250,
            total_items=500,
            estimated_remaining=timedelta(seconds=120),
            context={
                "current_step_name": "Data Validation",
                "step_detail": "Checking for gaps",
                "current_item_detail": "Segment 15 of 20",
                "symbol": "MSFT",
                "timeframe": "1h",
            },
        )

        # Verify critical fields exist and have correct values
        assert generic_state.operation_id == "test_op"
        assert generic_state.current_step == 3
        assert generic_state.total_steps == 10
        assert generic_state.percentage == 75.5
        assert generic_state.message == "Processing data"
        assert generic_state.items_processed == 250
        assert generic_state.total_items == 500
        assert generic_state.estimated_remaining == timedelta(seconds=120)

        # Verify context fields that CLI expects
        assert generic_state.context["current_step_name"] == "Data Validation"
        assert generic_state.context["step_detail"] == "Checking for gaps"
        assert generic_state.context["current_item_detail"] == "Segment 15 of 20"

    def test_enhanced_callback_with_generic_state(self):
        """Test enhanced progress callback works with GenericProgressState."""
        callback, display = create_enhanced_progress_callback()

        # Create state that would come from GenericProgressManager
        state = GenericProgressState(
            operation_id="generic_test",
            current_step=0,
            total_steps=3,
            percentage=0.0,
            message="Starting operation",
            context={"symbol": "AAPL", "timeframe": "1d"},
        )

        # Should work without errors
        callback(state)

        # Progress state
        state.current_step = 1
        state.percentage = 33.3
        state.message = "Processing"
        callback(state)

        # Completion state
        state.current_step = 3
        state.percentage = 100.0
        state.message = "Complete"
        callback(state)

    def test_cli_field_compatibility_layer(self):
        """Test that CLI can access all fields it needs from GenericProgressState."""
        # This test ensures that when CLI is migrated from ProgressState to GenericProgressState,
        # all the fields accessed by CLI components exist and behave correctly

        display = EnhancedCLIProgressDisplay()

        # Create comprehensive state with all fields CLI might need
        state = GenericProgressState(
            operation_id="comprehensive_test",
            current_step=2,
            total_steps=5,
            percentage=40.0,
            message="Processing data",
            items_processed=100,
            total_items=250,
            estimated_remaining=timedelta(seconds=90),
            context={
                # Fields that ProgressState had as direct attributes but GenericProgressState has in context
                "current_step_name": "Data Loading",
                "step_detail": "Loading from cache",
                "current_item_detail": "File 10 of 25",
                "operation_context": {"symbol": "AAPL", "timeframe": "1d"},
                "expected_items": 250,  # Backward compatibility
            },
        )

        # Test all CLI display method calls that might access these fields
        title = display._create_operation_title(
            state.operation_id, state.context.get("operation_context", {})
        )
        assert "comprehensive_test" in title

        description = display._create_step_description(state)
        assert "Data Loading" in description

        details = display._create_details_text(state)
        assert "File 10 of 25" in details
        assert "100/250 items" in details
        assert "ETA: 1m" in details

    def test_data_commands_import_compatibility(self):
        """Test that data_commands.py can import and use GenericProgressState."""
        # This test verifies the import migration will work
        from ktrdr.async_infrastructure.progress import GenericProgressState

        # Verify GenericProgressState can be used as a type hint and instantiated
        def example_function(progress: GenericProgressState) -> str:
            return f"Processing {progress.operation_id} at {progress.percentage}%"

        state = GenericProgressState(
            operation_id="test",
            current_step=1,
            total_steps=5,
            percentage=20.0,
            message="Testing",
        )

        result = example_function(state)
        assert "Processing test at 20.0%" == result

    @pytest.mark.skip(reason="Will pass after migration is complete")
    def test_progress_display_enhanced_imports_generic_state(self):
        """Test that progress_display_enhanced.py imports GenericProgressState instead of ProgressState."""
        # This test will pass after the migration is complete
        import inspect

        from ktrdr.cli import progress_display_enhanced

        # Check that the module imports GenericProgressState
        source = inspect.getsource(progress_display_enhanced)
        assert (
            "from ktrdr.async_infrastructure.progress import GenericProgressState"
            in source
        )
        assert (
            "from ktrdr.data.components.progress_manager import ProgressState"
            not in source
        )

    @pytest.mark.skip(reason="Will pass after migration is complete")
    def test_data_commands_imports_generic_state(self):
        """Test that data_commands.py imports GenericProgressState instead of ProgressState."""
        # This test will pass after the migration is complete
        import inspect

        from ktrdr.cli import data_commands

        # Check that the module imports GenericProgressState
        source = inspect.getsource(data_commands)
        assert (
            "from ktrdr.async_infrastructure.progress import GenericProgressState"
            in source
        )
        assert (
            "from ktrdr.data.components.progress_manager import ProgressState"
            not in source
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

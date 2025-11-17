"""
Unit tests for CheckpointType enum.

Tests verify:
- Enum values are correctly defined
- String representation works
- Can be used in comparisons
"""

import pytest

from ktrdr.checkpoint.types import CheckpointType


class TestCheckpointType:
    """Test CheckpointType enum."""

    def test_timer_type_value(self):
        """Test TIMER checkpoint type has correct value."""
        assert CheckpointType.TIMER.value == "TIMER"

    def test_force_type_value(self):
        """Test FORCE checkpoint type has correct value."""
        assert CheckpointType.FORCE.value == "FORCE"

    def test_cancellation_type_value(self):
        """Test CANCELLATION checkpoint type has correct value."""
        assert CheckpointType.CANCELLATION.value == "CANCELLATION"

    def test_shutdown_type_value(self):
        """Test SHUTDOWN checkpoint type has correct value."""
        assert CheckpointType.SHUTDOWN.value == "SHUTDOWN"

    def test_failure_type_value(self):
        """Test FAILURE checkpoint type has correct value."""
        assert CheckpointType.FAILURE.value == "FAILURE"

    def test_all_types_present(self):
        """Test all expected checkpoint types are defined."""
        expected_types = {"TIMER", "FORCE", "CANCELLATION", "SHUTDOWN", "FAILURE"}
        actual_types = {member.value for member in CheckpointType}
        assert actual_types == expected_types

    def test_type_comparison(self):
        """Test checkpoint types can be compared."""
        assert CheckpointType.TIMER == CheckpointType.TIMER
        assert CheckpointType.CANCELLATION != CheckpointType.SHUTDOWN

    def test_string_value_usage(self):
        """Test checkpoint type can be used as string value."""
        checkpoint_type = CheckpointType.CANCELLATION
        assert str(checkpoint_type.value) == "CANCELLATION"

    def test_enum_from_value(self):
        """Test creating enum from string value."""
        checkpoint_type = CheckpointType("CANCELLATION")
        assert checkpoint_type == CheckpointType.CANCELLATION

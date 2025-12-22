"""Tests for agent-related operation types.

Task 1.1 of M1: Verify operation types exist for agent system.
"""

import pytest

from ktrdr.api.models.operations import OperationType


class TestAgentOperationTypes:
    """Test that agent operation types are correctly defined."""

    def test_agent_research_type_exists(self):
        """AGENT_RESEARCH type should exist for orchestrator operations."""
        assert hasattr(OperationType, "AGENT_RESEARCH")
        assert OperationType.AGENT_RESEARCH.value == "agent_research"

    def test_agent_design_type_exists(self):
        """AGENT_DESIGN type should exist for Claude design phase."""
        assert hasattr(OperationType, "AGENT_DESIGN")
        assert OperationType.AGENT_DESIGN.value == "agent_design"

    def test_agent_assessment_type_exists(self):
        """AGENT_ASSESSMENT type should exist for Claude assessment phase."""
        assert hasattr(OperationType, "AGENT_ASSESSMENT")
        assert OperationType.AGENT_ASSESSMENT.value == "agent_assessment"


class TestExistingOperationTypesNotBroken:
    """Ensure existing operation types still work (no breaking changes)."""

    @pytest.mark.parametrize(
        "type_name,expected_value",
        [
            ("DATA_LOAD", "data_load"),
            ("TRAINING", "training"),
            ("BACKTESTING", "backtesting"),
            ("INDICATOR_COMPUTE", "indicator_compute"),
            ("FUZZY_ANALYSIS", "fuzzy_analysis"),
            ("DUMMY", "dummy"),
        ],
    )
    def test_existing_types_unchanged(self, type_name: str, expected_value: str):
        """Existing operation types should have unchanged values."""
        assert hasattr(OperationType, type_name)
        assert getattr(OperationType, type_name).value == expected_value

    def test_operation_type_is_str_enum(self):
        """OperationType should be a string enum for JSON serialization."""
        assert issubclass(OperationType, str)
        # Value should be the string representation
        assert OperationType.TRAINING.value == "training"
        # Should be usable as string (inherited from str)
        training_type = OperationType.TRAINING
        assert isinstance(training_type, str)
        assert training_type == "training"

"""Unit tests for save_assessment tool.

Tests for Task 5.2: save_assessment tool and executor handler.
"""

import json

import pytest

from ktrdr.agents.executor import ToolExecutor
from ktrdr.agents.tools import get_tool_by_name


class TestSaveAssessmentToolSchema:
    """Tests for save_assessment tool definition."""

    def test_save_assessment_tool_exists(self):
        """save_assessment tool is defined in AGENT_TOOLS."""
        tool = get_tool_by_name("save_assessment")
        assert tool is not None
        assert tool["name"] == "save_assessment"

    def test_tool_has_required_properties(self):
        """Tool schema has all required properties."""
        tool = get_tool_by_name("save_assessment")
        schema = tool["input_schema"]
        props = schema["properties"]

        assert "verdict" in props
        assert "strengths" in props
        assert "weaknesses" in props
        assert "suggestions" in props

    def test_verdict_has_enum_constraint(self):
        """Verdict is constrained to valid values."""
        tool = get_tool_by_name("save_assessment")
        verdict_prop = tool["input_schema"]["properties"]["verdict"]

        assert "enum" in verdict_prop
        assert "promising" in verdict_prop["enum"]
        assert "mediocre" in verdict_prop["enum"]
        assert "poor" in verdict_prop["enum"]

    def test_all_fields_required(self):
        """All fields are marked as required."""
        tool = get_tool_by_name("save_assessment")
        required = tool["input_schema"]["required"]

        assert "verdict" in required
        assert "strengths" in required
        assert "weaknesses" in required
        assert "suggestions" in required


class TestSaveAssessmentHandler:
    """Tests for save_assessment executor handler."""

    @pytest.fixture
    def executor(self):
        """Create a ToolExecutor with strategy name set."""
        executor = ToolExecutor()
        executor._current_strategy_name = "test_strategy_v1"
        return executor

    @pytest.fixture
    def temp_strategies_dir(self, monkeypatch, tmp_path):
        """Set up temporary strategies directory."""
        # Change working directory to tmp_path
        monkeypatch.chdir(tmp_path)
        return tmp_path

    @pytest.mark.asyncio
    async def test_save_assessment_creates_json_file(
        self, executor, temp_strategies_dir
    ):
        """save_assessment creates JSON file in strategies directory."""
        result = await executor.execute(
            "save_assessment",
            {
                "verdict": "promising",
                "strengths": ["Good win rate", "Low drawdown"],
                "weaknesses": ["Limited trades"],
                "suggestions": ["Increase sample size"],
            },
        )

        assert result.get("success") is True
        assert "path" in result

        # Verify file was created
        expected_path = (
            temp_strategies_dir / "strategies" / "test_strategy_v1" / "assessment.json"
        )
        assert expected_path.exists()

    @pytest.mark.asyncio
    async def test_assessment_contains_all_required_fields(
        self, executor, temp_strategies_dir
    ):
        """Saved assessment contains all required fields."""
        await executor.execute(
            "save_assessment",
            {
                "verdict": "mediocre",
                "strengths": ["Stable"],
                "weaknesses": ["Low returns"],
                "suggestions": ["Try different indicators"],
            },
        )

        assessment_path = (
            temp_strategies_dir / "strategies" / "test_strategy_v1" / "assessment.json"
        )
        with open(assessment_path) as f:
            assessment = json.load(f)

        assert assessment["verdict"] == "mediocre"
        assert assessment["strengths"] == ["Stable"]
        assert assessment["weaknesses"] == ["Low returns"]
        assert assessment["suggestions"] == ["Try different indicators"]

    @pytest.mark.asyncio
    async def test_assessment_directory_created_if_not_exists(
        self, executor, temp_strategies_dir
    ):
        """Assessment directory is created if it doesn't exist."""
        # Directory shouldn't exist before
        strategy_dir = temp_strategies_dir / "strategies" / "test_strategy_v1"
        assert not strategy_dir.exists()

        await executor.execute(
            "save_assessment",
            {
                "verdict": "poor",
                "strengths": ["Quick execution"],
                "weaknesses": ["Poor metrics"],
                "suggestions": ["Redesign strategy"],
            },
        )

        # Directory should exist after
        assert strategy_dir.exists()

    @pytest.mark.asyncio
    async def test_error_returned_if_no_strategy_name_set(self, temp_strategies_dir):
        """Error returned if no strategy name is set."""
        executor = ToolExecutor()
        # Don't set _current_strategy_name

        result = await executor.execute(
            "save_assessment",
            {
                "verdict": "promising",
                "strengths": ["Test"],
                "weaknesses": ["Test"],
                "suggestions": ["Test"],
            },
        )

        assert result.get("success") is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_timestamp_included_in_assessment(
        self, executor, temp_strategies_dir
    ):
        """Saved assessment includes timestamp."""
        await executor.execute(
            "save_assessment",
            {
                "verdict": "promising",
                "strengths": ["Test"],
                "weaknesses": ["Test"],
                "suggestions": ["Test"],
            },
        )

        assessment_path = (
            temp_strategies_dir / "strategies" / "test_strategy_v1" / "assessment.json"
        )
        with open(assessment_path) as f:
            assessment = json.load(f)

        assert "assessed_at" in assessment
        # Should be ISO format datetime
        assert "T" in assessment["assessed_at"]

    @pytest.mark.asyncio
    async def test_last_saved_assessment_tracked(self, executor, temp_strategies_dir):
        """Executor tracks last saved assessment."""
        await executor.execute(
            "save_assessment",
            {
                "verdict": "promising",
                "strengths": ["A", "B"],
                "weaknesses": ["C"],
                "suggestions": ["D"],
            },
        )

        assert executor.last_saved_assessment is not None
        assert executor.last_saved_assessment["verdict"] == "promising"
        assert executor.last_saved_assessment_path is not None

"""Tests for save_assessment MCP tool.

Tests the save_assessment business logic:
1. Valid assessment → saved as JSON
2. Invalid verdict value → rejected
3. Missing required fields → rejected
4. Assessment for non-existent strategy → still saves (strategy may be saved later)
5. Returns assessment_path on success
"""

import json
from pathlib import Path

import pytest

from ktrdr.mcp.assessment_service import save_assessment


class TestSaveAssessment:
    """Tests for save_assessment business logic."""

    @pytest.fixture
    def strategies_dir(self, tmp_path):
        """Create a temporary strategies directory."""
        strat_dir = tmp_path / "strategies"
        strat_dir.mkdir()
        return strat_dir

    @pytest.mark.asyncio
    async def test_valid_assessment_saved_as_json(self, strategies_dir):
        """Valid assessment → saved as JSON file, returns success."""
        result = await save_assessment(
            strategy_name="test_strategy",
            verdict="promising",
            strengths=["good RSI usage", "clean signal"],
            weaknesses=["limited data range"],
            suggestions=["add volume filter"],
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is True
        assert "assessment_path" in result
        saved_path = Path(result["assessment_path"])
        assert saved_path.exists()
        assert saved_path.suffix == ".json"

    @pytest.mark.asyncio
    async def test_saved_assessment_contains_all_fields(self, strategies_dir):
        """Saved assessment file should contain all provided fields."""
        await save_assessment(
            strategy_name="test_strategy",
            verdict="neutral",
            strengths=["decent returns"],
            weaknesses=["high drawdown"],
            suggestions=["reduce position size"],
            hypotheses=[
                {"hypothesis": "RSI works better with volume", "confidence": 0.7}
            ],
            strategies_dir=str(strategies_dir),
        )

        assessment_path = strategies_dir / "test_strategy_assessment.json"
        with open(assessment_path) as f:
            data = json.load(f)

        assert data["strategy_name"] == "test_strategy"
        assert data["verdict"] == "neutral"
        assert data["strengths"] == ["decent returns"]
        assert data["weaknesses"] == ["high drawdown"]
        assert data["suggestions"] == ["reduce position size"]
        assert len(data["hypotheses"]) == 1
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_invalid_verdict_rejected(self, strategies_dir):
        """Invalid verdict value → rejected with error."""
        result = await save_assessment(
            strategy_name="test_strategy",
            verdict="excellent",  # Not a valid verdict
            strengths=["good"],
            weaknesses=["bad"],
            suggestions=["improve"],
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is False
        assert "errors" in result
        assert any("verdict" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_missing_strengths_rejected(self, strategies_dir):
        """Missing required field strengths → rejected."""
        result = await save_assessment(
            strategy_name="test_strategy",
            verdict="promising",
            strengths=[],  # Empty — must have at least one
            weaknesses=["bad"],
            suggestions=["improve"],
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is False
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_missing_weaknesses_rejected(self, strategies_dir):
        """Missing required field weaknesses → rejected."""
        result = await save_assessment(
            strategy_name="test_strategy",
            verdict="poor",
            strengths=["good"],
            weaknesses=[],  # Empty — must have at least one
            suggestions=["improve"],
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is False
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_hypotheses_optional(self, strategies_dir):
        """Assessment without hypotheses should still save."""
        result = await save_assessment(
            strategy_name="test_strategy",
            verdict="promising",
            strengths=["good RSI usage"],
            weaknesses=["limited data"],
            suggestions=["add more indicators"],
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is True

        assessment_path = Path(result["assessment_path"])
        with open(assessment_path) as f:
            data = json.load(f)
        assert data["hypotheses"] == []

    @pytest.mark.asyncio
    async def test_assessment_path_includes_strategy_name(self, strategies_dir):
        """Assessment filename should include the strategy name."""
        result = await save_assessment(
            strategy_name="my_rsi_strategy",
            verdict="neutral",
            strengths=["ok"],
            weaknesses=["not great"],
            suggestions=["try harder"],
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is True
        path = Path(result["assessment_path"])
        assert "my_rsi_strategy" in path.name

    @pytest.mark.asyncio
    async def test_overwrite_existing_assessment(self, strategies_dir):
        """Saving assessment again should overwrite previous one."""
        # First save
        result1 = await save_assessment(
            strategy_name="test_strategy",
            verdict="poor",
            strengths=["one thing"],
            weaknesses=["many things"],
            suggestions=["start over"],
            strategies_dir=str(strategies_dir),
        )
        assert result1["success"] is True

        # Second save with different verdict
        result2 = await save_assessment(
            strategy_name="test_strategy",
            verdict="promising",
            strengths=["actually good"],
            weaknesses=["minor issue"],
            suggestions=["fine tune"],
            strategies_dir=str(strategies_dir),
        )
        assert result2["success"] is True

        # Verify the file contains the latest data
        with open(result2["assessment_path"]) as f:
            data = json.load(f)
        assert data["verdict"] == "promising"

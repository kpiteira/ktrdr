"""
MCP tools for assessment management.

Provides MCP tool wrappers for assessment operations:
- save_assessment: Save a structured assessment of a strategy

The actual business logic is in ktrdr.mcp.assessment_service
to allow proper unit testing without FastMCP dependencies.
"""

from typing import Any

from ktrdr.mcp.assessment_service import save_assessment as _save_assessment
from mcp.server.fastmcp import FastMCP

from ..telemetry import trace_mcp_tool

# Re-export for direct access
save_assessment = _save_assessment


def register_assessment_tools(mcp: FastMCP) -> None:
    """Register assessment management tools with the MCP server.

    Args:
        mcp: The FastMCP server instance to register tools with.
    """

    @trace_mcp_tool("save_assessment")
    @mcp.tool(name="save_assessment")
    async def save_assessment_tool(
        strategy_name: str,
        verdict: str,
        strengths: list[str],
        weaknesses: list[str],
        suggestions: list[str],
        hypotheses: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Save a structured assessment of a strategy.

        Records the evaluation results for a strategy after training and
        backtesting. The assessment is saved as JSON alongside the strategy.

        Args:
            strategy_name: Name of the strategy that was assessed
            verdict: Overall verdict — "promising", "neutral", or "poor"
            strengths: List of observed strengths (at least one required)
            weaknesses: List of observed weaknesses (at least one required)
            suggestions: List of improvement suggestions
            hypotheses: Optional list of new hypotheses generated from this assessment

        Returns:
            Dict with structure on success:
            {
                "success": true,
                "assessment_path": str
            }
            On failure:
            {
                "success": false,
                "errors": list[str]
            }

        Examples:
            # Save an assessment
            result = await save_assessment(
                strategy_name="rsi_momentum_v3",
                verdict="promising",
                strengths=["Good Sharpe ratio", "Low drawdown"],
                weaknesses=["Limited trade count"],
                suggestions=["Increase data range", "Add volume filter"]
            )

        Notes:
            - Valid verdicts: "promising", "neutral", "poor"
            - Strengths and weaknesses must each have at least one item
            - Hypotheses are optional but help guide future research
            - Overwrites previous assessment for the same strategy
        """
        return await _save_assessment(
            strategy_name=strategy_name,
            verdict=verdict,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            hypotheses=hypotheses,
        )

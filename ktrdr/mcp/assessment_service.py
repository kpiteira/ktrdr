"""Assessment service for MCP tools.

Provides business logic for assessment operations used by MCP tools.
This module is testable without FastMCP dependencies.
"""

import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ktrdr import get_logger

logger = get_logger(__name__)

VALID_VERDICTS = {"promising", "neutral", "poor"}
DEFAULT_STRATEGIES_DIR = "strategies"


def _sanitize_filename(name: str) -> str:
    """Sanitize strategy name for use as filename."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


async def save_assessment(
    strategy_name: str,
    verdict: str,
    strengths: list[str],
    weaknesses: list[str],
    suggestions: list[str],
    hypotheses: list[dict[str, Any]] | None = None,
    strategies_dir: str | None = None,
) -> dict[str, Any]:
    """Save a structured assessment result.

    Validates the assessment structure, then saves as JSON alongside
    the strategy YAML.

    Args:
        strategy_name: Which strategy was assessed
        verdict: "promising" | "neutral" | "poor"
        strengths: List of observed strengths
        weaknesses: List of observed weaknesses
        suggestions: List of improvement suggestions
        hypotheses: Optional list of new hypotheses generated
        strategies_dir: Directory to save assessments (default: strategies/)

    Returns:
        Dict with success status and assessment_path on success,
        or success=False with errors on failure.
    """
    # Validate verdict
    if verdict not in VALID_VERDICTS:
        return {
            "success": False,
            "errors": [
                f"Invalid verdict '{verdict}'. Must be one of: {', '.join(sorted(VALID_VERDICTS))}"
            ],
        }

    # Validate required lists are non-empty
    errors = []
    if not strengths:
        errors.append("strengths must contain at least one item")
    if not weaknesses:
        errors.append("weaknesses must contain at least one item")
    if errors:
        return {"success": False, "errors": errors}

    # Build assessment document
    assessment = {
        "strategy_name": strategy_name,
        "verdict": verdict,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "hypotheses": hypotheses or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Save
    target_dir = Path(strategies_dir or DEFAULT_STRATEGIES_DIR)
    safe_name = _sanitize_filename(strategy_name)
    target_path = target_dir / f"{safe_name}_assessment.json"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file then rename
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=target_dir, delete=False
        ) as out:
            json.dump(assessment, out, indent=2)
            tmp_out = Path(out.name)

        tmp_out.rename(target_path)

        logger.info("Assessment saved: %s -> %s", strategy_name, target_path)

        return {
            "success": True,
            "assessment_path": str(target_path),
        }

    except Exception as e:
        # Clean up partial write
        try:
            tmp_out.unlink(missing_ok=True)
        except Exception:
            pass
        logger.error("Error saving assessment: %s", e)
        return {
            "success": False,
            "errors": [f"Failed to save: {e}"],
        }

"""API-based assessment parsing for the agent system.

This module provides structured data extraction from agent assessment output
using the Anthropic API directly (not Claude CLI).

Decision: Make the agent 100% API-based.
See: docs/agentic/brain/INTENT.md
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# Prompt for parsing agent assessment output
PARSE_ASSESSMENT_PROMPT = """Extract structured assessment data from this agent output.

The output may be structured (with headers like "### Verdict") or prose.
Extract what you can, using reasonable defaults for missing fields.

Return a JSON object:
{{
  "verdict": "strong_signal" | "weak_signal" | "no_signal" | "overfit",
  "observations": ["observation 1", "observation 2", ...],
  "hypotheses": [{{"text": "hypothesis text", "status": "untested"}}, ...],
  "limitations": ["limitation 1", ...],
  "capability_requests": ["request 1", ...],
  "tested_hypothesis_ids": ["H_001", ...] // if existing hypotheses are referenced
}}

Guidelines:
- verdict: Classify based on test accuracy and generalization
  - "strong_signal": test accuracy >= 60%, small val-test gap
  - "weak_signal": test accuracy 55-60%
  - "no_signal": test accuracy <= 55% or large val-test gap
  - "overfit": high validation, low test (gap > 10pp)
- observations: Key factual statements about results
- hypotheses: New ideas generated for future testing
- limitations: What wasn't tested, caveats
- capability_requests: Things the agent wishes it could try
- tested_hypothesis_ids: Look for references to existing hypotheses like "H_001",
  "H_002", etc. If the agent mentions testing or validating a specific hypothesis
  ID, include it here. Examples:
  - "Testing hypothesis H_001" → include "H_001"
  - "H_002 was validated by this experiment" → include "H_002"
  - "This refutes H_003" → include "H_003"
  - "H_004 inconclusive" → include "H_004"
  Only include IDs explicitly mentioned, not hypotheses from new ideas.

Return ONLY the JSON, no other text.

Agent output:
{output}
"""


@dataclass
class ParsedAssessment:
    """Structured data extracted from agent's assessment output."""

    verdict: str  # "strong_signal" | "weak_signal" | "no_signal" | "overfit"
    observations: list[str]
    hypotheses: list[dict]  # [{"text": "...", "status": "untested"}]
    limitations: list[str]
    capability_requests: list[str]
    tested_hypothesis_ids: list[str]  # H_001, H_002, etc. if mentioned
    raw_text: str  # Original output for reference

    @classmethod
    def empty(cls, raw_text: str) -> "ParsedAssessment":
        """Create empty result when parsing fails."""
        return cls(
            verdict="unknown",
            observations=[],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text=raw_text,
        )


def parse_assessment(
    output: str,
    context: dict[str, Any] | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> ParsedAssessment:
    """Extract structured assessment from text using Anthropic API.

    Uses Claude to semantically understand the assessment output and
    extract structured data regardless of whether the input is
    structured markdown, prose, or mixed format.

    Args:
        output: The agent's assessment output text.
        context: Optional context dict (unused, kept for compatibility).
        model: Claude model to use (default: Haiku for speed/cost).

    Returns:
        ParsedAssessment with extracted fields, or empty result on failure.
    """
    prompt = PARSE_ASSESSMENT_PROMPT.format(output=output)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        response_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                response_text += block.text

        return _parse_response(response_text, output)

    except anthropic.APIError as e:
        logger.warning(f"API error during assessment parsing: {e}")
        return ParsedAssessment.empty(output)
    except Exception as e:
        logger.warning(f"Failed to parse assessment: {e}")
        return ParsedAssessment.empty(output)


def _parse_response(response: str, raw_output: str) -> ParsedAssessment:
    """Parse the JSON response from Claude into ParsedAssessment.

    Args:
        response: Claude's response text (should be JSON).
        raw_output: Original assessment text for reference.

    Returns:
        ParsedAssessment with extracted fields.
    """
    try:
        # Try to extract JSON from response
        json_str = _extract_json(response)
        data = json.loads(json_str)

        return ParsedAssessment(
            verdict=data.get("verdict", "unknown"),
            observations=data.get("observations", []),
            hypotheses=data.get("hypotheses", []),
            limitations=data.get("limitations", []),
            capability_requests=data.get("capability_requests", []),
            tested_hypothesis_ids=data.get("tested_hypothesis_ids", []),
            raw_text=raw_output,
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse assessment response: {e}")
        return ParsedAssessment.empty(raw_output)


def _extract_json(text: str) -> str:
    """Extract JSON object from text that may contain other content.

    Args:
        text: Text that may contain a JSON object.

    Returns:
        The extracted JSON string.
    """
    # Find the first { and last }
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return text.strip()

    return text[start : end + 1]

"""Tests for ktrdr.llm.haiku_brain module.

Tests for shared LLM utilities, starting with ParsedAssessment dataclass.
"""

import subprocess
from unittest.mock import patch

from ktrdr.llm.haiku_brain import HaikuBrain, ParsedAssessment


class TestParsedAssessment:
    """Tests for the ParsedAssessment dataclass."""

    def test_parsed_assessment_fields(self) -> None:
        """ParsedAssessment should have all required fields accessible."""
        assessment = ParsedAssessment(
            verdict="strong_signal",
            observations=["RSI improved accuracy", "Low val-test gap"],
            hypotheses=[{"text": "Multi-timeframe might help", "status": "untested"}],
            limitations=["Only tested on EURUSD"],
            capability_requests=["Need backtesting support"],
            tested_hypothesis_ids=["H_001"],
            raw_text="Original assessment text here",
        )

        assert assessment.verdict == "strong_signal"
        assert len(assessment.observations) == 2
        assert assessment.observations[0] == "RSI improved accuracy"
        assert len(assessment.hypotheses) == 1
        assert assessment.hypotheses[0]["text"] == "Multi-timeframe might help"
        assert assessment.hypotheses[0]["status"] == "untested"
        assert len(assessment.limitations) == 1
        assert len(assessment.capability_requests) == 1
        assert assessment.tested_hypothesis_ids == ["H_001"]
        assert assessment.raw_text == "Original assessment text here"

    def test_parsed_assessment_empty(self) -> None:
        """empty() classmethod should create valid object with defaults."""
        raw = "Some raw text that couldn't be parsed"
        assessment = ParsedAssessment.empty(raw)

        assert assessment.verdict == "unknown"
        assert assessment.observations == []
        assert assessment.hypotheses == []
        assert assessment.limitations == []
        assert assessment.capability_requests == []
        assert assessment.tested_hypothesis_ids == []
        assert assessment.raw_text == raw

    def test_parsed_assessment_empty_preserves_raw_text(self) -> None:
        """empty() should preserve the raw_text for debugging."""
        long_text = "A" * 1000
        assessment = ParsedAssessment.empty(long_text)
        assert assessment.raw_text == long_text
        assert len(assessment.raw_text) == 1000


class TestParseAssessment:
    """Tests for HaikuBrain.parse_assessment() method."""

    def test_parse_assessment_structured(self) -> None:
        """parse_assessment should extract data from structured markdown."""
        brain = HaikuBrain()

        # Mock Haiku response with structured JSON
        mock_response = """{
            "verdict": "strong_signal",
            "observations": ["RSI + DI improved accuracy by 0.6pp", "Val-test gap of 1.7pp"],
            "hypotheses": [{"text": "Multi-timeframe might break plateau", "status": "untested"}],
            "limitations": ["Only tested on 1h EURUSD"],
            "capability_requests": [],
            "tested_hypothesis_ids": []
        }"""

        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.parse_assessment("Some structured assessment", {})

        assert result.verdict == "strong_signal"
        assert len(result.observations) == 2
        assert "RSI + DI improved accuracy" in result.observations[0]
        assert len(result.hypotheses) == 1
        assert result.hypotheses[0]["text"] == "Multi-timeframe might break plateau"
        assert result.limitations == ["Only tested on 1h EURUSD"]
        assert result.raw_text == "Some structured assessment"

    def test_parse_assessment_prose(self) -> None:
        """parse_assessment should extract meaning from prose (mocked Haiku)."""
        brain = HaikuBrain()

        prose_input = """This strategy performed surprisingly well. The combination of RSI and DI
        produced a test accuracy of 64.8%, which is significantly above random.
        The validation-test gap was minimal, suggesting the model generalizes well.
        I think this is a promising approach worth building on."""

        # Mock Haiku extracting meaning from prose
        mock_response = """{
            "verdict": "strong_signal",
            "observations": ["Test accuracy of 64.8%", "Minimal val-test gap"],
            "hypotheses": [],
            "limitations": [],
            "capability_requests": [],
            "tested_hypothesis_ids": []
        }"""

        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.parse_assessment(prose_input, {})

        assert result.verdict == "strong_signal"
        assert len(result.observations) >= 1
        assert result.raw_text == prose_input

    def test_parse_assessment_haiku_failure(self) -> None:
        """parse_assessment should return empty on Haiku failure."""
        brain = HaikuBrain()

        with patch.object(
            brain, "_invoke_haiku", side_effect=RuntimeError("CLI failed")
        ):
            result = brain.parse_assessment("Some assessment text", {})

        assert result.verdict == "unknown"
        assert result.observations == []
        assert result.raw_text == "Some assessment text"

    def test_parse_assessment_timeout(self) -> None:
        """parse_assessment should return empty on timeout."""
        brain = HaikuBrain()

        with patch.object(
            brain, "_invoke_haiku", side_effect=subprocess.TimeoutExpired("claude", 60)
        ):
            result = brain.parse_assessment("Some assessment text", {})

        assert result.verdict == "unknown"
        assert result.raw_text == "Some assessment text"

    def test_parse_assessment_partial(self) -> None:
        """parse_assessment should handle missing fields gracefully."""
        brain = HaikuBrain()

        # Response missing several optional fields
        mock_response = """{
            "verdict": "weak_signal",
            "observations": ["Single observation"]
        }"""

        with patch.object(brain, "_invoke_haiku", return_value=mock_response):
            result = brain.parse_assessment("Partial assessment", {})

        assert result.verdict == "weak_signal"
        assert result.observations == ["Single observation"]
        assert result.hypotheses == []  # Missing field defaults to empty
        assert result.limitations == []
        assert result.capability_requests == []
        assert result.tested_hypothesis_ids == []

    def test_parse_assessment_invalid_json(self) -> None:
        """parse_assessment should return empty on invalid JSON response."""
        brain = HaikuBrain()

        with patch.object(brain, "_invoke_haiku", return_value="Not valid JSON at all"):
            result = brain.parse_assessment("Assessment text", {})

        assert result.verdict == "unknown"
        assert result.raw_text == "Assessment text"

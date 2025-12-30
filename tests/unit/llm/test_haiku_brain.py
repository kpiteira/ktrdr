"""Tests for ktrdr.llm.haiku_brain module.

Tests for shared LLM utilities, starting with ParsedAssessment dataclass.
"""

from ktrdr.llm.haiku_brain import ParsedAssessment


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

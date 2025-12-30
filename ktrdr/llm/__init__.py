"""Shared LLM utilities for KTRDR.

This package provides LLM-based utilities used across the codebase:
- HaikuBrain: Fast, cheap interpretation via Claude Haiku
"""

from ktrdr.llm.haiku_brain import (
    ExtractedTask,
    HaikuBrain,
    InterpretationResult,
    RetryDecision,
)

__all__ = [
    "HaikuBrain",
    "InterpretationResult",
    "RetryDecision",
    "ExtractedTask",
    # ParsedAssessment will be added in Task 2.3
]

"""Context loading for squad squad_engine.

Reads knowledge base files from ~/.ktrdr/shared/squad/, estimates token
usage, and detects when synthesis is needed. Replaces loop_lib.sh's
context assembly functions.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from ktrdr import get_logger

logger = get_logger(__name__)

# Default knowledge base location
DEFAULT_SHARED_DIR = os.path.expanduser("~/.ktrdr/shared/squad")

# Context budget: 200K tokens, emergency synthesis at 80%
CONTEXT_BUDGET_TOKENS = 200_000
EMERGENCY_THRESHOLD = 0.80

# Approximate chars per token for estimation
CHARS_PER_TOKEN = 4


class ContextLoader:
    """Load and manage knowledge base files for squad agents.

    Reads files from the shared squad directory, estimates token usage,
    and detects when emergency synthesis is needed.
    """

    def __init__(self, shared_dir: str | None = None) -> None:
        if shared_dir:
            self._shared_dir = Path(shared_dir)
        else:
            env_dir = os.environ.get("SQUAD_SHARED_DIR")
            self._shared_dir = Path(env_dir) if env_dir else Path(DEFAULT_SHARED_DIR)

    @property
    def shared_dir(self) -> Path:
        return self._shared_dir

    def load_file(self, relative_path: str) -> str:
        """Load a file from the shared directory.

        Returns empty string if file doesn't exist (don't crash — KB may be sparse).
        """
        full_path = self._shared_dir / relative_path
        if not full_path.exists():
            logger.warning("KB file not found: %s", relative_path)
            return ""
        return full_path.read_text()

    def load_files(self, paths: list[str]) -> dict[str, str]:
        """Load multiple files, returning a dict of path → content."""
        return {path: self.load_file(path) for path in paths}

    def load_recent_experiments(self, n: int = 5) -> str:
        """Load the last N experiments from experiments.md.

        Parses by '## ' headers to identify experiment boundaries.
        """
        content = self.load_file("knowledge/experiments.md")
        if not content:
            return ""

        # Split by experiment headers (## C..., ## Squad Cycle..., etc.)
        # Each section starts with '## ' at the beginning of a line
        sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)

        # Filter out non-experiment sections (preamble, curation notes)
        experiment_sections = [s for s in sections if s.strip().startswith("## ")]

        if not experiment_sections:
            return content

        # Return last N
        recent = experiment_sections[-n:]
        return "\n---\n\n".join(recent)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text.

        Uses ~4 chars per token heuristic. Good enough for budget monitoring.
        """
        return max(1, len(text) // CHARS_PER_TOKEN)

    def needs_synthesis(self, loaded_context: dict[str, str]) -> bool:
        """Check if total context exceeds emergency synthesis threshold.

        Returns True when estimated tokens > 80% of 200K budget.
        """
        total_chars = sum(len(v) for v in loaded_context.values())
        estimated_tokens = total_chars // CHARS_PER_TOKEN
        threshold = int(CONTEXT_BUDGET_TOKENS * EMERGENCY_THRESHOLD)

        if estimated_tokens > threshold:
            logger.warning(
                "Context budget exceeded: ~%d tokens > %d threshold",
                estimated_tokens,
                threshold,
            )
            return True
        return False

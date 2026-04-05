"""Tests for ContextLoader — KB file loading, token estimation, synthesis detection."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure .squad/ is on sys.path
_squad_dir = str(Path(__file__).resolve().parents[3] / ".squad")
if _squad_dir not in sys.path:
    sys.path.insert(0, _squad_dir)

from squad_engine.context import ContextLoader  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_EXPERIMENTS = """# Experiment Log

## C8: Compressed Capacity Control
Val accuracy: 72.85%, Sharpe: -0.37, Return: -3.02%

## C10: Confidence Regime Sweep
Val accuracy: 72.04%, Sharpe: -0.37, Return: -3.02%

## C13: High-Confidence Filter
PF: 0.378, WR: 21.9%

## C17: Information Bottleneck
Sharpe: -1.94, WR: 16.8%

## C18: Triple Barrier vs Zigzag
Per-trade expectancy identical across label types.
"""


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    """Create a mock knowledge base directory."""
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "experiments.md").write_text(SAMPLE_EXPERIMENTS)
    (knowledge / "synthesis.md").write_text("# Synthesis\nPatterns here.")
    (knowledge / "decisions.md").write_text("# Decisions\nD1: MLP is dead.")

    agents = tmp_path / "agents" / "engineer"
    agents.mkdir(parents=True)
    (agents / "history.md").write_text("## Cycle 1\nLearned things.")

    loop = tmp_path / "loop"
    loop.mkdir()
    (loop / "cadence.md").write_text("cadence: full_squad")

    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestContextLoader:
    def test_load_file_reads_content(self, kb_dir: Path):
        loader = ContextLoader(shared_dir=str(kb_dir))
        content = loader.load_file("knowledge/synthesis.md")
        assert "Patterns here" in content

    def test_load_file_missing_returns_empty(self, kb_dir: Path):
        loader = ContextLoader(shared_dir=str(kb_dir))
        content = loader.load_file("knowledge/nonexistent.md")
        assert content == ""

    def test_load_files_returns_dict(self, kb_dir: Path):
        loader = ContextLoader(shared_dir=str(kb_dir))
        result = loader.load_files(["knowledge/synthesis.md", "knowledge/decisions.md"])
        assert "knowledge/synthesis.md" in result
        assert "knowledge/decisions.md" in result
        assert "MLP is dead" in result["knowledge/decisions.md"]

    def test_respects_squad_shared_dir_env(self, kb_dir: Path, monkeypatch):
        monkeypatch.setenv("SQUAD_SHARED_DIR", str(kb_dir))
        loader = ContextLoader()
        content = loader.load_file("knowledge/synthesis.md")
        assert "Patterns here" in content

    def test_load_recent_experiments_returns_last_n(self, kb_dir: Path):
        loader = ContextLoader(shared_dir=str(kb_dir))
        recent = loader.load_recent_experiments(n=2)
        # Should include last 2 experiments (C17 and C18) but not C8
        assert "C18" in recent
        assert "C17" in recent
        assert "C8" not in recent

    def test_load_recent_experiments_returns_all_if_fewer_than_n(self, kb_dir: Path):
        loader = ContextLoader(shared_dir=str(kb_dir))
        recent = loader.load_recent_experiments(n=100)
        assert "C8" in recent
        assert "C18" in recent

    def test_estimate_tokens_within_range(self, kb_dir: Path):
        loader = ContextLoader(shared_dir=str(kb_dir))
        text = "Hello world, this is a test of token estimation."
        tokens = loader.estimate_tokens(text)
        # ~4 chars per token, text is ~49 chars, so ~12 tokens
        assert 8 <= tokens <= 20

    def test_needs_synthesis_false_for_small_context(self, kb_dir: Path):
        loader = ContextLoader(shared_dir=str(kb_dir))
        context = {"file.md": "Small content"}
        assert not loader.needs_synthesis(context)

    def test_needs_synthesis_true_for_large_context(self, kb_dir: Path):
        loader = ContextLoader(shared_dir=str(kb_dir))
        # Create context that exceeds 80% of 200K tokens (~160K tokens ~640K chars)
        large_text = "x" * 700_000
        context = {"experiments.md": large_text}
        assert loader.needs_synthesis(context)

    def test_shared_dir_property(self, kb_dir: Path):
        loader = ContextLoader(shared_dir=str(kb_dir))
        assert loader.shared_dir == kb_dir

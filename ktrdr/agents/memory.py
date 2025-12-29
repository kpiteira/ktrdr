"""Memory module for agent experiment and hypothesis tracking.

This module provides persistence for:
- ExperimentRecord: Contextual experiment records with full context
- Hypothesis: Testable hypotheses tracked across experiments

Storage is YAML-based for human readability and git-friendliness.
Memory is enhancement, not requirement - graceful degradation if missing.
"""

import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Data lives at repo root, not in ktrdr/
MEMORY_DIR = Path("memory")
EXPERIMENTS_DIR = MEMORY_DIR / "experiments"
HYPOTHESES_FILE = MEMORY_DIR / "hypotheses.yaml"


@dataclass
class ExperimentRecord:
    """A single experiment with full context.

    Every observation is tied to its context. Nothing is stated as universal truth.
    The agent sees the fact with its context, then reasons about applicability.
    """

    id: str
    timestamp: str
    strategy_name: str

    # Full context - what makes this experiment unique
    context: dict[str, Any]
    # Fields: indicators, indicator_params, composition, timeframe,
    #         symbol, zigzag_threshold, nn_architecture, training_epochs

    # What happened
    results: dict[str, Any]
    # Fields: test_accuracy, val_accuracy, val_test_gap, sharpe_ratio,
    #         total_trades, win_rate

    # Agent's interpretation
    assessment: dict[str, Any]
    # Fields: verdict, observations, hypotheses, limitations,
    #         capability_requests

    source: str = "agent"  # "agent" | "v1.5_bootstrap"


@dataclass
class Hypothesis:
    """A testable hypothesis tracked across experiments.

    Hypotheses drive systematic investigation rather than random exploration.
    Status is updated when experiments test them.
    """

    id: str
    text: str
    source_experiment: str
    rationale: str
    status: str = "untested"  # "untested" | "validated" | "refuted" | "inconclusive"
    tested_by: list[str] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now().isoformat())


# === Loading ===


def load_experiments(n: int = 15) -> list[dict]:
    """Load N most recent experiments, sorted by file modification time desc.

    Returns empty list if memory directory doesn't exist (graceful degradation).

    Args:
        n: Maximum number of experiments to return (default 15)

    Returns:
        List of experiment dicts, most recent first
    """
    if not EXPERIMENTS_DIR.exists():
        return []

    # Sort by file modification time, most recent first
    files = sorted(
        EXPERIMENTS_DIR.glob("*.yaml"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    experiments = []
    for f in files[:n]:
        experiments.append(yaml.safe_load(f.read_text()))
    return experiments


# === Saving ===


def save_experiment(record: ExperimentRecord) -> Path:
    """Save experiment record to memory/experiments/{id}.yaml.

    Creates directories if needed.

    Args:
        record: ExperimentRecord to save

    Returns:
        Path to saved file
    """
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPERIMENTS_DIR / f"{record.id}.yaml"
    path.write_text(
        yaml.dump(asdict(record), default_flow_style=False, sort_keys=False)
    )
    return path


# === ID Generation ===


def generate_experiment_id() -> str:
    """Generate unique experiment ID.

    Format: exp_YYYYMMDD_HHMMSS_xxxxxxxx
    Example: exp_20251228_143052_abc12345

    Returns:
        Unique experiment ID string
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(4)  # 8 hex characters
    return f"exp_{ts}_{suffix}"

---
design: ../DESIGN.md
architecture: ../SCENARIOS.md
---

# Milestone 1: Memory Infrastructure

**Branch:** `feature/v2-memory-m1`
**Goal:** Create memory module and bootstrap with v1.5 experiment data

---

## E2E Test Scenario

**Purpose:** Verify memory module works and v1.5 data is correctly bootstrapped
**Prerequisites:** v1.5 strategy files exist in `strategies/v15_*.yaml`

```bash
# 1. Run bootstrap script
uv run python scripts/bootstrap_v15_memory.py

# 2. Verify experiment files created
ls memory/experiments/ | wc -l
# Expected: 24 (one per v1.5 strategy with test metrics)

# 3. Verify schema is correct
cat memory/experiments/exp_v15_rsi_zigzag_1_5.yaml
# Expected: Contains id, timestamp, strategy_name, context, results, assessment

# 4. Verify hypotheses file created
cat memory/hypotheses.yaml
# Expected: Contains initial hypotheses from v1.5 learnings

# 5. Test loading via Python
uv run python -c "
from ktrdr.agents.memory import load_experiments, get_open_hypotheses
exps = load_experiments(n=5)
hyps = get_open_hypotheses()
print(f'Loaded {len(exps)} experiments, {len(hyps)} open hypotheses')
assert len(exps) == 5
assert len(hyps) >= 1
print('OK')
"
```

**Success Criteria:**
- [ ] 24 experiment YAML files exist in `memory/experiments/`
- [ ] Each file has correct schema (id, timestamp, context, results, assessment)
- [ ] `hypotheses.yaml` exists with initial hypotheses
- [ ] `load_experiments()` returns experiments sorted by timestamp desc
- [ ] `get_open_hypotheses()` returns hypotheses with status="untested"

---

## Task 1.1: Create Memory Module with Dataclasses

**File:** `ktrdr/agents/memory.py` (NEW)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Create the memory module with dataclasses for ExperimentRecord and Hypothesis, plus load/save functions. Focus on the data structures and file I/O, not the parsing logic (that's M2).

**Implementation Notes:**
- Use YAML for storage (human-readable, git-friendly)
- `load_experiments()` should gracefully handle missing directory (return [])
- Sort experiments by timestamp descending (most recent first)
- Generate IDs with format `exp_YYYYMMDD_HHMMSS_xxxx` (timestamp + random suffix)

**Code sketch:**
```python
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any
import yaml
import secrets

MEMORY_DIR = Path("memory")
EXPERIMENTS_DIR = MEMORY_DIR / "experiments"
HYPOTHESES_FILE = MEMORY_DIR / "hypotheses.yaml"


@dataclass
class ExperimentRecord:
    id: str
    timestamp: str
    strategy_name: str
    context: dict[str, Any]
    results: dict[str, Any]
    assessment: dict[str, Any]
    source: str = "agent"


@dataclass
class Hypothesis:
    id: str
    text: str
    source_experiment: str
    rationale: str
    status: str = "untested"
    tested_by: list[str] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now().isoformat())


def load_experiments(n: int = 15) -> list[dict]:
    """Load N most recent experiments."""
    if not EXPERIMENTS_DIR.exists():
        return []

    files = sorted(EXPERIMENTS_DIR.glob("*.yaml"),
                   key=lambda f: f.stat().st_mtime, reverse=True)

    experiments = []
    for f in files[:n]:
        experiments.append(yaml.safe_load(f.read_text()))
    return experiments


def save_experiment(record: ExperimentRecord) -> Path:
    """Save experiment to YAML file."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPERIMENTS_DIR / f"{record.id}.yaml"
    path.write_text(yaml.dump(asdict(record), default_flow_style=False, sort_keys=False))
    return path


def generate_experiment_id() -> str:
    """Generate unique experiment ID."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(4)
    return f"exp_{ts}_{suffix}"
```

**Tests:** `tests/unit/agents/test_memory.py`
- [ ] `test_load_experiments_empty_dir` — returns [] when no directory
- [ ] `test_load_experiments_returns_n_most_recent` — respects n parameter
- [ ] `test_load_experiments_sorted_by_timestamp` — most recent first
- [ ] `test_save_experiment_creates_file` — file exists with correct content
- [ ] `test_save_experiment_creates_directories` — handles missing parent dirs
- [ ] `test_generate_experiment_id_unique` — multiple calls return different IDs
- [ ] `test_generate_experiment_id_format` — matches expected pattern

**Acceptance Criteria:**
- [ ] ExperimentRecord and Hypothesis dataclasses defined
- [ ] `load_experiments(n)` works with empty/missing directory
- [ ] `save_experiment()` creates valid YAML files
- [ ] `generate_experiment_id()` produces unique IDs
- [ ] All unit tests pass

---

## Task 1.2: Add Hypothesis Functions

**File:** `ktrdr/agents/memory.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Add functions for hypothesis management: loading, saving, and status updates.

**Implementation Notes:**
- `hypotheses.yaml` stores all hypotheses in a single file (simpler than per-hypothesis files)
- `get_open_hypotheses()` filters by status="untested"
- `update_hypothesis_status()` modifies in place and rewrites file
- Generate IDs as `H_001`, `H_002`, etc. (sequential)

**Code sketch:**
```python
def get_all_hypotheses() -> list[dict]:
    """Load all hypotheses."""
    if not HYPOTHESES_FILE.exists():
        return []
    data = yaml.safe_load(HYPOTHESES_FILE.read_text())
    return data.get("hypotheses", [])


def get_open_hypotheses() -> list[dict]:
    """Get hypotheses with status='untested'."""
    return [h for h in get_all_hypotheses() if h.get("status") == "untested"]


def save_hypothesis(hypothesis: Hypothesis) -> None:
    """Add hypothesis to registry."""
    hypotheses = get_all_hypotheses()
    hypotheses.append(asdict(hypothesis))
    HYPOTHESES_FILE.parent.mkdir(parents=True, exist_ok=True)
    HYPOTHESES_FILE.write_text(yaml.dump({"hypotheses": hypotheses}, sort_keys=False))


def update_hypothesis_status(
    hypothesis_id: str,
    status: str,
    tested_by_experiment: str,
) -> None:
    """Update hypothesis status and add to tested_by list."""
    hypotheses = get_all_hypotheses()
    for h in hypotheses:
        if h["id"] == hypothesis_id:
            h["status"] = status
            h.setdefault("tested_by", []).append(tested_by_experiment)
            break
    HYPOTHESES_FILE.write_text(yaml.dump({"hypotheses": hypotheses}, sort_keys=False))


def generate_hypothesis_id() -> str:
    """Generate next hypothesis ID."""
    hypotheses = get_all_hypotheses()
    max_num = 0
    for h in hypotheses:
        if h["id"].startswith("H_"):
            try:
                num = int(h["id"][2:])
                max_num = max(max_num, num)
            except ValueError:
                pass
    return f"H_{max_num + 1:03d}"
```

**Tests:** `tests/unit/agents/test_memory.py` (add to existing)
- [ ] `test_get_all_hypotheses_empty` — returns [] when no file
- [ ] `test_get_open_hypotheses_filters` — only returns untested
- [ ] `test_save_hypothesis_appends` — adds to existing list
- [ ] `test_update_hypothesis_status_modifies` — status changes
- [ ] `test_update_hypothesis_status_adds_tested_by` — experiment added to list
- [ ] `test_generate_hypothesis_id_sequential` — H_001, H_002, etc.

**Acceptance Criteria:**
- [ ] `get_open_hypotheses()` filters correctly
- [ ] `save_hypothesis()` appends without overwriting
- [ ] `update_hypothesis_status()` modifies correct hypothesis
- [ ] ID generation is sequential and zero-padded
- [ ] All unit tests pass

---

## Task 1.3: Create Bootstrap Script

**File:** `scripts/bootstrap_v15_memory.py` (NEW)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Create a script that reads v1.5 results and strategy files, then creates experiment records and initial hypotheses. This is a one-time bootstrap to seed memory.

**Implementation Notes:**
- Parse `strategies/v15_*.yaml` for context (indicators, timeframe, zigzag)
- Parse `docs/agentic/v1.5/RESULTS.md` for test accuracy results
- Create experiment records with `source: "v1.5_bootstrap"`
- Create initial hypotheses based on v1.5 learnings
- Script should be idempotent (can re-run safely)

**Data sources:**
- Strategy files: `strategies/v15_*.yaml` → context fields
- Results table: `docs/agentic/v1.5/RESULTS.md` → test_accuracy, verdict

**Code sketch:**
```python
#!/usr/bin/env python3
"""Bootstrap memory from v1.5 experiment results."""

import re
from pathlib import Path
import yaml

from ktrdr.agents.memory import (
    ExperimentRecord, Hypothesis,
    save_experiment, save_hypothesis,
    EXPERIMENTS_DIR, HYPOTHESES_FILE,
)


def parse_v15_results() -> dict[str, dict]:
    """Parse results table from RESULTS.md.

    Note: raw_results.csv only contains validation accuracy.
    Test accuracy (held-out data) was analyzed separately and is
    documented in the RESULTS.md table. We parse the markdown table
    to extract these test accuracy values.
    """
    results_file = Path("docs/agentic/v1.5/RESULTS.md")
    content = results_file.read_text()

    # Parse the "Detailed Results" table which has test accuracy
    # Format: | Rank | Strategy | Test Acc | Val Acc | Gap | Signal |
    results = {}
    for match in re.finditer(
        r'\| \d+ \| \*?\*?(v15_\w+)\*?\*? \| \*?\*?(\d+\.\d+)%\*?\*? \|',
        content
    ):
        strategy = match.group(1)
        test_acc = float(match.group(2)) / 100
        results[strategy] = {"test_accuracy": test_acc}

    return results


def parse_strategy_file(path: Path) -> dict:
    """Extract context from strategy YAML."""
    config = yaml.safe_load(path.read_text())

    indicators = [ind["name"] for ind in config.get("indicators", [])]
    zigzag = config.get("training", {}).get("labels", {}).get("zigzag_threshold", 0.02)
    timeframe = config.get("training_data", {}).get("timeframes", {}).get("list", ["1h"])[0]

    return {
        "indicators": indicators,
        "composition": "solo" if len(indicators) == 1 else "pair" if len(indicators) == 2 else "ensemble",
        "timeframe": timeframe,
        "symbol": "EURUSD",
        "zigzag_threshold": zigzag,
    }


def determine_verdict(test_acc: float) -> str:
    """Determine verdict from test accuracy."""
    if test_acc >= 0.60:
        return "strong_signal"
    elif test_acc >= 0.55:
        return "weak_signal"
    else:
        return "no_signal"


def main():
    # Clear existing bootstrap data
    if EXPERIMENTS_DIR.exists():
        for f in EXPERIMENTS_DIR.glob("exp_v15_*.yaml"):
            f.unlink()

    results = parse_v15_results()

    for strategy_file in sorted(Path("strategies").glob("v15_*.yaml")):
        strategy_name = strategy_file.stem
        if strategy_name not in results:
            continue

        context = parse_strategy_file(strategy_file)
        test_acc = results[strategy_name]["test_accuracy"]

        record = ExperimentRecord(
            id=f"exp_{strategy_name}",
            timestamp="2025-12-27T00:00:00Z",
            strategy_name=strategy_name,
            context=context,
            results={"test_accuracy": test_acc},
            assessment={
                "verdict": determine_verdict(test_acc),
                "observations": [],
                "hypotheses": [],
            },
            source="v1.5_bootstrap",
        )
        save_experiment(record)
        print(f"Created: {record.id}")

    # Create initial hypotheses
    # ... (based on v1.5 learnings)


if __name__ == "__main__":
    main()
```

**Tests:** Manual verification via E2E test
- [ ] Script runs without errors
- [ ] Creates correct number of experiment files
- [ ] Each file has valid schema

**Acceptance Criteria:**
- [ ] Script parses v1.5 results correctly
- [ ] Script parses strategy YAML files correctly
- [ ] Creates 24 experiment records (strategies with test metrics)
- [ ] Creates initial hypotheses from v1.5 learnings
- [ ] Script is idempotent (re-running doesn't duplicate)

---

## Task 1.4: Add Initial Hypotheses from v1.5

**File:** `scripts/bootstrap_v15_memory.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Add the initial hypotheses derived from v1.5 learnings to the bootstrap script. These are the starting points for v2.0 research.

**Hypotheses to create (from v1.5 RESULTS.md):**
1. Multi-timeframe (5m with 1h context) might break the 64.8% plateau
2. ADX might work as a trend filter when combined with RSI
3. LSTM/attention might capture RSI trajectories better than MLP
4. Training on multiple symbols might improve generalization
5. Zigzag threshold should scale with timeframe

**Code sketch:**
```python
INITIAL_HYPOTHESES = [
    Hypothesis(
        id="H_001",
        text="Multi-timeframe (5m with 1h context) might break the 64.8% plateau",
        source_experiment="exp_v15_rsi_zigzag_1_5",
        rationale="Single timeframe seems to be a ceiling. Adding context from higher TF might help.",
        status="untested",
    ),
    Hypothesis(
        id="H_002",
        text="ADX might work as a trend filter when combined with RSI",
        source_experiment="exp_v15_adx_only",
        rationale="ADX solo showed no signal, but it measures trend strength which could filter RSI entries.",
        status="untested",
    ),
    # ... more hypotheses
]
```

**Tests:** Manual verification
- [ ] `hypotheses.yaml` contains expected hypotheses
- [ ] Each hypothesis has required fields

**Acceptance Criteria:**
- [ ] 5+ initial hypotheses created
- [ ] Each linked to source experiment
- [ ] All have status="untested"
- [ ] Rationale explains why hypothesis is worth testing

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest tests/unit/agents/test_memory.py -v`
- [ ] E2E test passes (bootstrap script creates expected files)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
- [ ] Memory directory structure created and populated

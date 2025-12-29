# v2.0: Memory Foundation - Design

## Problem Statement

The agent currently has **zero memory** between sessions. This causes:

1. **Repetition**: Same strategies designed multiple times
2. **Ignorance**: Agent doesn't know what was tried or what happened
3. **No learning**: Can't build on successes or learn from failures
4. **Random exploration**: No hypotheses, no systematic investigation

Without memory, the agent is a random strategy generator. With memory, it becomes a researcher that improves over time.

---

## Goals

**Primary Goal**: Agent designs better strategies by reasoning about past experiments.

**Measurable Outcomes**:

1. Zero duplicate experiments (agent checks before designing)
2. Agent cites past results when explaining design choices
3. Agent generates testable hypotheses
4. Strategy quality improves over time (not random variation)

**Stretch Goal**: Agent requests new capabilities it needs to progress.

---

## Non-Goals (Out of Scope for v2.0)

1. **Multi-agent coordination** — Single agent with memory first
2. **Vector search / semantic matching** — Simple text injection is sufficient
3. **Database-backed memory** — Files are fine for MVP scale

---

## Core Insight: Observations, Not Rules

### The Danger of Prescriptive Memory

Saying "ADX doesn't work" closes doors that should stay open:

- ADX solo on 1h EURUSD: no signal → but what about 1d?
- ADX solo: no signal → but what about ADX as part of a regime detection system?
- Zigzag 3.5% overfits on 1h → but maybe perfect for 5m?
- RSI is great solo → but how does it interact with 5 other components?

**Learnings are contextual observations, not universal rules.**

### The Solution: Contextual Experiment Records

Instead of:
```markdown
### What Doesn't Work
- ADX solo: 50% (random noise)  ← DANGEROUS: closes the door on ADX forever
```

Store:
```yaml
experiment:
  id: exp_v15_adx_only
  context:
    indicators: [ADX]
    composition: solo  # solo, pair, ensemble
    timeframe: 1h
    symbol: EURUSD
    zigzag_threshold: 0.02
  results:
    test_accuracy: 0.50
    val_accuracy: 0.584
    val_test_gap: 0.084
  observation: "No predictive signal detected in this specific configuration"
```

The agent sees the fact **with its context**, then reasons:

> "ADX solo on 1h showed no signal. But I'm trying 1d now with different market dynamics. Or maybe ADX works as a filter when combined with RSI. Let me test."

**The agent synthesizes patterns on the fly. No pre-baked rules.**

---

## Memory Components

### 1. Experiment Records (Primary Memory)

Every completed experiment becomes a record with full context:

```yaml
experiment:
  id: "exp_20251228_001"
  timestamp: "2025-12-28T14:30:00Z"
  strategy_name: "rsi_di_v3"

  # Full context - what makes this experiment unique
  context:
    indicators: ["RSI", "DI"]
    indicator_params:
      RSI: {period: 14}
      DI: {period: 14}
    composition: "pair"  # solo | pair | trio | ensemble
    timeframe: "1h"
    symbol: "EURUSD"
    zigzag_threshold: 0.015
    nn_architecture: [32, 16]
    training_epochs: 100
    data_range: "2015-2023"

  # What happened
  results:
    test_accuracy: 0.648
    val_accuracy: 0.665
    val_test_gap: 0.017
    sharpe_ratio: 0.42
    total_trades: 847
    win_rate: 0.52

  # Agent's interpretation (generated during assessment)
  assessment:
    verdict: "strong_signal"  # strong_signal | weak_signal | no_signal | overfit
    observations:
      - "Combining RSI with DI improved test accuracy by 0.6pp vs RSI solo"
      - "Val-test gap of 1.7pp suggests good generalization"
      - "This is the best result on 1h EURUSD so far"
    hypotheses:
      - text: "Adding a third complementary indicator might help"
        status: "untested"
      - text: "This approach might work on other forex pairs"
        status: "untested"
    limitations:
      - "Only tested on EURUSD"
      - "Only tested on 1h timeframe"
    capability_requests: []
```

**Key principle**: Every observation is tied to its context. Nothing is stated as universal truth.

**Storage**: YAML files in `memory/experiments/` directory

**When created**: Automatically after assessment phase

### 2. Hypothesis Registry

Hypotheses extracted from experiments, tracked across sessions:

```yaml
hypotheses:
  - id: "H_001"
    text: "Multi-timeframe (5m with 1h context) might break the 64.8% plateau"
    source_experiment: "exp_20251228_001"
    rationale: "Single timeframe seems to be a ceiling. Adding context from higher TF might help."
    status: "untested"  # untested | testing | validated | refuted | inconclusive
    tested_by: []  # list of experiment IDs that tested this
    created: "2025-12-28"

  - id: "H_002"
    text: "ADX might work as a trend filter when combined with RSI"
    source_experiment: "exp_v15_adx_only"
    rationale: "ADX solo showed no signal, but it measures trend strength which could filter RSI entries"
    status: "untested"
    tested_by: []
    created: "2025-12-28"
```

**Storage**: `memory/hypotheses.yaml`

**When updated**: After each assessment (new hypotheses added, status updated)

### 3. Capability Requests

What the agent wishes it could try:

```yaml
requests:
  - id: "req_001"
    capability: "5m data aligned with 1h bars"
    rationale: "To test multi-timeframe hypothesis H_001"
    requested_by: "exp_20251228_003"
    requested: "2025-12-28"
    status: "pending"  # pending | approved | implemented | rejected
    implemented: null

  - id: "req_002"
    capability: "LSTM architecture option"
    rationale: "To test if RSI trajectory patterns matter"
    requested_by: "exp_20251228_005"
    requested: "2025-12-28"
    status: "pending"
    implemented: null
```

**Storage**: `memory/capability_requests.yaml`

**When updated**: Agent can request during assessment

---

## How Memory is Injected

### Prompt Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                      SYSTEM PROMPT                               │
│  Role, tools, guidelines                                        │
│  + NEW: Instructions for using experiment history               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      USER PROMPT                                 │
│                                                                 │
│  ## Current Context                                             │
│  Trigger: start_new_cycle                                       │
│  Operation ID: ...                                              │
│                                                                 │
│  ## Experiment History   ◀──── Contextual facts, not rules      │
│  [Last 10-20 experiments, formatted for reasoning]              │
│                                                                 │
│  ## Open Hypotheses      ◀──── What to explore                  │
│  [Untested hypotheses from previous experiments]                │
│                                                                 │
│  ## Available Resources                                         │
│  [Indicators, symbols, capabilities]                            │
│                                                                 │
│  ## Your Task                                                   │
│  Design a new strategy. Reason about past experiments.          │
│  Generate hypotheses. Request capabilities if needed.           │
└─────────────────────────────────────────────────────────────────┘
```

### Experiment History Format

The agent sees experiments as contextual observations:

```markdown
## Experiment History

### Recent Experiments (last 10)

**exp_v15_rsi_di** (2025-12-27)
- Context: RSI + DI | 1h | EURUSD | zigzag 1.5% | NN [32,16]
- Results: 64.8% test (66.5% val, 1.7pp gap) | Sharpe 0.42
- Verdict: strong_signal
- Observations:
  - Combining RSI with DI improved by 0.6pp vs RSI solo
  - Best result on 1h EURUSD so far
- Hypotheses generated:
  - "Multi-timeframe might break this plateau" (untested)

**exp_v15_adx_only** (2025-12-27)
- Context: ADX solo | 1h | EURUSD | zigzag 2.0% | NN [32,16]
- Results: 50.0% test (58.4% val, 8.4pp gap)
- Verdict: no_signal
- Observations:
  - No predictive signal in this configuration
  - Large val-test gap suggests validation was misleading
- Hypotheses generated:
  - "ADX might work as filter with other indicators" (untested)

**exp_v15_rsi_zigzag_3_5** (2025-12-27)
- Context: RSI solo | 1h | EURUSD | zigzag 3.5% | NN [32,16]
- Results: 55.5% test (71.2% val, 15.7pp gap)
- Verdict: overfit
- Observations:
  - Massive val-test gap indicates overfitting
  - Larger zigzag = fewer labels = model memorizes patterns
  - Note: This was on 1h with limited labels. Different TFs may behave differently.
- Hypotheses generated:
  - "Smaller zigzag thresholds generalize better" (validated on 1h)
  - "Zigzag threshold should scale with timeframe" (untested)
```

### What the Agent Does

The agent **reasons about the context**, not follows rules:

```
Agent thinking: "I see ADX solo on 1h showed no signal. But that was:
- Solo (no other indicators)
- On 1h (maybe different on 1d where trends are clearer)
- With zigzag 2.0% (maybe different threshold would help)

There's an untested hypothesis that ADX might work as a filter.
Let me try: RSI + ADX (as trend strength filter) on 1h.
This tests whether ADX adds value in composition even though it failed solo."
```

---

## Automated Memory Generation

### During Assessment Phase

The agent already writes assessments. We structure the output:

```markdown
## Assessment

### Verdict
strong_signal

### Observations
- [Observation 1 with specific context]
- [Observation 2 with specific context]

### Hypotheses Generated
- H: [Hypothesis text] | Status: untested
- H: [Hypothesis text] | Status: untested

### Limitations
- [What wasn't tested]
- [Conditions that might change results]

### Capability Requests
- [What I wish I could try]
```

### Parsing and Storage

After assessment:
1. Parse the structured assessment output
2. Create experiment record with full context
3. Extract new hypotheses → add to registry
4. Extract capability requests → add to requests
5. Update hypothesis status if this experiment tested one

**No human curation required.** The system is self-maintaining.

---

## Bootstrap: v1.5 as Experiment Records

Convert v1.5 results into experiment records (not rules):

```yaml
# memory/experiments/exp_v15_rsi_zigzag_1_5.yaml
experiment:
  id: "exp_v15_rsi_zigzag_1_5"
  timestamp: "2025-12-27T00:00:00Z"
  strategy_name: "v15_rsi_zigzag_1_5"
  source: "v1.5_experiments"  # marks this as historical

  context:
    indicators: ["RSI"]
    indicator_params:
      RSI: {period: 14}
    composition: "solo"
    timeframe: "1h"
    symbol: "EURUSD"
    zigzag_threshold: 0.015
    nn_architecture: [32, 16]
    training_epochs: 100
    data_range: "2015-2023"

  results:
    test_accuracy: 0.642
    val_accuracy: 0.654
    val_test_gap: 0.012
    sharpe_ratio: null  # not recorded in v1.5

  assessment:
    verdict: "strong_signal"
    observations:
      - "RSI solo achieves 64.2% test accuracy on 1h EURUSD"
      - "Small val-test gap (1.2pp) indicates good generalization"
      - "This is with zigzag 1.5% labeling"
    hypotheses:
      - text: "Adding complementary indicator (trend) might improve"
        status: "validated"
        tested_by: ["exp_v15_rsi_di"]
      - text: "This might work on other timeframes"
        status: "untested"
    limitations:
      - "Only tested on 1h EURUSD"
      - "Only tested solo"
```

**27 experiment records** from v1.5 become the initial memory.

---

## Implementation Plan

### Phase 1: Memory Infrastructure

1. Create `memory/` directory structure
2. Convert v1.5 results to experiment records
3. Build memory loader (load experiments, hypotheses, requests)
4. Build experiment formatter (for prompt injection)

### Phase 2: Prompt Integration

1. Add experiment history to prompt context
2. Add open hypotheses to prompt context
3. Update system prompt with memory reasoning instructions
4. Test: Does agent reference experiments?

### Phase 3: Automated Recording

1. Structure assessment output format
2. Parse assessment into experiment record
3. Auto-save after each assessment
4. Extract and track hypotheses

### Phase 4: Hypothesis Lifecycle

1. Track hypothesis status across experiments
2. Update status when experiments test hypotheses
3. Agent sees which hypotheses are tested/untested/validated

### Phase 5: Capability Requests

1. Parse capability requests from assessment
2. Store in requests registry
3. Human reviews and implements
4. Agent sees what capabilities are available

---

## Changes to Existing Code

### Prompt Builder (`ktrdr/agents/prompts.py`)

```python
@dataclass
class PromptContext:
    # ... existing fields ...
    experiment_history: list[dict] | None = None  # NEW
    open_hypotheses: list[dict] | None = None  # NEW
    available_capabilities: list[str] | None = None  # NEW
```

```python
def _format_experiment_history(self, experiments: list[dict]) -> str:
    """Format experiments as contextual observations for reasoning."""
    if not experiments:
        return "No previous experiments recorded."

    lines = ["## Experiment History\n"]
    for exp in experiments[:15]:  # Last 15 experiments
        lines.append(self._format_single_experiment(exp))
    return "\n".join(lines)

def _format_single_experiment(self, exp: dict) -> str:
    """Format one experiment with full context."""
    ctx = exp.get("context", {})
    res = exp.get("results", {})
    assess = exp.get("assessment", {})

    # Build context string
    indicators = " + ".join(ctx.get("indicators", []))
    context_str = f"{indicators} | {ctx.get('timeframe')} | {ctx.get('symbol')} | zigzag {ctx.get('zigzag_threshold')}"

    # Build results string
    test_acc = res.get("test_accuracy", 0) * 100
    val_acc = res.get("val_accuracy", 0) * 100
    gap = res.get("val_test_gap", 0) * 100

    lines = [
        f"**{exp['id']}** ({exp.get('timestamp', 'unknown')[:10]})",
        f"- Context: {context_str}",
        f"- Results: {test_acc:.1f}% test ({val_acc:.1f}% val, {gap:.1f}pp gap)",
        f"- Verdict: {assess.get('verdict', 'unknown')}",
    ]

    if assess.get("observations"):
        lines.append("- Observations:")
        for obs in assess["observations"][:3]:
            lines.append(f"  - {obs}")

    return "\n".join(lines) + "\n"
```

### Memory Module (NEW: `orchestrator/memory.py`)

```python
from pathlib import Path
import yaml
from datetime import datetime

MEMORY_DIR = Path("memory")
EXPERIMENTS_DIR = MEMORY_DIR / "experiments"
HYPOTHESES_FILE = MEMORY_DIR / "hypotheses.yaml"
REQUESTS_FILE = MEMORY_DIR / "capability_requests.yaml"


def load_experiments(n: int = 20) -> list[dict]:
    """Load the N most recent experiment records."""
    if not EXPERIMENTS_DIR.exists():
        return []

    files = sorted(EXPERIMENTS_DIR.glob("*.yaml"), key=lambda f: f.stat().st_mtime, reverse=True)
    experiments = []
    for f in files[:n]:
        experiments.append(yaml.safe_load(f.read_text()))
    return experiments


def save_experiment(record: dict) -> Path:
    """Save an experiment record."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{record['id']}.yaml"
    path = EXPERIMENTS_DIR / filename
    path.write_text(yaml.dump(record, default_flow_style=False))
    return path


def load_hypotheses() -> list[dict]:
    """Load all hypotheses."""
    if not HYPOTHESES_FILE.exists():
        return []
    data = yaml.safe_load(HYPOTHESES_FILE.read_text())
    return data.get("hypotheses", [])


def save_hypothesis(hypothesis: dict) -> None:
    """Add a hypothesis to the registry."""
    hypotheses = load_hypotheses()
    hypotheses.append(hypothesis)
    HYPOTHESES_FILE.parent.mkdir(parents=True, exist_ok=True)
    HYPOTHESES_FILE.write_text(yaml.dump({"hypotheses": hypotheses}))


def get_open_hypotheses() -> list[dict]:
    """Get untested hypotheses for the agent to consider."""
    return [h for h in load_hypotheses() if h.get("status") == "untested"]
```

### Assessment Parser (NEW)

```python
def parse_assessment(output: str, experiment_context: dict) -> dict:
    """Parse agent assessment into structured experiment record."""
    # Extract verdict, observations, hypotheses from agent output
    # Create experiment record with full context
    # Return structured record ready for storage
    ...
```

---

## Success Criteria

### Minimum Viable Memory

- [ ] v1.5 experiments loaded as records
- [ ] Experiment history injected into prompt
- [ ] Agent mentions past experiments when designing
- [ ] Agent avoids exact duplicate configurations

### Full v2.0

- [ ] Agent generates structured assessment
- [ ] Experiments auto-saved after each cycle
- [ ] Hypotheses tracked across sessions
- [ ] Agent pursues open hypotheses
- [ ] Agent reasons about context (not follows rules)

### Evidence of Contextual Reasoning

We'll know it's working when the agent says:

```
"I see ADX solo on 1h showed no signal (exp_v15_adx_only). However, that
was tested in isolation. Hypothesis H_002 suggests ADX might work as a
trend filter with RSI. Let me test: RSI for entry signals, ADX > 25 as
a trend confirmation filter. This explores whether ADX adds value in
composition even though it failed solo."
```

vs. the dangerous version:

```
"ADX doesn't work, so I won't use it."
```

---

## Key Design Principles

### 1. Context is Everything

Every observation is tied to its specific conditions:
- Indicator configuration
- Timeframe
- Symbol
- Composition (solo vs. combined)
- Labeling parameters

### 2. No Universal Rules

The memory never says "X doesn't work." It says "X showed Y result in Z conditions."

### 3. Agent Reasons, System Records

The system stores facts. The agent synthesizes patterns. This happens fresh each cycle, avoiding stale rules.

### 4. Automated from Day One

No human curation. Agent generates observations during assessment. System stores them automatically.

### 5. Hypotheses Drive Exploration

Open hypotheses guide the agent toward systematic investigation rather than random exploration.

---

*Document Version: 2.0*
*Created: 2025-12-28*
*Revised: 2025-12-28 - Removed prescriptive rules, added contextual observations*
*Status: Ready for implementation*

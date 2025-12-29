# v2.0: Memory Foundation - Design Validation

**Date:** 2025-12-28
**Documents Validated:**
- Design: [DESIGN.md](DESIGN.md)
- Philosophy: [PHILOSOPHY.md](PHILOSOPHY.md)

**Scope:** Full v2.0 implementation

---

## Validation Summary

**Scenarios Validated:** 8 traced, all integration points identified
**Critical Gaps Found:** 3 (all resolved)
**Interface Contracts:** Defined for memory module, HaikuBrain, PromptContext

---

## Key Decisions Made

These decisions came from the validation conversation and should inform implementation:

### 1. Always Use Haiku for Parsing
- **Context:** Agent output is inherently variable - structured headers, prose, mixed formats
- **Decision:** Always use Haiku to parse assessments, never regex-first with fallback
- **Trade-off:** Slightly higher latency (~200ms) and cost (~$0.0001) per parse, but much more robust

### 2. Shared HaikuBrain
- **Context:** Both orchestrator and research agent need Haiku-based text interpretation
- **Decision:** Refactor HaikuBrain to `ktrdr/llm/haiku_brain.py` as shared component
- **Trade-off:** Requires import updates in orchestrator, but avoids duplicate Haiku-calling logic

### 3. Memory Lives in ktrdr/agents/
- **Context:** Memory is about the research loop, not the orchestrator's coding tasks
- **Decision:** Create `ktrdr/agents/memory.py` for experiment/hypothesis persistence
- **Trade-off:** None significant - clean separation of concerns

### 4. Caller Loads Memory
- **Context:** Need to inject experiment history into prompts
- **Decision:** Design worker loads memory and passes to PromptContext (not PromptBuilder loading internally)
- **Trade-off:** Slightly more code in worker, but keeps PromptBuilder pure and testable

### 5. Context Flows Through Pipeline
- **Context:** When saving experiment records, we need strategy config details (indicators, timeframe, etc.)
- **Decision:** strategy_config already in PromptContext, flows through to assessment, available at save time
- **Trade-off:** None - leverages existing data flow

---

## Scenarios Validated

### Happy Paths

#### 1. Fresh Start with Memory
**Trigger:** Agent invoked with `trigger_reason: start_new_cycle`
**Flow:**
1. Design worker calls `memory.load_experiments(n=15)`
2. Design worker calls `memory.get_open_hypotheses()`
3. PromptBuilder formats experiment history + hypotheses into prompt
4. Agent receives context, designs strategy referencing past experiments

**Integration Points:**
- `design_worker.py:197-217` - add memory loading after existing context gathering
- `prompts.py:PromptContext` - add `experiment_history`, `open_hypotheses` fields
- `prompts.py:StrategyDesignerPromptBuilder` - add `_format_experiment_history()` method

#### 2. Assessment Creates Memory
**Trigger:** Agent completes assessment phase
**Flow:**
1. Assessment worker gets verdict, strengths, weaknesses, suggestions
2. HaikuBrain.parse_assessment() extracts structured observations + hypotheses
3. memory.save_experiment() writes record to `memory/experiments/{id}.yaml`
4. memory.extract_hypotheses() adds new hypotheses to registry

**Integration Points:**
- `assessment_worker.py:266-275` - add memory save after building assessment_result
- `ktrdr/llm/haiku_brain.py` - add `parse_assessment()` method
- `ktrdr/agents/memory.py` - new module

#### 3. Hypothesis Lifecycle
**Trigger:** Agent tests a specific hypothesis
**Flow:**
1. Agent sees `H_002: ADX as filter` in open hypotheses
2. Agent designs strategy explicitly to test this hypothesis
3. Assessment mentions "H_002 validated" or "H_002 refuted"
4. HaikuBrain extracts hypothesis status from assessment
5. memory.update_hypothesis_status() updates registry

**Integration Points:**
- `haiku_brain.py:parse_assessment()` - extract hypothesis references
- `memory.py:update_hypothesis_status()` - new function

### Error Paths

#### 4. Malformed Assessment
**Trigger:** Agent produces unstructured prose assessment
**Flow:**
1. Agent writes: "This strategy performed well because..."
2. HaikuBrain.parse_assessment() extracts what it can from prose
3. Record saved with partial data, `raw_text` preserved

**Decision:** Always produce a record, even if incomplete. Haiku extracts best-effort.

#### 5. Memory Load Failure
**Trigger:** `memory/` directory missing or corrupted
**Flow:**
1. memory.load_experiments() returns empty list
2. Agent proceeds without history (graceful degradation)
3. Log warning for visibility

**Decision:** Memory is enhancement, not requirement. Agent works without it.

### Edge Cases

#### 6. Duplicate Experiment Detection
**Trigger:** Agent designs nearly identical experiment to past one
**Flow:**
1. Experiment history shows similar past experiment
2. Agent (hopefully) notices and tries something different
3. If agent ignores, duplicate gets recorded anyway

**Decision:** No hard enforcement - agent is responsible for novelty. Memory enables but doesn't enforce.

#### 7. Memory Overflow
**Trigger:** 100+ experiments in memory
**Flow:**
1. memory.load_experiments(n=15) returns 15 most recent by timestamp
2. Older experiments still exist, just not injected into prompt

**Decision:** Simple recency-based selection. Future enhancement could add relevance scoring.

### Integration Boundaries

#### 8. Bootstrap from v1.5
**Trigger:** Initial memory population
**Flow:**
1. Script reads `docs/agentic/v1.5/RESULTS.md` for metrics
2. Script reads `strategies/v15_*.yaml` for context (indicators, params, zigzag)
3. Creates 24 experiment records with `source: "v1.5_bootstrap"`

**Decision:** Parse strategy YAML files for missing context. Mark as bootstrap source.

---

## Interface Contracts

### Memory Module (`ktrdr/agents/memory.py`)

```python
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import yaml

MEMORY_DIR = Path("memory")
EXPERIMENTS_DIR = MEMORY_DIR / "experiments"
HYPOTHESES_FILE = MEMORY_DIR / "hypotheses.yaml"


@dataclass
class ExperimentRecord:
    """A single experiment with full context."""
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
    """A testable hypothesis tracked across experiments."""
    id: str
    text: str
    source_experiment: str
    rationale: str
    status: str  # "untested" | "validated" | "refuted" | "inconclusive"
    tested_by: list[str] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now().isoformat())


# === Loading ===

def load_experiments(n: int = 15) -> list[dict]:
    """Load N most recent experiments, sorted by timestamp desc.

    Returns empty list if memory directory doesn't exist (graceful degradation).
    """
    ...

def get_open_hypotheses() -> list[dict]:
    """Get hypotheses with status='untested'."""
    ...

def get_all_hypotheses() -> list[dict]:
    """Get all hypotheses regardless of status."""
    ...


# === Saving ===

def save_experiment(record: ExperimentRecord) -> Path:
    """Save experiment record to memory/experiments/{id}.yaml.

    Creates directories if needed.
    """
    ...

def save_hypothesis(hypothesis: Hypothesis) -> None:
    """Add hypothesis to registry."""
    ...

def update_hypothesis_status(
    hypothesis_id: str,
    status: str,
    tested_by_experiment: str,
) -> None:
    """Update hypothesis status and add to tested_by list."""
    ...


# === ID Generation ===

def generate_experiment_id() -> str:
    """Generate unique experiment ID like 'exp_20251228_143052_abc123'."""
    ...

def generate_hypothesis_id() -> str:
    """Generate unique hypothesis ID like 'H_001'."""
    ...
```

### HaikuBrain Extension (`ktrdr/llm/haiku_brain.py`)

```python
from dataclasses import dataclass
from typing import Any


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


class HaikuBrain:
    """Shared Haiku-based text interpreter.

    Used by:
    - orchestrator: interpret Claude Code task output
    - research agent: parse assessment output into structured records
    """

    # ... existing methods (interpret_result, should_retry_or_escalate) ...

    def parse_assessment(
        self,
        output: str,
        context: dict[str, Any],  # strategy_config, training_results, backtest_results
    ) -> ParsedAssessment:
        """Extract structured assessment from any format using Haiku.

        Haiku interprets the agent's assessment text (which may be structured,
        prose, or mixed) and extracts:
        - Verdict classification
        - Key observations
        - New hypotheses generated
        - Limitations noted
        - Capability requests
        - References to existing hypotheses being tested

        Always returns a result, even if some fields are empty.
        """
        ...
```

### PromptContext Extension (`ktrdr/agents/prompts.py`)

```python
@dataclass
class PromptContext:
    """Context for building the strategy designer prompt."""

    trigger_reason: TriggerReason
    operation_id: str
    phase: str
    available_indicators: list[dict[str, Any]] | None = None
    available_symbols: list[dict[str, Any]] | None = None
    recent_strategies: list[dict[str, Any]] | None = None
    training_results: dict[str, Any] | None = None
    backtest_results: dict[str, Any] | None = None
    strategy_config: dict[str, Any] | None = None

    # NEW: Memory context
    experiment_history: list[dict[str, Any]] | None = None
    open_hypotheses: list[dict[str, Any]] | None = None
```

### Experiment History Format (in prompt)

```markdown
## Experiment History

### Recent Experiments (last 15)

**exp_v15_rsi_di** (2025-12-27)
- Context: RSI + DI | 1h | EURUSD | zigzag 1.5% | NN [32,16]
- Results: 64.8% test (66.5% val, 1.7pp gap) | Sharpe 0.42
- Verdict: strong_signal
- Observations:
  - Combining RSI with DI improved by 0.6pp vs RSI solo
  - Best result on 1h EURUSD so far
- Hypotheses: "Multi-timeframe might break this plateau" (untested)

**exp_v15_adx_only** (2025-12-27)
- Context: ADX solo | 1h | EURUSD | zigzag 2.0% | NN [32,16]
- Results: 50.0% test (58.4% val, 8.4pp gap)
- Verdict: no_signal
- Observations:
  - No predictive signal in this configuration
  - Large val-test gap suggests validation was misleading
- Hypotheses: "ADX might work as filter with other indicators" (untested)

## Open Hypotheses

- **H_001**: Multi-timeframe (5m with 1h context) might break the 64.8% plateau
  - Source: exp_v15_rsi_di | Status: untested

- **H_002**: ADX might work as a trend filter when combined with RSI
  - Source: exp_v15_adx_only | Status: untested
```

---

## Implementation Milestones

### Milestone 1: Memory Infrastructure + Bootstrap
**E2E Test:** Load v1.5 experiments, verify format correct

**Scope:**
- Create `ktrdr/agents/memory.py` with load/save functions
- Create `memory/` directory structure
- Bootstrap script: `scripts/bootstrap_v15_memory.py`
- Unit tests for all memory functions

**Tasks:**
1. Create memory module with dataclasses and file operations
2. Write bootstrap script that parses v1.5 results + strategy YAMLs
3. Unit tests: load empty, load multiple, save, generate IDs

**E2E:**
```
Given: v1.5 results exist, strategies/v15_*.yaml exist
When: Run bootstrap script
Then: memory/experiments/ contains 24 YAML files with correct schema
      memory/hypotheses.yaml contains initial hypotheses from v1.5 learnings
```

---

### Milestone 2: Shared HaikuBrain Refactor
**E2E Test:** Both orchestrator and agent can use HaikuBrain

**Scope:**
- Move `orchestrator/haiku_brain.py` → `ktrdr/llm/haiku_brain.py`
- Update all orchestrator imports
- Add `parse_assessment()` method
- Verify orchestrator still works

**Tasks:**
1. Create `ktrdr/llm/` package
2. Move and update imports
3. Add parse_assessment method with Haiku prompt
4. Unit tests for parse_assessment (various input formats)

**E2E:**
```
Given: HaikuBrain refactored to shared location
When: Run orchestrator tests + agent tests
Then: All existing tests pass
      New parse_assessment method correctly extracts from prose/structured/mixed
```

---

### Milestone 3: Prompt Integration (Read Path)
**E2E Test:** Agent sees experiment history in prompt

**Scope:**
- Extend `PromptContext` with experiment_history, open_hypotheses
- Add `_format_experiment_history()` to PromptBuilder
- Modify `design_worker.py` to load and pass memory
- Update system prompt with memory reasoning instructions

**Tasks:**
1. Add fields to PromptContext
2. Implement experiment history formatting
3. Implement hypothesis formatting
4. Update design worker to load memory
5. Update system prompt with memory usage instructions

**E2E:**
```
Given: 5 experiments in memory/experiments/, 2 open hypotheses
When: Trigger design phase (can use stub invoker)
Then: Built prompt contains "## Experiment History" with 5 experiments
      Built prompt contains "## Open Hypotheses" with 2 hypotheses
```

---

### Milestone 4: Assessment → Memory (Write Path)
**E2E Test:** Assessment creates experiment record

**Scope:**
- Assessment worker calls HaikuBrain.parse_assessment()
- Assessment worker calls memory.save_experiment()
- Handle malformed output gracefully

**Tasks:**
1. Integrate parse_assessment into assessment_worker
2. Build ExperimentRecord from parsed + context
3. Save after successful assessment
4. Graceful handling if parse partially fails

**E2E:**
```
Given: Agent completes assessment with verdict="promising"
When: Assessment worker finishes
Then: New file exists in memory/experiments/
      File contains correct context (from strategy_config)
      File contains correct results (from training/backtest metrics)
      File contains parsed assessment (verdict, observations)
```

---

### Milestone 5: Hypothesis Lifecycle
**E2E Test:** Agent tests hypothesis, status updates

**Scope:**
- Extract new hypotheses from assessments
- Detect when agent references existing hypothesis
- Update hypothesis status based on assessment

**Tasks:**
1. Enhance parse_assessment to extract hypothesis references
2. Add hypothesis extraction and saving to assessment flow
3. Update existing hypothesis status when tested
4. Inject open hypotheses into design prompt (if not done in M3)

**E2E:**
```
Given: H_001 exists with status="untested"
When: Assessment includes "H_001 validated - multi-timeframe improved accuracy"
Then: hypotheses.yaml shows H_001 status="validated"
      H_001.tested_by includes new experiment ID
      New hypotheses from assessment added to registry
```

---

## File Structure After Implementation

```
ktrdr/
├── llm/
│   ├── __init__.py
│   └── haiku_brain.py          # Shared Haiku interpreter (moved from orchestrator)
├── agents/
│   ├── memory.py               # NEW: experiment/hypothesis persistence
│   ├── prompts.py              # Extended with experiment_history, open_hypotheses
│   ├── design_worker.py        # Modified to load memory
│   └── assessment_worker.py    # Modified to save memory

memory/
├── experiments/
│   ├── exp_v15_rsi_zigzag_1_5.yaml
│   ├── exp_v15_adx_only.yaml
│   └── ...                     # 24 bootstrap + new experiments
└── hypotheses.yaml             # Hypothesis registry

orchestrator/
├── runner.py                   # Updated import: from ktrdr.llm.haiku_brain
└── ...                         # No other changes

scripts/
└── bootstrap_v15_memory.py     # One-time bootstrap script
```

---

## Open Questions (To Resolve During Implementation)

1. **Hypothesis ID format:** Design shows `H_001`, but should we use something more descriptive like `H_multi_timeframe_001`?

2. **Memory directory location:** Design shows `memory/` at repo root. Should it be `data/memory/` to match other data directories?

3. **Capability requests:** Design includes them but Milestone 5 doesn't fully implement. Defer to v2.1?

---

*Validation completed: 2025-12-28*
*Validated by: Claude + Karl*

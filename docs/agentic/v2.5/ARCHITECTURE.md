# v2.5 Agent Reliability: Architecture

## Overview

This document describes the technical implementation of v2.5 Agent Reliability features. The core changes are:

1. **Research Brief** — Add `brief` parameter to guide agent toward specific configurations
2. **Baby Stage Gates** — Lax thresholds that only catch catastrophic failures
3. **Pipeline Error Propagation** — Every step fails loudly instead of returning zeros
4. **Failed Experiment Recording** — Save failures with error context to memory
5. **Fix Multi-Symbol Pipeline** — Make multi-symbol training actually work
6. **Fix Multi-Timeframe Pipeline** — Make multi-timeframe training actually work

---

## Components

### Component 1: Research Brief Parameter

**Responsibility:** Accept a `brief` parameter and pass it through to the prompt.

**Location:** `ktrdr/agents/prompts.py`

**Current State:**

The `get_strategy_designer_prompt()` function builds the system prompt. It receives context (past experiments, hypotheses) but has no `brief` parameter.

**Changes Required:**

Add `brief` as a parameter to `get_strategy_designer_prompt()`. The prompt template itself (in the same file or a separate `.md` file) should include a placeholder for the brief:

```markdown
## Research Brief

{brief}

Follow this brief carefully when designing your strategy.

---

## Your Task
...
```

When `brief` is None, that section is omitted.

**Open Decision:** Should prompts live in `.md` files or stay in Python code? Either way, the brief becomes a template variable, not special injection logic.

**Dependencies:** None — additive change

---

### Component 2: Baby Gate Thresholds

**Responsibility:** Set lax gate thresholds for exploration, add catastrophic failure check.

**Location:** `ktrdr/agents/gates.py`

**Current State:**

```python
# Current thresholds (too strict for exploration)
@dataclass
class GateConfig:
    min_accuracy: float = 0.45
    max_loss: float = 0.8
    min_loss_decrease: float = 0.2
```

**Changes Required:**

Simply update the default thresholds to Baby-appropriate values:

```python
# gates.py

@dataclass
class GateConfig:
    min_accuracy: float = 0.10        # Only catch 0-10% (completely broken)
    max_loss: float = 0.8
    min_loss_decrease: float = -0.5   # Allow regression while exploring
    min_win_rate: float = 0.10        # Only catch catastrophic backtest


def check_training_gate(metrics: dict, config: GateConfig | None = None) -> tuple[bool, str]:
    """Check if training metrics pass the gate."""
    if config is None:
        config = GateConfig()

    accuracy = metrics.get("test_accuracy", 0)

    # Catastrophic failure check (always applies, regardless of config)
    if accuracy == 0.0:
        return False, "training_completely_failed (0% accuracy)"

    if accuracy < config.min_accuracy:
        return False, f"accuracy_too_low ({accuracy:.1%} < {config.min_accuracy:.1%})"

    # ... other checks
    return True, "passed"
```

**Note:** The maturity model (Baby → Teenager progression) is documented in the v2.5 DESIGN but NOT implemented in code. We just set Baby thresholds. Future versions will add stage progression.

**Dependencies:** None — existing file, threshold changes only

---

### Component 3: Pipeline Error Propagation

**Responsibility:** Raise exceptions when ANY pipeline step fails instead of returning zeros or continuing silently.

**Locations:**

- `ktrdr/training/training_pipeline.py` — Training failures
- `ktrdr/backtesting/backtest_runner.py` — Backtest failures
- `ktrdr/agents/workers/*_worker.py` — Worker-level error handling

**Principle:** Every step should fail loudly. Silent failures hide bugs.

**Training Example (current silent failure):**

```python
# Line ~650-671
if X_test is None or y_test is None:
    logger.warning("No test data provided - returning zero metrics")
    return {"test_accuracy": 0.0, ...}  # BAD: Silent failure
```

**Training Fix:**

```python
class TrainingDataError(Exception):
    """Raised when training cannot produce valid data."""
    pass

if X_test is None or y_test is None:
    raise TrainingDataError(
        "Training produced no test data. "
        "Check data pipeline for multi-symbol/multi-timeframe issues."
    )
```

**Backtest Example:**

```python
class BacktestError(Exception):
    """Raised when backtest fails."""
    pass

if len(trades) == 0 and len(signals) > 0:
    raise BacktestError(
        "Backtest produced 0 trades despite signals. "
        "Check signal-to-trade conversion logic."
    )
```

**Worker-Level Handling:**

Each worker catches step-specific errors and converts them to a unified result:

```python
# In any worker
try:
    result = await run_step(...)
except (TrainingDataError, BacktestError) as e:
    return StepResult(
        success=False,
        error=str(e),
        error_type=type(e).__name__,
    )
```

**Audit Required:** Review all pipeline steps for places that return zeros, empty results, or log-and-continue patterns. Convert to exceptions.

**Dependencies:** Changes to callers needed to handle exceptions

---

### Component 4: Gate Rejection Recording

**Responsibility:** Save gate-rejected experiments to memory with partial results for learning.

**Important distinction:**

- **Infrastructure errors** (TrainingDataError, etc.) → Operation fails, NO memory record. Fix the bug.
- **Gate rejections** (valid training but poor results) → Route to AssessmentWorker, record to memory for learning.

**Location:** `ktrdr/agents/memory.py`, `ktrdr/agents/workers/assessment_worker.py`, `ktrdr/agents/workers/research_worker.py`

**Current State:**

Experiments are saved via `save_experiment()` in assessment_worker. Currently only called after successful backtest.

**Changes Required:**

1. **research_worker.py:** On gate rejection, transition to ASSESSING instead of FAILED
2. **assessment_worker.py:** Handle partial results (backtest_result=None for training gate rejection)
3. **ExperimentRecord:** Add status field for gate rejections

```python
# memory.py

@dataclass
class ExperimentRecord:
    id: str
    timestamp: datetime
    strategy_name: str
    context: ExperimentContext
    training_result: TrainingMetrics  # Always present for recorded experiments
    backtest_result: BacktestMetrics | None  # None if gate rejected after training
    assessment: Assessment | None
    source: str

    # NEW fields
    status: str = "completed"  # "completed", "gate_rejected_training", "gate_rejected_backtest"
    gate_rejection_reason: str | None = None  # e.g., "accuracy_too_low (8% < 10%)"
```

```python
# assessment_worker.py

async def run(
    self,
    operation_id: str,
    training_result: dict,
    backtest_result: dict | None,  # None for training gate rejections
    gate_rejection_reason: str | None = None,
) -> dict:
    """Assess experiment and save to memory. Handles both successes and gate rejections."""
    # LLM analyzes results (including partial results)
    # Save experiment with appropriate status
```

**Dependencies:**

- research_worker.py state machine change (gate rejection → ASSESSING)
- assessment_worker.py signature change (optional backtest_result)

---

### Component 5: Fix Multi-Symbol Training Pipeline

**Responsibility:** Make multi-symbol training actually work — agent can train on EURUSD + GBPUSD + USDJPY and get valid results.

**Location:** `ktrdr/training/training_pipeline.py`

**Current State:**

`combine_multi_symbol_data()` exists but produces `X_test = None` for multi-symbol strategies, causing silent 0% accuracy.

**Root Cause (from investigation):**

Unknown — needs debugging. Likely candidates:

- Different date ranges across symbols causing empty intersection
- Feature alignment issues when combining DataFrames
- Train/test split failing on combined data

**Fix Approach:**

1. Add detailed logging at each step of `combine_multi_symbol_data()`
2. Validate data shapes before/after each transformation
3. Raise `TrainingDataError` with specific message when combination fails
4. Fix the actual bug once identified

**Done When:**

```bash
# Run research with multi-symbol brief
start_research(
    brief="Train on EURUSD, GBPUSD, USDJPY. Use RSI indicator.",
    model="haiku"
)
# Result: test_accuracy > 0, total_trades > 0
```

---

### Component 6: Fix Multi-Timeframe Training Pipeline

**Responsibility:** Make multi-timeframe training actually work — agent can use 1h + 5m data together and get valid results.

**Location:** `ktrdr/data/multi_timeframe_coordinator.py`

**Current State:**

`MultiTimeframeCoordinator.load_multi_timeframe_data()` exists but produces 0 trades in backtest for multi-TF strategies.

**Root Cause (from investigation):**

Unknown — needs debugging. Likely candidates:

- 5m/1h bar alignment issues (5m bars don't align to 1h boundaries)
- Feature name collisions between timeframes
- Incorrect indexing when combining timeframe data

**Fix Approach:**

1. Add detailed logging at each step of multi-TF data loading
2. Validate alignment between timeframes
3. Raise `TrainingDataError` with specific message when alignment fails
4. Fix the actual bug once identified

**Done When:**

```bash
# Run research with multi-timeframe brief
start_research(
    brief="Use both 1h and 5m timeframes for EURUSD. RSI on both.",
    model="haiku"
)
# Result: test_accuracy > 0, total_trades > 0
```

---

## Data Flow

### Happy Path: Successful Research Cycle

```
┌──────────────┐
│ start_research(brief="...", model="haiku")
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ DesignWorker │ ← brief injected into prompt
│ designs      │
│ strategy     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ TrainingWorker │
│ trains model   │
│ returns metrics│
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Gate Check   │ ← Baby mode thresholds
│ (passes)     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ BacktestWorker │
│ runs backtest  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ AssessmentWorker │
│ saves to memory  │ → memory/experiments/{id}.yaml
│ status=completed │
└──────────────────┘
```

### Failure Path: Infrastructure Error (No Memory Record)

Infrastructure errors (TrainingDataError, BacktestError, etc.) are bugs to fix, not experiments to learn from. They fail loudly but don't record to memory.

```
┌──────────────┐
│ TrainingWorker  │
│ X_test = None   │
│ raises          │
│ TrainingDataError│
└──────┬───────────┘
       │
       ▼
┌──────────────┐
│ Orchestrator    │
│ catches error   │
│ sets operation  │
│ status=FAILED   │
│ error_message=  │
│ "TrainingData..." │
└──────┬──────────┘
       │
       ▼
   (cycle ends, NO memory record)
   (fix the bug, retry)
```

### Failure Path: Gate Rejection (Records to Memory)

Gate rejections are valid experiments with poor results. They route to AssessmentWorker and record to memory for learning.

```
┌──────────────┐
│ TrainingWorker │
│ returns        │
│ accuracy=8%    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Gate Check   │
│ accuracy < 10%│
│ → REJECT     │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ AssessmentWorker │
│ receives partial │
│ results (no      │
│ backtest)        │
│ LLM analyzes why │
│ training failed  │
│ saves to memory  │ → memory/experiments/{id}.yaml
│ status=gate_     │
│ rejected_training│
└──────────────────┘
```

### State Machine (Complete)

```text
DESIGNING
  ├─[complete]─→ TRAINING
  └─[error]─→ FAILED (infra error, no memory record)

TRAINING
  ├─[complete, gate pass]─→ BACKTESTING
  ├─[complete, gate fail]─→ ASSESSING (partial, training results only)
  └─[error]─→ FAILED (infra error, no memory record)

BACKTESTING
  ├─[complete, gate pass]─→ ASSESSING (full results)
  ├─[complete, gate fail]─→ ASSESSING (full results, gate rejected)
  └─[error]─→ FAILED (infra error, no memory record)

ASSESSING
  ├─[complete]─→ COMPLETE (experiment in memory)
  └─[error]─→ FAILED (infra error, no memory record)
```

---

## API Contracts

### start_research()

```python
async def start_research(
    brief: str | None = None,
    model: str = "opus",  # or "haiku"
    bypass_gates: bool = False,  # Keep for debugging, don't use in prod
) -> ResearchResult:
    """
    Start an agent research cycle.

    Args:
        brief: Natural language guidance for the designer.
               Injected into the system prompt.
        model: LLM model to use ("opus" or "haiku").
        bypass_gates: Skip quality gates (debugging only).

    Returns:
        ResearchResult with experiment record or error.
    """
```

### ResearchResult

```python
@dataclass
class ResearchResult:
    status: str  # "completed", "failed", "gate_rejected"
    experiment: ExperimentRecord | None
    error: str | None
    duration_seconds: float
```

### GateConfig

```python
@dataclass
class GateConfig:
    min_accuracy: float = 0.10
    max_loss: float = 0.8
    min_loss_decrease: float = -0.5
    min_win_rate: float = 0.10
```

---

## State Management

### Gate Configuration

**Where:** `ktrdr/agents/gates.py`

**Shape:** Default `GateConfig` values set to Baby thresholds.

**Transitions:** None in v2.5. Future versions may add maturity-based progression.

### Experiment Status

**Where:** `memory/experiments/{id}.yaml`

**Shape:**

```yaml
status: "completed" | "gate_rejected_training" | "gate_rejected_backtest"
gate_rejection_reason: "accuracy_too_low (8% < 10%)" | null
training_result: {...}  # Always present
backtest_result: {...} | null  # Null for training gate rejections
```

**Note:** Infrastructure errors (TrainingDataError, etc.) do NOT create experiment records. They fail the operation visibly but don't pollute memory with non-experiments.

**Transitions (for recorded experiments only):**

- Training completes → gate rejects → `status=gate_rejected_training`
- Training + backtest complete → gate rejects → `status=gate_rejected_backtest`
- Full cycle succeeds → `status=completed`

---

## Error Handling

### Infrastructure Errors (TrainingDataError, BacktestError, etc.)

**When:** Any pipeline step fails due to a bug (no data, invalid results, alignment issues, etc.)

**Response:** Exception raised, operation status set to FAILED with error message. NO memory record.

**User experience:** Operation fails visibly with clear error. Fix the bug and retry. These are not "experiments" — they're infrastructure problems.

### Gate Rejection

**When:** Training or backtest metrics fail gate checks

**Response:** Route to AssessmentWorker with partial results, experiment saved as gate_rejected

**User experience:** Experiment recorded with rejection reason and LLM analysis, subsequent steps skipped

---

## Integration Points

### Memory System

- ExperimentRecord schema extended with status/error fields
- `save_experiment()` handles both successes and failures
- Failed experiments visible to future research cycles (learning from mistakes)

### Prompt System

- `get_strategy_designer_prompt()` gains `brief` parameter
- Brief becomes a template variable in the prompt
- Open decision: prompts in `.md` files vs Python code

### Worker System

- DesignWorker accepts `brief` parameter
- All workers raise specific exceptions on failures (TrainingDataError, BacktestError, etc.)
- AssessmentWorker handles failure recording for any step

---

## Verification Strategy

**The goal is not to verify individual components work in isolation. The goal is to verify the whole research cycle works end-to-end.**

### End-to-End Verification Tests

These are REAL tests that run the FULL pipeline — design → training → gates → backtest → assessment → memory. Not mocked. Uses Haiku for speed/cost.

#### E2E Test 1: Simple Single-Symbol Research

```bash
# Run a real research cycle with a simple config
start_research(
    brief="Design a simple RSI strategy for EURUSD 1h. Single indicator only.",
    model="haiku"
)
```

**Pass criteria:**

- `status == "completed"`
- `test_accuracy > 0` (not silent failure)
- `total_trades > 0` (backtest ran)
- Experiment saved to `memory/experiments/`

#### E2E Test 2: Multi-Symbol Research

```bash
# Run a real research cycle with multi-symbol config
start_research(
    brief="Train on EURUSD, GBPUSD, USDJPY. Use RSI indicator.",
    model="haiku"
)
```

**Pass criteria:**

- Same as above — proves multi-symbol pipeline works

#### E2E Test 3: Multi-Timeframe Research

```bash
# Run a real research cycle with multi-timeframe config
start_research(
    brief="Use both 1h and 5m timeframes for EURUSD.",
    model="haiku"
)
```

**Pass criteria:**

- Same as above — proves multi-timeframe pipeline works

#### E2E Test 4: Gate Rejection Recorded

Force a gate rejection and verify it's recorded:

**Pass criteria:**

- Training completes with very low accuracy (< 10%)
- Gate rejects, routes to assessment
- Experiment saved to `memory/experiments/` with `status=gate_rejected_training`
- `gate_rejection_reason` is set (e.g., "accuracy_too_low")
- Backtest did NOT run

#### E2E Test 5: Infrastructure Error Fails Loudly

Force an infrastructure error and verify it fails visibly:

**Pass criteria:**

- Trigger scenario that causes TrainingDataError (e.g., multi-symbol with bad config)
- Operation status = FAILED with clear error_message
- NO experiment saved to memory (infra errors don't record)
- Error visible in operation details

### Unit Tests (Supporting)

Unit tests verify individual components work correctly, but they don't prove the system works. They catch regressions.

- Gate thresholds match Baby config
- `TrainingDataError` raised when `X_test is None`
- `ExperimentRecord` serializes with error fields
- Brief parameter included in prompt

### Integration Tests (Supporting)

Integration tests verify components wire together, but they don't prove real research works.

- Training failure results in experiment with `status=failed`
- Gate rejection skips backtest
- Failed experiments loadable from memory

---

## Migration / Rollout

No database migrations required. Changes are:

1. **Additive code changes** — New parameters, new fields, new exceptions
2. **Backward compatible** — Old experiments without status field default to "completed"
3. **Configuration change** — Gates switch to Baby thresholds (can revert if needed)

**Implementation order (vertical milestones):**

See [implementation/OVERVIEW.md](implementation/OVERVIEW.md) for detailed task breakdowns.

1. **Fail loudly on infra errors** — Audit and convert silent failures to exceptions
   - E2E: Operation FAILED with clear error, no memory record

2. **Gate rejections → memory** — State machine change, assessment handles partial results
   - E2E: Gate reject triggers assessment, experiment saved with status=gate_rejected_training

3. **Baby gates + brief** — Update thresholds, add brief to prompts
   - E2E: Brief guides design, 30% accuracy passes Baby gates

4. **Fix multi-symbol pipeline** — Debug and fix data combination
   - E2E: Multi-symbol research completes with valid metrics

5. **Fix multi-timeframe pipeline** — Debug and fix alignment
   - E2E: Multi-TF research completes with valid metrics

6. **Combined multi-symbol + multi-timeframe** — Verify both work together
   - E2E: Combined research completes with valid metrics

**Each milestone verified by E2E test before moving to next.**

---

*Created: 2025-12-31*
*Validated: 2026-01-01*
*Status: Validated — ready for implementation planning*

## Validation Notes

Key decisions from design validation:

1. **Timeout removed** — Not needed; health check system handles stuck operations
2. **Infrastructure errors vs gate rejections** — Infra errors fail loudly but don't record to memory (they're bugs to fix). Gate rejections route to assessment and record for learning.
3. **State machine updated** — Gate rejection transitions to ASSESSING, not FAILED
4. **E2E tests** — Each milestone includes E2E verification, not just unit tests

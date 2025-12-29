---
design: ../DESIGN.md
architecture: ../SCENARIOS.md
---

# Milestone 3: Prompt Integration (Read Path)

**Branch:** `feature/v2-memory-m3`
**Builds on:** Milestone 1
**Goal:** Agent sees experiment history and hypotheses in design prompt

---

## E2E Test Scenario

**Purpose:** Verify memory is loaded and injected into design prompts
**Prerequisites:** M1 complete (experiments + hypotheses in memory/)

```bash
# 1. Ensure memory has content
ls memory/experiments/ | head -5
cat memory/hypotheses.yaml | head -20

# 2. Test prompt building with memory
uv run python -c "
from ktrdr.agents.memory import load_experiments, get_open_hypotheses
from ktrdr.agents.prompts import (
    PromptContext, TriggerReason, StrategyDesignerPromptBuilder
)

# Load memory
experiments = load_experiments(n=5)
hypotheses = get_open_hypotheses()
print(f'Loaded {len(experiments)} experiments, {len(hypotheses)} hypotheses')

# Build prompt with memory
ctx = PromptContext(
    trigger_reason=TriggerReason.START_NEW_CYCLE,
    operation_id='test_op',
    phase='designing',
    experiment_history=experiments,
    open_hypotheses=hypotheses,
)

builder = StrategyDesignerPromptBuilder()
prompts = builder.build(ctx)

# Verify memory sections in prompt
user_prompt = prompts['user']
assert '## Experiment History' in user_prompt, 'Missing experiment history section'
assert '## Open Hypotheses' in user_prompt, 'Missing hypotheses section'
assert 'exp_v15' in user_prompt, 'No experiments in prompt'

print('Prompt length:', len(user_prompt))
print('First 500 chars of user prompt:')
print(user_prompt[:500])
print('...')
print('OK')
"

# 3. Test design worker loads memory (integration)
# This would require mocking the invoker, covered in unit tests
```

**Success Criteria:**
- [ ] PromptContext has experiment_history and open_hypotheses fields
- [ ] PromptBuilder formats experiment history in readable format
- [ ] PromptBuilder formats hypotheses list
- [ ] Design worker loads memory before building prompt
- [ ] System prompt updated with memory usage instructions

---

## Task 3.1: Extend PromptContext

**File:** `ktrdr/agents/prompts.py` (MODIFY)
**Type:** CODING
**Estimated time:** 30 minutes

**Description:**
Add `experiment_history` and `open_hypotheses` fields to PromptContext dataclass.

**Implementation Notes:**
- Both fields are optional (None when memory not available)
- Type is `list[dict]` to match memory module output

**Code:**
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

    # Memory context (NEW)
    experiment_history: list[dict[str, Any]] | None = None
    open_hypotheses: list[dict[str, Any]] | None = None
```

**Tests:** `tests/unit/agents/test_prompts.py`
- [ ] `test_prompt_context_with_memory` — can create with memory fields
- [ ] `test_prompt_context_without_memory` — works without memory fields

**Acceptance Criteria:**
- [ ] New fields added to PromptContext
- [ ] Existing tests still pass
- [ ] New fields default to None

---

## Task 3.2: Add Experiment History Formatting

**File:** `ktrdr/agents/prompts.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1.5 hours

**Description:**
Add methods to StrategyDesignerPromptBuilder for formatting experiment history. The format should match the contract in SCENARIOS.md.

**Implementation Notes:**
- Format matches SCENARIOS.md example
- Show context, results, verdict, observations, hypotheses
- Limit observations to 3 per experiment (token efficiency)
- Handle missing fields gracefully

**Code sketch:**
```python
def _format_experiment_history(self, experiments: list[dict]) -> str:
    """Format experiments as contextual observations for reasoning."""
    if not experiments:
        return ""

    lines = ["## Experiment History\n", "### Recent Experiments\n"]

    for exp in experiments:
        lines.append(self._format_single_experiment(exp))

    return "\n".join(lines)


def _format_single_experiment(self, exp: dict) -> str:
    """Format one experiment with full context."""
    exp_id = exp.get("id", "unknown")
    timestamp = exp.get("timestamp", "")[:10]  # Just date
    ctx = exp.get("context", {})
    res = exp.get("results", {})
    assess = exp.get("assessment", {})

    # Build context string
    indicators = " + ".join(ctx.get("indicators", ["unknown"]))
    timeframe = ctx.get("timeframe", "?")
    symbol = ctx.get("symbol", "?")
    zigzag = ctx.get("zigzag_threshold", "?")
    context_str = f"{indicators} | {timeframe} | {symbol} | zigzag {zigzag}"

    # Build results string
    test_acc = res.get("test_accuracy", 0)
    if isinstance(test_acc, float) and test_acc < 1:
        test_acc = test_acc * 100
    test_str = f"{test_acc:.1f}%"

    lines = [
        f"**{exp_id}** ({timestamp})",
        f"- Context: {context_str}",
        f"- Results: {test_str} test",
        f"- Verdict: {assess.get('verdict', 'unknown')}",
    ]

    observations = assess.get("observations", [])
    if observations:
        lines.append("- Observations:")
        for obs in observations[:3]:
            lines.append(f"  - {obs}")

    return "\n".join(lines) + "\n"
```

**Tests:** `tests/unit/agents/test_prompts.py`
- [ ] `test_format_experiment_history_empty` — returns empty string
- [ ] `test_format_experiment_history_single` — formats one experiment
- [ ] `test_format_experiment_history_multiple` — formats multiple
- [ ] `test_format_experiment_missing_fields` — handles missing gracefully

**Acceptance Criteria:**
- [ ] Experiment history formatted as readable markdown
- [ ] Format matches SCENARIOS.md contract
- [ ] Handles missing fields without crashing
- [ ] Observations limited to 3 per experiment

---

## Task 3.3: Add Hypothesis Formatting and Integration

**File:** `ktrdr/agents/prompts.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Add hypothesis formatting and integrate both memory sections into the prompt building flow.

**Implementation Notes:**
- Only show untested hypotheses (already filtered by get_open_hypotheses)
- Include source experiment and rationale
- Add to `_format_new_cycle_context()` after recent strategies section

**Code sketch:**
```python
def _format_hypotheses(self, hypotheses: list[dict]) -> str:
    """Format open hypotheses for the agent to consider."""
    if not hypotheses:
        return ""

    lines = ["## Open Hypotheses\n"]
    lines.append("Consider testing one of these hypotheses:\n")

    for h in hypotheses:
        h_id = h.get("id", "?")
        text = h.get("text", "")
        source = h.get("source_experiment", "")
        rationale = h.get("rationale", "")

        lines.append(f"- **{h_id}**: {text}")
        if source:
            lines.append(f"  - Source: {source}")
        if rationale:
            lines.append(f"  - Rationale: {rationale}")

    return "\n".join(lines)


def _format_new_cycle_context(self, context: PromptContext) -> str:
    """Format context for starting a new design cycle."""
    sections = ["## Available Resources"]

    # ... existing sections (indicators, symbols, recent strategies) ...

    # Add memory sections (NEW)
    if context.experiment_history:
        sections.append(self._format_experiment_history(context.experiment_history))

    if context.open_hypotheses:
        sections.append(self._format_hypotheses(context.open_hypotheses))

    # ... existing task section ...

    return "\n\n".join(sections)
```

**Tests:** `tests/unit/agents/test_prompts.py`
- [ ] `test_format_hypotheses_empty` — returns empty string
- [ ] `test_format_hypotheses_multiple` — formats all hypotheses
- [ ] `test_new_cycle_includes_memory` — memory sections in final prompt
- [ ] `test_new_cycle_without_memory` — works when memory is None

**Acceptance Criteria:**
- [ ] Hypotheses formatted with ID, text, source, rationale
- [ ] Memory sections appear in new_cycle prompts
- [ ] Prompt works with or without memory (graceful)

---

## Task 3.4: Update Design Worker to Load Memory

**File:** `ktrdr/agents/workers/design_worker.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Modify the design worker to load experiments and hypotheses before building the prompt.

**Implementation Notes:**
- Import from ktrdr.agents.memory
- Load after existing context gathering (symbols, indicators, strategies)
- Pass to PromptContext
- Log memory loading for visibility
- Handle load failures gracefully (empty lists, warning log)

**Code sketch:**
```python
# At top of file
from ktrdr.agents.memory import load_experiments, get_open_hypotheses

# In run() method, after existing context gathering:
async def run(self, parent_operation_id: str, model: str | None = None) -> dict[str, Any]:
    # ... existing code ...

    # Task 8.1: Gather ALL context upfront
    available_symbols = self._get_available_symbols()
    available_indicators = await self._get_available_indicators()
    recent_strategies = await self._get_recent_strategies(limit=5)

    # NEW: Load memory
    experiment_history = self._load_experiment_history()
    open_hypotheses = self._load_open_hypotheses()

    logger.info(
        f"Context gathered: {len(available_symbols)} symbols, "
        f"{len(available_indicators)} indicators, "
        f"{len(recent_strategies)} recent strategies, "
        f"{len(experiment_history)} experiments, "  # NEW
        f"{len(open_hypotheses)} hypotheses"  # NEW
    )

    # Build prompt with ALL context embedded
    prompt_data = get_strategy_designer_prompt(
        trigger_reason=TriggerReason.START_NEW_CYCLE,
        operation_id=op.operation_id,
        phase="designing",
        available_symbols=available_symbols,
        available_indicators=available_indicators,
        recent_strategies=recent_strategies,
        experiment_history=experiment_history,  # NEW
        open_hypotheses=open_hypotheses,  # NEW
    )
    # ...


def _load_experiment_history(self, n: int = 15) -> list[dict]:
    """Load experiment history from memory."""
    try:
        experiments = load_experiments(n=n)
        logger.info(f"Loaded {len(experiments)} experiments from memory")
        return experiments
    except Exception as e:
        logger.warning(f"Failed to load experiments: {e}")
        return []


def _load_open_hypotheses(self) -> list[dict]:
    """Load open hypotheses from memory."""
    try:
        hypotheses = get_open_hypotheses()
        logger.info(f"Loaded {len(hypotheses)} open hypotheses")
        return hypotheses
    except Exception as e:
        logger.warning(f"Failed to load hypotheses: {e}")
        return []
```

**Tests:** `tests/unit/agents/test_design_worker.py`
- [ ] `test_design_worker_loads_memory` — memory functions called
- [ ] `test_design_worker_memory_failure` — continues with empty lists on failure
- [ ] `test_design_worker_prompt_includes_memory` — memory in built prompt

**Smoke Test:**
```bash
# Check logs when running design
docker compose logs backend 2>&1 | grep -i "experiments from memory"
```

**Acceptance Criteria:**
- [ ] Design worker loads experiments before prompting
- [ ] Design worker loads hypotheses before prompting
- [ ] Memory passed to prompt builder
- [ ] Graceful handling of load failures
- [ ] Logging shows memory loading

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest tests/unit/agents/test_prompts.py -v`
- [ ] Design worker tests pass
- [ ] E2E test passes (prompt contains memory sections)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions in design flow
- [ ] Prompt includes experiment history when memory exists
- [ ] Prompt includes hypotheses when memory exists

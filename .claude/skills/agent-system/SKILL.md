---
name: agent-system
description: Use when working on autonomous research agents, agent prompts, tool execution, assessment parsing, quality gates, experiment memory, hypothesis tracking, budget tracking, agent workers (design, assessment, research), multi-research coordination, or agent API endpoints.
---

# Agent System

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL agent-system loaded!`

Load this skill when working on:

- Agent orchestration (research cycles, phase transitions)
- Agent prompts (design, assessment, context formatting)
- Tool definitions and executor (strategy save, validation)
- Quality gates (training gate, backtest gate)
- Experiment memory and hypothesis tracking
- Budget tracking and cost control
- Agent API endpoints or CLI commands
- Assessment parsing (structured + fallback)
- Agent workers (design, assessment, research, stubs)
- Agent metrics (Prometheus)

---

## End-to-End Research Cycle

```
User/API: POST /agent/trigger {model, brief}
    │
    ▼
AgentService (creates AGENT_RESEARCH operation)
    │
    ▼
AgentResearchWorker (polling loop orchestrator)
    │
    ├─ Phase 1: DESIGNING
    │   └─ AgentDesignWorker → Claude designs strategy → saves YAML
    │
    ├─ Gate: Training quality check (zero-cost, deterministic)
    │
    ├─ Phase 2: TRAINING
    │   └─ TrainingService → dispatches to GPU/CPU worker
    │
    ├─ Gate: Backtest quality check (zero-cost, deterministic)
    │
    ├─ Phase 3: BACKTESTING
    │   └─ BacktestingService → dispatches to backtest worker
    │
    └─ Phase 4: ASSESSING
        └─ AgentAssessmentWorker → Claude evaluates results
            ├─ Saves ExperimentRecord to memory
            └─ Updates hypothesis status
```

### The Polling Loop Pattern

The orchestrator does **not** directly await child workers. It runs a polling loop:

```python
while active_operations:
    for op in get_active_research_operations():
        advance_research(op)  # Non-blocking, advances one phase
    await asyncio.sleep(poll_interval)  # Default 5s
```

Why polling (not direct await):
- Training/backtest run on **distributed workers** (different containers/hosts)
- Per-research error isolation (one failure doesn't crash others)
- Multiple concurrent researches (each advances independently)
- Cancellation-responsive (short sleep intervals)

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/agents/invoker.py` | AnthropicAgentInvoker — Claude API agentic loop |
| `ktrdr/agents/executor.py` | ToolExecutor — routes and executes tool calls |
| `ktrdr/agents/tools.py` | Tool schema definitions (AGENT_TOOLS, DESIGN_PHASE_TOOLS) |
| `ktrdr/agents/prompts.py` | Prompt builders (design + assessment contexts) |
| `ktrdr/agents/gates.py` | Quality gates (training + backtest) |
| `ktrdr/agents/memory.py` | ExperimentRecord, Hypothesis persistence |
| `ktrdr/agents/assessment_parser.py` | Parse Claude's assessment output |
| `ktrdr/agents/budget.py` | Daily spending limits and tracking |
| `ktrdr/agents/metrics.py` | Prometheus metrics (cycles, phases, tokens, gates) |
| `ktrdr/agents/strategy_utils.py` | Strategy file management + V3 validation |
| `ktrdr/agents/checkpoint_builder.py` | Agent checkpoint state for resume |
| `ktrdr/agents/workers/research_worker.py` | AgentResearchWorker orchestrator |
| `ktrdr/agents/workers/design_worker.py` | AgentDesignWorker (Claude designs strategies) |
| `ktrdr/agents/workers/assessment_worker.py` | AgentAssessmentWorker (Claude evaluates) |
| `ktrdr/agents/workers/stubs.py` | Stub workers for E2E testing |
| `ktrdr/api/endpoints/agent.py` | REST endpoints (trigger, status, cancel, budget) |
| `ktrdr/api/services/agent_service.py` | AgentService (manages lifecycle) |
| `ktrdr/api/models/agent.py` | Pydantic request/response models |

---

## AnthropicAgentInvoker

**Location:** `ktrdr/agents/invoker.py`

Direct Anthropic API integration implementing the agentic tool-use loop.

```python
invoker = AnthropicAgentInvoker(
    executor=tool_executor,
    config=AnthropicInvokerConfig(
        model="claude-opus-4-5-20251101",
        max_tokens=4096,
        timeout=300,          # 5 min per API call
        max_iterations=10,    # Safety: prevent infinite loops
        max_input_tokens=50000,  # Circuit breaker for context growth
    ),
    tools=DESIGN_PHASE_TOOLS,  # or AGENT_TOOLS
)
result: AgentResult = await invoker.run(system_prompt, user_prompt)
# result.success, result.output, result.input_tokens, result.output_tokens, result.error
```

### Loop mechanics

1. Send system + user prompt to Claude
2. If Claude returns `tool_use` blocks → execute each via ToolExecutor
3. Append tool results as `tool_result` blocks
4. Send back to Claude (new iteration)
5. Repeat until Claude returns `end_turn` (no more tool calls)
6. Return accumulated result with total token counts

### Safety features

- **Max iterations** (default 10): Prevents infinite tool-call loops
- **Input token circuit breaker** (default 50,000): Stops if conversation context grows too large
- **Timeout** (default 300s): Per-API-call timeout
- **Graceful error handling**: Returns `AgentResult(success=False, error=...)` on failures

### Model selection

```python
from ktrdr.agents.invoker import resolve_model, MODEL_ALIASES

# Aliases: "opus" → "claude-opus-4-5-20251101"
#          "sonnet" → "claude-sonnet-4-5-20250929"
#          "haiku" → "claude-haiku-4-5-20251001"
model_id = resolve_model("haiku")      # From alias
model_id = resolve_model(None)         # From AGENT_MODEL env var or default (Opus)
```

---

## Tool System

### Tool Definitions (`tools.py`)

Two tool sets:

| Set | Tools | Used by |
|-----|-------|---------|
| `AGENT_TOOLS` (8 tools) | validate, save, get_indicators, get_symbols, get_strategies, start_training, start_backtest, save_assessment | Full cycle |
| `DESIGN_PHASE_TOOLS` (2 tools) | validate_strategy_config, save_strategy_config | Design phase only |

**Why two sets?** Cost optimization (Task 8.1). Design phase pre-populates indicators/symbols in the prompt, eliminating the need for `get_available_*` tool calls.

### ToolExecutor (`executor.py`)

Routes tool calls from Claude to handler methods:

```python
executor = ToolExecutor(api_url="http://localhost:8000/api/v1")
result = await executor.execute("save_strategy_config", {"name": "rsi_v1", "config": {...}})
```

Key handlers:
- `validate_strategy_config` → Pre-save validation
- `save_strategy_config` → Saves YAML, captures `last_saved_strategy_name/path`
- `get_available_indicators` → Fetches from API
- `get_available_symbols` → Fetches from API
- `get_recent_strategies` → Most recent N strategies
- `start_training` / `start_backtest` → Calls backend API
- `save_assessment` → Stores assessment JSON, captures `last_saved_assessment`

**State capture pattern:** After tool execution, check `executor.last_saved_strategy_name` and `executor.last_saved_strategy_path` (instance-level state, not persistent).

---

## Prompt System

**Location:** `ktrdr/agents/prompts.py` (~1000 lines)

### PromptContext

```python
@dataclass
class PromptContext:
    trigger_reason: str       # START_NEW_CYCLE, TRAINING_COMPLETED, BACKTEST_COMPLETED
    operation_id: str
    phase: str                # designing, training, backtesting, assessing
    indicators: list          # Pre-fetched indicator metadata
    symbols: list             # Pre-fetched symbol metadata
    recent_strategies: list   # Previous strategies for context
    training_results: dict    # (assessment phase)
    backtest_results: dict    # (assessment phase)
    brief: str | None         # User-provided research brief
    memory: dict | None       # Experiment history + hypotheses
```

### Design Phase Prompt

`StrategyDesignerPromptBuilder` builds the prompt with:

1. System prompt (role, goals, V3 format instructions)
2. Available indicators in compact format: `RSI(period:14,source:close) - momentum`
3. Available symbols: `AAPL: 1m,5m,15m,1h,4h,1d (2020-01-01 to 2024-12-01)`
4. Recent strategies (what's been tried before)
5. Research brief (user's direction/hypothesis to test)
6. Memory context (past experiments, open hypotheses)

**Cost optimization:** Compact formatting saves ~50% tokens vs JSON. Indicators/symbols injected in prompt, not fetched via tools.

### Assessment Phase Prompt

Built with full training + backtest results. Guides Claude to produce:
- Verdict: `strong_signal`, `weak_signal`, `no_signal`, `overfit`
- Observations, hypotheses, limitations
- Hypothesis IDs (H_001, etc.) if testing specific hypotheses

---

## Quality Gates

**Location:** `ktrdr/agents/gates.py`

Zero-cost deterministic checks between phases. No LLM invocation.

### Training Gate

```python
passed, reason = check_training_gate(training_metrics)
# Thresholds (intentionally lax — "baby stage"):
#   min_accuracy: 10%  (only catch completely broken)
#   max_loss: 0.8
#   min_loss_decrease: -0.5  (allow regression while exploring)
```

### Backtest Gate

```python
passed, reason = check_backtest_gate(backtest_metrics)
# Thresholds:
#   min_win_rate: 10%
#   max_drawdown: 40%
#   min_sharpe: -0.5
```

### Gate Rejection

When a gate rejects:
- No assessment phase runs (saves tokens)
- ExperimentRecord saved with status `gate_rejected_training` or `gate_rejected_backtest`
- Rejection reason stored: e.g., `"accuracy_below_threshold (5% < 10%)"`
- Agent learns from rejections without full assessment cost

Gates can be bypassed via API: `POST /agent/trigger {"bypass_gates": true}`

---

## Memory System

**Location:** `ktrdr/agents/memory.py`

YAML-based persistence at `memory/` (repo root). Git-friendly. Graceful degradation if missing.

### ExperimentRecord

```python
@dataclass
class ExperimentRecord:
    id: str                    # exp_YYYYMMDD_HHMMSS_xxxxxxxx
    timestamp: str
    strategy_name: str
    context: dict              # indicators, params, composition, timeframe, symbol, etc.
    results: dict              # test_accuracy, val_accuracy, sharpe_ratio, win_rate, etc.
    assessment: dict           # verdict, observations, hypotheses, limitations
    source: str = "agent"      # "agent" | "v1.5_bootstrap"
    status: str = "completed"  # "completed" | "gate_rejected_training" | "gate_rejected_backtest"
    gate_rejection_reason: str | None = None
```

### Hypothesis

```python
@dataclass
class Hypothesis:
    id: str                    # H_001, H_002, etc.
    text: str                  # The hypothesis statement
    source_experiment: str     # Which experiment generated it
    rationale: str
    status: str = "untested"   # "untested" | "validated" | "refuted" | "inconclusive"
    tested_by: list[str]       # Experiment IDs that tested this
```

### Key Functions

```python
from ktrdr.agents.memory import (
    load_experiments,         # Load N most recent (default 15)
    save_experiment,          # Persist to memory/experiments/{id}.yaml
    get_all_hypotheses,       # Load all hypotheses
    get_open_hypotheses,      # Get untested hypotheses
    save_hypothesis,          # Add to registry
    update_hypothesis_status, # Track testing results
)
```

---

## Assessment Parsing

**Location:** `ktrdr/agents/assessment_parser.py`

### Two Paths

1. **Primary:** Claude calls `save_assessment` tool → structured data captured directly
2. **Fallback:** Claude returns prose → `parse_assessment()` uses a separate Claude API call (Haiku) to semantically extract verdict/strengths/weaknesses/suggestions

### ParsedAssessment

```python
@dataclass
class ParsedAssessment:
    verdict: str               # strong_signal, weak_signal, no_signal, overfit
    observations: list[str]
    hypotheses: list[str]
    limitations: list[str]
    capability_requests: list[str]
    tested_hypothesis_ids: list[str]  # H_001, H_002 references
```

---

## Budget Tracking

**Location:** `ktrdr/agents/budget.py`

### BudgetTracker

```python
from ktrdr.agents.budget import get_budget_tracker

tracker = get_budget_tracker()
remaining = tracker.get_remaining()           # Dollars left today
can_proceed = tracker.can_spend(estimated)    # Check before operation
tracker.record_spend(amount, operation_id)    # Log transaction
status = tracker.get_status()                 # Full report
```

- Daily limit: `$5.00` (from `AGENT_DAILY_BUDGET`)
- Per-day JSON files: `data/budget/YYYY-MM-DD.json`
- Token-to-cost conversion uses `MODEL_PRICING` in `research_worker.py`

### Model Pricing (per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| Opus | $5.00 | $25.00 |
| Sonnet | $3.00 | $15.00 |
| Haiku | $1.00 | $5.00 |

---

## Workers

### AgentResearchWorker (`workers/research_worker.py`)

The orchestrator. Runs the polling loop advancing each active research through phases.

Key responsibilities:
- Phase transitions (designing → training → backtesting → assessing)
- Quality gate checks between phases
- Token counting and budget recording per phase
- Child operation tracking (`_child_tasks` dict keyed by operation_id)
- Error isolation (per-research, not global)
- Checkpoint saving on cancellation/failure (M7)

### AgentDesignWorker (`workers/design_worker.py`)

Uses Claude to design a strategy:
1. Creates child `AGENT_DESIGN` operation
2. Pre-populates prompt with indicators/symbols/memory
3. Runs AnthropicAgentInvoker with `DESIGN_PHASE_TOOLS`
4. Claude calls `save_strategy_config` tool
5. Captures strategy name/path from `executor.last_saved_strategy_name`
6. Returns design results with token counts

### AgentAssessmentWorker (`workers/assessment_worker.py`)

Uses Claude to evaluate training/backtest results:
1. Creates child `AGENT_ASSESSMENT` operation
2. Builds assessment prompt with full results context
3. Runs AnthropicAgentInvoker
4. Parses assessment (tool call or text fallback)
5. Saves ExperimentRecord to memory
6. Updates hypothesis status if testing specific hypotheses

### Stub Workers (`workers/stubs.py`)

For E2E testing without Claude API or real operations:
- `StubDesignWorker`: Returns mock strategy after delay
- `StubAssessmentWorker`: Returns mock assessment
- Enable: `USE_STUB_WORKERS=true`
- Fast mode: `STUB_WORKER_FAST=true` (0.5s per phase vs 30s default)
- Error injection: Include `"INJECT_FAILURE"` in brief to trigger `WorkerError`

---

## API & CLI

### Endpoints

```
POST   /agent/trigger              → Start research (202 or 409 if active)
GET    /agent/status               → Active researches, workers, budget, capacity
DELETE /agent/cancel/{operation_id} → Cancel specific research
GET    /agent/budget               → Budget status
```

### Trigger Request

```python
class AgentTriggerRequest(BaseModel):
    model: str | None = None      # "opus", "haiku", or full model ID
    brief: str | None = None      # Research direction / hypothesis
    strategy: str | None = None   # Pre-made strategy YAML (mutually exclusive with brief)
    bypass_gates: bool = False    # Skip quality gates (testing)
```

### CLI

```bash
ktrdr agent status                # Show active researches, budget, capacity
ktrdr agent status --json         # Machine-readable output
```

---

## Common Patterns

### Adding a New Tool

1. Add handler method in `ToolExecutor` (`executor.py`):
   ```python
   async def _handle_my_tool(self, param1: str, ...) -> dict:
       ...
   ```
2. Register in `_handler_methods` dict
3. Add JSON schema to `AGENT_TOOLS` in `tools.py`
4. Mention in system prompt if Claude should call it
5. Write test in `tests/unit/agent_tests/`

### Modifying Prompts

1. Edit `prompts.py` — find the trigger reason
2. Update `_format_new_cycle_context()` or `_format_backtest_completed_context()`
3. Remember: indicators/symbols are pre-populated in prompt (no tool calls needed)
4. Test with `test_prompts_brief.py` patterns

### Adding a New Quality Gate

1. Add config dataclass in `gates.py` (with `from_env()` classmethod)
2. Add check function: `check_xxx_gate(metrics) -> tuple[bool, str]`
3. Call from `AgentResearchWorker._advance_research()` at the appropriate phase transition
4. Add Prometheus metric via `record_gate_result()`

---

## Gotchas

### Polling loop is NOT a sequential state machine

The `AgentResearchWorker` advances each operation one step per poll iteration. Multiple researches advance independently. If you modify orchestrator logic, be careful about:
- Thread safety for `_child_tasks` dict
- Cancellation responsiveness (sleep in short intervals)
- State stored in `operation.metadata.parameters` (survives worker restarts)

### Tool executor state is ephemeral

`executor.last_saved_strategy_name/path` and `executor.last_saved_assessment` are instance-level. They reset if the executor is recreated. Read them immediately after tool execution.

### Token counts are cumulative

`AgentResult.input_tokens` and `output_tokens` are **totals** across the entire agentic loop (all iterations), not per-iteration counts. If `max_iterations` is hit, costs may be higher than expected.

### Gate rejections skip assessment

When a gate rejects, the assessment phase is never invoked. The experiment is recorded with status `gate_rejected_*` and a reason. Don't expect assessment data for gate-rejected experiments.

### Design phase uses restricted tools

`DESIGN_PHASE_TOOLS` only has `validate_strategy_config` and `save_strategy_config`. The `get_available_*` tools are excluded because that data is pre-populated in the prompt. Don't add discovery tools to the design phase without updating the prompt to remove pre-populated data.

### Model aliases are lowercase

API requests must use lowercase: `"haiku"`, not `"Haiku"`. Full model IDs are case-sensitive.

### Memory is enhancement, not requirement

The memory system degrades gracefully — empty lists if files are missing. Don't add hard dependencies on memory files existing. The agent should work (less effectively) without any memory.

### Stubs are for testing only

`USE_STUB_WORKERS=true` replaces real Claude/training/backtest with mocks. Never enable in production. `INJECT_FAILURE` in the brief triggers intentional errors for testing error paths.

### Brief and strategy are mutually exclusive

`POST /agent/trigger` accepts either `brief` (research direction) or `strategy` (pre-made YAML), not both. The API validates this.

### Assessment parsing has two paths

Primary: Claude calls `save_assessment` tool (structured). Fallback: parse text response with a separate Claude API call. The fallback is slower and less reliable. System prompts should guide Claude to use the tool.

---

## Environment Variables

```bash
# Model
AGENT_MODEL=claude-opus-4-5-20251101  # Default model
AGENT_MAX_TOKENS=4096                  # Max response tokens
AGENT_TIMEOUT_SECONDS=300              # Per API call timeout
AGENT_MAX_ITERATIONS=10                # Max tool-call loop iterations
AGENT_MAX_INPUT_TOKENS=50000          # Circuit breaker

# Orchestration
AGENT_POLL_INTERVAL=5                 # Seconds between status polls
USE_STUB_WORKERS=false                # Use stubs for testing
STUB_WORKER_DELAY=30                  # Stub phase delay (seconds)
STUB_WORKER_FAST=false                # Fast stubs (0.5s per phase)

# Budget
AGENT_DAILY_BUDGET=5.0                # Daily spend limit ($)
AGENT_BUDGET_DIR=data/budget          # Budget file location

# Gates
TRAINING_GATE_MIN_ACCURACY=0.10
TRAINING_GATE_MAX_LOSS=0.8
TRAINING_GATE_MIN_LOSS_DECREASE=-0.5
BACKTEST_GATE_MIN_WIN_RATE=0.10
BACKTEST_GATE_MAX_DRAWDOWN=0.40
BACKTEST_GATE_MIN_SHARPE=-0.5
```

---

## Metrics (Prometheus)

| Metric | Type | Labels |
|--------|------|--------|
| `agent_cycles_total` | Counter | outcome (completed/failed/cancelled) |
| `agent_cycle_duration_seconds` | Histogram | — |
| `agent_phase_duration_seconds` | Histogram | phase (designing/training/backtesting/assessing) |
| `agent_gate_results_total` | Counter | gate, result (pass/fail) |
| `agent_tokens_total` | Counter | phase (design/assessment) |
| `agent_budget_spend_total` | Counter | — |

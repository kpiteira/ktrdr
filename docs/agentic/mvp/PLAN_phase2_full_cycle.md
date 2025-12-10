# Phase 2: Full Research Cycle

**Objective:** Complete the design → train → backtest → assess loop

**Duration:** 3-4 days

**Prerequisites:** Phase 1 complete (strategy design works, agent-host-service operational)

---

## ⚠️ Architectural Context (from Phase 1)

**Phase 1 established the following architecture that Phase 2 builds upon:**

```
┌──────────┐     ┌─────────────────┐     ┌───────────────────────┐
│   CLI    │────▶│  Backend API    │────▶│  Agent Host Service   │
│          │     │  (Docker:8000)  │     │  (Native:5005)        │
└──────────┘     └─────────────────┘     │                       │
                         │               │  • TriggerService     │
                         │               │  • ClaudeCodeInvoker  │
                         │               │  • MCP Access         │
                         │               └───────────────────────┘
                         │                          │
                         │ Operation status         │ Claude invocation
                         │ notifications            │
                         ▼                          ▼
                 ┌───────────────┐        ┌─────────────────┐
                 │  PostgreSQL   │        │  Claude Code    │
                 │  + KTRDR Ops  │        │  + MCP Tools    │
                 └───────────────┘        └─────────────────┘
```

**Key Points:**
- **TriggerService runs in agent-host-service**, not in backend
- **CLI calls Backend API**, which proxies to agent-host-service
- **Operation status** (training/backtest) is tracked in backend, host service polls for updates
- All MCP tool calls happen from agent-host-service (where Claude runs)

---

## Branch Strategy

**Branch:** `feature/agent-mvp`

Continue on the same branch from Phase 1. All MVP phases (0-3) use this single branch.

---

## ⚠️ Implementation Principles

**Check Before Creating:**
For ANY functionality that might already exist in KTRDR:
1. **Search** the codebase for existing implementations
2. **Review** if existing code covers requirements
3. **Enhance** existing code if gaps found
4. **Create new** only if nothing suitable exists

**Known Existing Systems to Check:**
- `mcp/src/tools/` - MCP tools for training, backtest, operations
- `ktrdr/training/` - training pipeline
- `ktrdr/backtesting/` - backtest engine
- KTRDR API endpoints for async operations

---

## Success Criteria

- [ ] Agent designs strategy, triggers training, waits for completion
- [ ] Training quality gate evaluates results
- [ ] Passing strategies proceed to backtest
- [ ] Backtest quality gate evaluates results
- [ ] Agent assesses final results and writes explanation
- [ ] Full cycle completes autonomously

---

## Tasks

### 2.1 start_training MCP Tool (Check-First)

**⚠️ CHECK FIRST:** Training tools likely exist in `mcp/src/tools/`

**Step 1: Search existing MCP tools**
```bash
grep -r "start_training\|training" mcp/src/tools/
ls mcp/src/tools/
```

**Step 2: If exists, verify it supports:**
- Starting training with strategy name
- Symbol and timeframe selection
- Date range specification
- Returns operation_id for tracking
- Async operation (non-blocking)

**Step 3: Action**
- If exists and complete: Document location, move on
- If exists but incomplete: Enhance existing tool
- If missing: Create in `mcp/src/tools/training_tools.py`

**Required interface:**
```python
def start_training(
    strategy_name: str,
    symbols: list[str],
    timeframes: list[str],
    start_date: str,
    end_date: str,
    config_overrides: dict | None = None
) -> dict:  # Returns {operation_id, status}
```

**Acceptance:**
- Tool starts training via KTRDR API
- Returns operation_id for tracking
- Handles errors gracefully

**Effort:** 0-3 hours (depends on what exists)

---

### 2.2 start_backtest MCP Tool (Check-First)

**⚠️ CHECK FIRST:** Backtest tools likely exist in `mcp/src/tools/`

**Step 1: Search existing MCP tools**
```bash
grep -r "start_backtest\|backtest" mcp/src/tools/
ls mcp/src/tools/
```

**Step 2: If exists, verify it supports:**
- Starting backtest with strategy name
- Model path specification
- Symbol and timeframe selection
- Date range for backtest period
- Initial capital setting
- Returns operation_id for tracking

**Step 3: Action**
- If exists and complete: Document location, move on
- If exists but incomplete: Enhance existing tool
- If missing: Create in `mcp/src/tools/backtest_tools.py`

**Required interface:**
```python
def start_backtest(
    strategy_name: str,
    model_path: str,
    symbols: list[str],
    timeframes: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float = 100000
) -> dict:  # Returns {operation_id, status}
```

**Acceptance:**
- Tool starts backtest via KTRDR API
- Returns operation_id for tracking
- Handles errors gracefully

**Effort:** 0-4 hours (depends on what exists)

---

### 2.3 Implement Training Quality Gate

**Goal:** Deterministic check on training results

**Gate logic (from design doc):**
```python
def evaluate_training_gate(results: dict) -> tuple[bool, str]:
    """
    Returns (passed, reason)
    """
    if results['accuracy'] < TRAINING_MIN_ACCURACY:  # 0.45
        return False, f"Accuracy {results['accuracy']:.2%} below threshold"
    
    if results['final_loss'] > TRAINING_MAX_LOSS:  # 0.8
        return False, f"Final loss {results['final_loss']:.3f} above threshold"
    
    loss_reduction = 1 - (results['final_loss'] / results['initial_loss'])
    if loss_reduction < TRAINING_MIN_LOSS_REDUCTION:  # 0.2
        return False, f"Loss reduction {loss_reduction:.1%} below threshold"
    
    return True, "All thresholds passed"
```

**File:** `research_agents/gates/training_gate.py`

**Acceptance:**
- Gate evaluates training results
- Returns pass/fail with clear reason
- Thresholds configurable via environment

**Effort:** 2-3 hours

---

### 2.4 Implement Backtest Quality Gate

**Goal:** Deterministic check on backtest results

**Gate logic (from design doc):**
```python
def evaluate_backtest_gate(results: dict) -> tuple[bool, str]:
    """
    Returns (passed, reason)
    """
    if results['win_rate'] < BACKTEST_MIN_WIN_RATE:  # 0.45
        return False, f"Win rate {results['win_rate']:.1%} below threshold"
    
    if results['max_drawdown'] > BACKTEST_MAX_DRAWDOWN:  # 0.4
        return False, f"Max drawdown {results['max_drawdown']:.1%} above threshold"
    
    if results['sharpe_ratio'] < BACKTEST_MIN_SHARPE:  # -0.5
        return False, f"Sharpe {results['sharpe_ratio']:.2f} below threshold"
    
    return True, "All thresholds passed"
```

**File:** `research_agents/gates/backtest_gate.py`

**Acceptance:**
- Gate evaluates backtest results
- Returns pass/fail with clear reason
- Thresholds configurable via environment

**Effort:** 2-3 hours

---

### 2.5 Update Trigger Service for Full State Machine

**Goal:** Handle all state transitions and gate evaluations

**⚠️ Architecture Note:** TriggerService runs in `agent-host-service` (Phase 1 Task 1.10). It needs to poll the backend API for operation status since training/backtest operations run in KTRDR backend.

**Full state machine:**

```
IDLE
  ↓ (trigger: start_new_cycle)
DESIGNING
  ↓ (agent completes design)
TRAINING
  ↓ (training completes)
[Training Gate]
  ↓ pass                    ↓ fail
BACKTESTING              IDLE (outcome: failed_training_gate)
  ↓ (backtest completes)
[Backtest Gate]
  ↓ pass                    ↓ fail
ASSESSING                IDLE (outcome: failed_backtest_gate)
  ↓ (agent completes assessment)
IDLE (outcome: success)
```

**Operation Status Polling:**

The host service polls backend API for operation status:

```python
# In agent-host-service, poll for operation completion
async def check_operation_status(operation_id: str) -> dict:
    """Poll backend API for operation status."""
    response = await http_client.get(
        f"http://localhost:8000/api/v1/operations/{operation_id}"
    )
    return response.json()
```

**Trigger events:**

- `start_new_cycle`: No active session
- `training_completed`: Training operation finished (detected via polling)
- `training_failed`: Training operation errored
- `backtest_completed`: Backtest operation finished (detected via polling)
- `backtest_failed`: Backtest operation errored

**File:** `agent-host-service/trigger_service.py` (extends from `research_agents/services/trigger.py`)

**Acceptance:**

- All state transitions work
- Gates evaluated at correct points
- Correct outcomes recorded
- Host service polls backend for operation status

**Effort:** 4-5 hours

---

### 2.6 Update Agent Prompt for Full Cycle

**Goal:** Agent handles all phases appropriately

**Phase-specific behavior:**

**DESIGNING phase:**
- Design novel strategy
- Save configuration
- Start training
- Update state to TRAINING

**Post-training (TRAINING → gate passed):**
- Review training results
- Start backtest
- Update state to BACKTESTING

**Post-backtest (ASSESSING phase):**
- Analyze full results
- Write assessment explanation
- Record final outcome
- Update state to complete

**File:** `research_agents/prompts/strategy_designer.py`

**Acceptance:**
- Agent behaves correctly in each phase
- Transitions happen smoothly
- Assessment provides useful insights

**Effort:** 3-4 hours

---

### 2.7 Implement Assessment Storage

**Goal:** Store agent's assessment of results

**Add to agent_sessions:**
```sql
assessment_text TEXT,          -- Agent's written analysis
assessment_metrics JSONB       -- Structured metrics summary
```

**Assessment includes:**
- What worked / didn't work
- Hypothesis validation
- Suggestions for future experiments
- Key metrics summary

**File:** `research_agents/database/schema.py` (modify)

**Acceptance:**
- Assessment stored with session
- Queryable for learning (future phases)

**Effort:** 1-2 hours

---

### 2.8 Implement Checkpoint Recovery

**Goal:** Resume interrupted operations

**Logic in trigger service:**
```python
async def check_for_resumable_operations(session):
    """Check if operation can be resumed from checkpoint"""
    if session.phase == 'TRAINING' and session.operation_id:
        status = await get_operation_status(session.operation_id)
        if status.has_checkpoint and status.state == 'interrupted':
            # Resume training
            await resume_operation(session.operation_id)
            return True
    return False
```

**File:** `research_agents/services/recovery.py`

**Acceptance:**
- Interrupted training can resume
- Interrupted backtest can resume
- Failed operations (no checkpoint) fail cleanly

**Effort:** 2-3 hours

---

### 2.9 Full Cycle Integration Tests

**Goal:** Verify complete cycle works

**Test scenarios:**
1. Happy path: design → train (pass) → backtest (pass) → assess
2. Training gate failure: design → train (fail gate) → end
3. Backtest gate failure: design → train (pass) → backtest (fail gate) → end
4. Training error: design → train (error) → end
5. Checkpoint recovery: interrupt training → resume → complete

**File:** `tests/integration/agent_tests/test_full_cycle.py`

**Note:** Test directory is `agent_tests/` not `research_agents/` (see Phase 1 handoff for naming convention).

**Acceptance:**

- All scenarios pass
- State transitions correct
- Outcomes recorded correctly

**Effort:** 4-5 hours

---

## Task Summary

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| 2.1 | start_training tool (check-first) | 0-3h | Phase 1 |
| 2.2 | start_backtest tool (check-first) | 0-4h | Phase 1 |
| 2.3 | Training quality gate | 2-3h | None |
| 2.4 | Backtest quality gate | 2-3h | None |
| 2.5 | Full state machine | 4-5h | 2.1-2.4 |
| 2.6 | Updated agent prompt | 3-4h | 2.5 |
| 2.7 | Assessment storage | 1-2h | 2.6 |
| 2.8 | Checkpoint recovery | 2-3h | 2.5 |
| 2.9 | Integration tests | 4-5h | All above |

**Total estimated effort:** 18-32 hours (3-4 days)

*Note: Effort varies based on what already exists. Tasks 2.1, 2.2 may require minimal work if MCP tools exist.*

---

## Out of Scope for Phase 2

- Cost tracking (Phase 3)
- Budget enforcement (Phase 3)
- Full observability (Phase 3)
- Grafana dashboard (Phase 3)

---

## Files to Create/Modify

```
research_agents/
├── database/
│   └── schema.py                   # 2.7 (modify - add assessment fields)
├── gates/
│   ├── __init__.py
│   ├── training_gate.py            # 2.3
│   └── backtest_gate.py            # 2.4
├── services/
│   ├── trigger.py                  # 2.5 (modify - full state machine)
│   └── recovery.py                 # 2.8
└── prompts/
    └── strategy_designer.py        # 2.6 (modify - full cycle)

mcp/
└── src/
    └── tools/
        ├── training_tools.py       # 2.1 (check if exists in mcp/src/tools/)
        └── backtest_tools.py       # 2.2 (likely new)

tests/
└── integration/
    └── research_agents/
        └── test_full_cycle.py      # 2.9
```

---

## Timing Expectations

A typical successful cycle:
- Design phase: 1-2 minutes (agent thinking + tool calls)
- Training phase: 10-30 minutes (depends on data/model)
- Backtest phase: 2-5 minutes
- Assessment phase: 1 minute

**Total cycle time: 15-40 minutes**

With ~25 cycles/day capacity, we should see:
- Cycles completing throughout the day
- Mix of successes and gate failures
- Accumulating data for analysis

---

## Definition of Done

Phase 2 is complete when:
1. Full cycle runs autonomously
2. Quality gates filter poor strategies
3. Assessment captures insights
4. Checkpoint recovery works
5. Integration tests pass

Then we move to Phase 3: Observability & Cost Control.

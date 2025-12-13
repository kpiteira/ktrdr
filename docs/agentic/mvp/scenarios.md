# Design Validation: Operations-Only Agent MVP

**Date:** 2025-12-13
**Validated By:** Karl + Claude
**Documents Validated:**
- [design.md](design.md)
- [ARCHITECTURE_operations_only.md](../ARCHITECTURE_operations_only.md)

---

## Executive Summary

This document captures the results of design validation for the autonomous research agent MVP. Through scenario tracing and discussion, we clarified the architecture and resolved several gaps in the original design documents.

**Key Outcome:** The design is sound, but the documentation needed significant clarification around the trigger-per-phase worker model.

---

## Architecture Clarification

### The Correct Mental Model

The original documentation was ambiguous about how the state machine operates. Through validation, we established:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT_RESEARCH WORKER                                 │
│                     (orchestrator - IS a worker)                            │
│                                                                             │
│  - Has its own operation_id, status, progress, cancellation                 │
│  - Runs state machine loop: sleep → check child status → advance → repeat   │
│  - Sleeps in 100ms intervals for cancellation responsiveness                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ spawns child workers
                                    │
        ┌───────────────┬───────────┴───────────┬───────────────┐
        ▼               ▼                       ▼               ▼
  ┌───────────┐   ┌───────────┐           ┌───────────┐   ┌───────────┐
  │  DESIGN   │   │ TRAINING  │           │ BACKTEST  │   │  ASSESS   │
  │  WORKER   │   │  WORKER   │           │  WORKER   │   │  WORKER   │
  │ (Claude)  │   │ (exists)  │           │ (exists)  │   │ (Claude)  │
  └───────────┘   └───────────┘           └───────────┘   └───────────┘
```

**Key Principles:**

1. **Every phase is a worker** — Design, Training, Backtest, Assessment all run as async operations
2. **The orchestrator is also a worker** — AGENT_RESEARCH is itself an operation that runs the state machine
3. **Trigger-per-phase model** — The orchestrator wakes periodically, checks current child status, advances if done
4. **100ms sleep intervals** — For responsive cancellation (not one big 5-minute sleep)

### State Machine

```
                         TRIGGER                    TRIGGER
                         no active op               Design worker COMPLETED
                            │                              │
                            ▼                              ▼
    ┌──────┐          ┌───────────┐               ┌──────────┐
    │ IDLE │─────────▶│ DESIGNING │──────────────▶│ TRAINING │
    └──────┘  Start   └───────────┘    Start      └──────────┘
        ▲     design        │          training         │
        │     worker        │                           │
        │                   │                           │
        │              TRIGGER                     TRIGGER
        │              Design worker               Training worker
        │              still RUNNING               still RUNNING
        │                   │                           │
        │                   └──────┐                    └──────┐
        │                          ▼                           ▼
        │                    (loop back)                 (loop back)
        │
        │                                          TRIGGER
        │                                          Training COMPLETED
        │                                          Gate PASS
        │                                               │
        │                                               ▼
        │                                        ┌─────────────┐
        │     TRIGGER                            │ BACKTESTING │
        │     Assess worker      ┌───────────┐   └─────────────┘
        │     COMPLETED          │ ASSESSING │          │
        │         │              └───────────┘          │
        │         │                    ▲                │
        │         │                    │           TRIGGER
        │         │               Start assess     Backtest COMPLETED
        │         │               worker           Gate PASS
        │         │                    │                │
        │         │                    └────────────────┘
        │         │
        └─────────┴──────────────────▶ (back to IDLE / COMPLETED)


    ANY STATE ───────▶ CANCELLED  (user cancels)
    ANY STATE ───────▶ FAILED     (worker error or gate failure)
```

---

## Validated Scenarios

### Scenario 1: Full Cycle Success

**Trigger:** User runs `ktrdr agent trigger`
**Expected Outcome:** Strategy designed, trained, backtested, assessed, operation COMPLETED

**Flow:**
1. Trigger creates AGENT_RESEARCH operation (phase=designing)
2. Orchestrator starts AGENT_DESIGN worker
3. Design worker calls Claude, saves strategy, completes
4. Orchestrator sees design COMPLETED, starts TRAINING worker
5. Training worker runs, completes
6. Orchestrator checks training gate → PASS, starts BACKTESTING worker
7. Backtest worker runs, completes
8. Orchestrator checks backtest gate → PASS, starts AGENT_ASSESSMENT worker
9. Assessment worker calls Claude, saves assessment, completes
10. Orchestrator completes AGENT_RESEARCH operation

**Status:** Validated ✅

### Scenario 2: Training Gate Failure

**Trigger:** Training completes but accuracy is 40% (below 45% threshold)
**Expected Outcome:** Operation marked FAILED with gate reason

**Flow:**
1. Design completes successfully
2. Training completes with accuracy=0.40
3. Orchestrator checks gate: 40% < 45% → FAIL
4. Orchestrator fails AGENT_RESEARCH with "Training gate failed: accuracy_below_threshold (40% < 45%)"
5. Next trigger sees no active operation (FAILED is terminal)

**Status:** Validated ✅

### Scenario 3: Cancellation Mid-Cycle

**Trigger:** User runs `ktrdr agent cancel <op_id>` while training
**Expected Outcome:** Both parent and child operations cancelled

**Flow:**
1. Cycle in TRAINING phase, training worker running
2. User cancels AGENT_RESEARCH operation
3. Orchestrator receives CancelledError
4. Orchestrator cancels current child (training_op_id from metadata)
5. Both operations marked CANCELLED

**Status:** Validated ✅

### Scenario 4: Trigger While Active

**Trigger:** User triggers when cycle already running
**Expected Outcome:** Returns rejection with existing operation ID

**Flow:**
1. AGENT_RESEARCH operation exists with status=RUNNING
2. User calls trigger
3. API returns: `{"triggered": false, "reason": "active_cycle_exists", "operation_id": "..."}`

**Status:** Validated ✅

### Scenario 5: Backend Restart

**Trigger:** Backend restarts while cycle is in TRAINING phase
**Expected Outcome:** Cycle lost (accepted trade-off for MVP)

**Flow:**
1. Cycle in TRAINING, training worker running on distributed worker
2. Backend restarts
3. OperationsService (in-memory) cleared
4. No operations exist after restart
5. Training worker completes but has nowhere to report
6. Next trigger starts fresh cycle

**Decision:** Accepted for MVP. Resilience/checkpointing is future work.

**Status:** Validated ✅ (accepted limitation)

---

## Key Decisions

### Decision 1: All Phases Are Workers

**Context:** Original design was ambiguous about whether Claude calls (design, assessment) were blocking within the trigger or async.

**Decision:** All phases run as async workers with their own operation IDs:
- `AGENT_DESIGN` — Claude call for strategy design
- `TRAINING` — Existing training worker
- `BACKTESTING` — Existing backtest worker
- `AGENT_ASSESSMENT` — Claude call for assessment

**Rationale:**
- Consistent patterns across all phases
- Each phase gets progress tracking, cancellation, observability for free
- State machine is simple (just polls child status, advances when done)

### Decision 2: Orchestrator Is a Worker

**Context:** How does the periodic "trigger" mechanism work?

**Decision:** The AGENT_RESEARCH operation itself is a worker that runs the state machine loop internally. It sleeps, wakes, checks state, advances, repeats.

**Rationale:**
- Gets operation_id, cancellation, progress tracking automatically
- No external scheduler needed
- Cancelling the orchestrator cleanly cancels the whole cycle

### Decision 3: 100ms Sleep Intervals

**Context:** How to make cancellation responsive?

**Decision:** Instead of `await asyncio.sleep(300)`, use many small sleeps:
```python
for _ in range(3000):  # 3000 * 100ms = 300 seconds
    await asyncio.sleep(0.1)  # CancelledError caught here
```

**Rationale:** Cancellation requests are handled within 100ms, not up to 5 minutes.

### Decision 4: Backend Restart = Lost Cycle

**Context:** What happens if backend restarts mid-cycle?

**Decision:** Accept that restart loses the current cycle. Workers become orphaned. No recovery mechanism for MVP.

**Rationale:**
- Consistent with "No Partial Recovery" in design doc
- Resilience/checkpointing is broader infrastructure work
- MVP goal is proving the loop works, not bulletproof reliability

### Decision 5: Failed Cycles Create New Operation

**Context:** Can users retry a failed cycle?

**Decision:** No retry of existing operation. User triggers again, creates new AGENT_RESEARCH operation.

**Rationale:** Failed operations are immutable. Simpler than retry logic.

### Decision 6: Child Cancellation via Metadata

**Context:** How to cancel child operations when parent is cancelled?

**Decision:** Parent operation metadata tracks child operation IDs:
```python
metadata = {
    "phase": "training",
    "design_op_id": "op_agent_design_...",
    "training_op_id": "op_training_...",
    ...
}
```

On cancel, orchestrator reads current child ID and cancels it.

**Rationale:** Simple, explicit tracking. No magic parent-child relationship needed in OperationsService.

---

## Interface Contracts

### Operation Types

```python
class OperationType(str, Enum):
    # Existing
    DATA_LOAD = "data_load"
    TRAINING = "training"
    BACKTESTING = "backtesting"

    # New for agent
    AGENT_RESEARCH = "agent_research"      # Orchestrator
    AGENT_DESIGN = "agent_design"          # Claude design
    AGENT_ASSESSMENT = "agent_assessment"  # Claude assessment
```

### AGENT_RESEARCH Metadata

```python
{
    "phase": "designing" | "training" | "backtesting" | "assessing",
    "design_op_id": "op_agent_design_...",
    "training_op_id": "op_training_...",
    "backtest_op_id": "op_backtesting_...",
    "assess_op_id": "op_agent_assessment_...",
    "strategy_name": "momentum_rsi_v3",
    "strategy_path": "/app/strategies/momentum_rsi_v3.yaml",
}
```

### AGENT_DESIGN Result

```python
{
    "success": True,
    "strategy_name": "momentum_rsi_v3",
    "strategy_path": "/app/strategies/momentum_rsi_v3.yaml",
    "input_tokens": 2500,
    "output_tokens": 1800,
}
```

### AGENT_ASSESSMENT Result

```python
{
    "success": True,
    "verdict": "promising" | "mediocre" | "poor",
    "strengths": ["Good risk management", ...],
    "weaknesses": ["Limited sample size", ...],
    "suggestions": ["Try with longer timeframe", ...],
    "assessment_path": "/app/strategies/momentum_rsi_v3/assessment.json",
    "input_tokens": 3000,
    "output_tokens": 1500,
}
```

### Quality Gates

**Training Gate:**
- Accuracy ≥ 45%
- Final loss ≤ 0.8
- Loss decreased by ≥ 20%

**Backtest Gate:**
- Win rate ≥ 45%
- Max drawdown ≤ 40%
- Sharpe ratio ≥ -0.5

---

## Implementation Milestones

| # | Milestone | Key Deliverable | E2E Test |
|---|-----------|-----------------|----------|
| 1 | Orchestrator Shell | State machine with stub children | Trigger → phases progress → completes (~30s) |
| 2 | Design Worker | Real Claude design | Strategy file created on disk |
| 3 | Training Integration | Real training + gate | Training runs, gate evaluated |
| 4 | Backtest Integration | Real backtest + gate | Backtest runs, gate evaluated |
| 5 | Assessment Worker | Real Claude assessment | Assessment file created |
| 6 | Cancellation & Errors | Robust error handling | Cancel mid-cycle works cleanly |
| 7 | Budget & Observability | Cost control, metrics | Budget enforced, traces in Jaeger |

---

## Documentation Updates Required

The following documents need updates to reflect the validated architecture:

1. **PLAN_phase0_state_machine.md** — Currently describes wrong model (single sequential task). Needs rewrite for worker-based orchestrator.

2. **design.md** — Should clarify:
   - The trigger-per-phase model
   - That all phases are workers
   - That the orchestrator itself is a worker

3. **ARCHITECTURE_operations_only.md** — Should add:
   - Diagram showing orchestrator + child workers
   - Explanation of 100ms sleep intervals
   - Child operation tracking in metadata

---

## Open Questions (Deferred)

1. **Assessment necessity** — Karl's diagram had "Assess?? (needed??)" — confirm assessment phase is wanted for MVP
2. **Auto-start** — Should cycles auto-start after completion, or always require manual trigger?
3. **History persistence** — How to persist completed cycle history across restarts?

---

*Validation complete. Ready for implementation.*

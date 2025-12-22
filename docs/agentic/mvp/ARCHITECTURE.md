# Agent Research System: Technical Architecture

**Status**: Validated
**Last Updated**: 2025-12-13
**Design Rationale**: See [DESIGN.md](DESIGN.md) for the "what" and "why"

---

## Operation Types

| Type | Purpose | Worker Class |
|------|---------|--------------|
| `AGENT_RESEARCH` | Orchestrator (state machine loop) | `AgentResearchWorker` |
| `AGENT_DESIGN` | Claude call for strategy design | `AgentDesignWorker` |
| `TRAINING` | Model training | Existing `TrainingWorker` |
| `BACKTESTING` | Backtest execution | Existing `BacktestWorker` |
| `AGENT_ASSESSMENT` | Claude call for assessment | `AgentAssessmentWorker` |

---

## Component Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer                                       │
│                                                                             │
│  POST /agent/trigger  →  Creates AGENT_RESEARCH operation, starts worker   │
│  GET /agent/status    →  Queries AGENT_RESEARCH operation status           │
│  DELETE /agent/cancel →  Cancels AGENT_RESEARCH operation                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AgentResearchWorker                                  │
│                     (runs as AGENT_RESEARCH operation)                      │
│                                                                             │
│  • Runs state machine loop with 5-minute sleep intervals                    │
│  • Spawns child workers (design, training, backtest, assess)                │
│  • Tracks child operation IDs in metadata                                   │
│  • Applies quality gates between phases                                     │
│  • Sleeps in 100ms chunks for cancellation responsiveness                   │
└─────────────────────────────────────────────────────────────────────────────┘
         │                    │                    │                    │
         ▼                    ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│AgentDesignWorker│  │ TrainingWorker  │  │ BacktestWorker  │  │AgentAssessWorker│
│                 │  │   (existing)    │  │   (existing)    │  │                 │
│ • Claude API    │  │ • Model train   │  │ • Run backtest  │  │ • Claude API    │
│ • Save strategy │  │ • Report prog   │  │ • Report prog   │  │ • Save assess   │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │                    │
         └────────────────────┴────────────────────┴────────────────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  OperationsService  │
                              └─────────────────────┘
```

---

## State Machine

### State Transitions

| Current Phase | Child Status | Gate | Action | Next Phase |
|---------------|--------------|------|--------|------------|
| (none) | - | - | Create op, start design worker | designing |
| designing | RUNNING | - | Sleep | designing |
| designing | COMPLETED | - | Start training worker | training |
| designing | FAILED | - | Fail parent | FAILED |
| training | RUNNING | - | Sleep | training |
| training | COMPLETED | PASS | Start backtest worker | backtesting |
| training | COMPLETED | FAIL | Fail parent | FAILED |
| training | FAILED | - | Fail parent | FAILED |
| backtesting | RUNNING | - | Sleep | backtesting |
| backtesting | COMPLETED | PASS | Start assess worker | assessing |
| backtesting | COMPLETED | FAIL | Fail parent | FAILED |
| backtesting | FAILED | - | Fail parent | FAILED |
| assessing | RUNNING | - | Sleep | assessing |
| assessing | COMPLETED | - | Complete parent | COMPLETED |
| assessing | FAILED | - | Fail parent | FAILED |

### State Diagram

```text
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
        │                   └───────┐                   └──────┐
        │                           ▼                          ▼
        │                     (loop back)                (loop back)
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
        │         │                    ▲           TRIGGER
        │         │               Start assess     Backtest COMPLETED
        │         │               worker           Gate PASS
        │         │                    │                │
        │         │                    └────────────────┘
        │         │
        └─────────┴──────────────────▶ (COMPLETED)


    ANY STATE ───────▶ CANCELLED  (user cancels parent)
    ANY STATE ───────▶ FAILED     (child error or gate failure)
```

---

## Orchestrator Implementation

### Main Loop

```python
class AgentResearchWorker:
    """Orchestrator worker for research cycles."""

    async def run(self, operation_id: str) -> dict:
        """Main worker loop - runs as AGENT_RESEARCH operation."""

        while True:
            op = await self.ops.get_operation(operation_id)
            phase = op.metadata.get("phase", "idle")

            # Get current child operation
            child_op_id = self._get_child_op_id(op, phase)
            child_op = await self.ops.get_operation(child_op_id) if child_op_id else None

            # State machine logic
            if phase == "idle" or child_op is None:
                await self._start_design_worker(operation_id)

            elif child_op.status == OperationStatus.RUNNING:
                await self._update_parent_progress(operation_id, phase, child_op)

            elif child_op.status == OperationStatus.COMPLETED:
                if not await self._check_gate_and_advance(operation_id, phase, child_op):
                    return {"success": False, "reason": "gate_failed"}

                if phase == "assessing":
                    return {"success": True, "strategy_name": op.metadata["strategy_name"]}

            elif child_op.status == OperationStatus.FAILED:
                raise WorkerError(f"Child operation failed: {child_op.error_message}")

            await self._cancellable_sleep(300)  # 5 minutes

    async def _cancellable_sleep(self, seconds: float, interval: float = 0.1):
        """Sleep in small intervals for cancellation responsiveness."""
        for _ in range(int(seconds / interval)):
            await asyncio.sleep(interval)
```

### Child Operation Tracking

```python
async def _start_design_worker(self, operation_id: str):
    """Start the design worker and track its ID."""

    design_op = await self.ops.create_operation(
        operation_type=OperationType.AGENT_DESIGN,
        metadata={"parent_operation_id": operation_id}
    )

    task = asyncio.create_task(self.design_worker.run(design_op.operation_id))
    await self.ops.start_operation(design_op.operation_id, task)

    await self.ops.update_metadata(operation_id, {
        "phase": "designing",
        "design_op_id": design_op.operation_id,
    })
```

### Cancellation Handling

```python
async def run(self, operation_id: str) -> dict:
    try:
        # ... main loop ...
    except asyncio.CancelledError:
        op = await self.ops.get_operation(operation_id)
        child_op_id = self._get_current_child_op_id(op)
        if child_op_id:
            await self.ops.cancel_operation(child_op_id, "Parent cancelled")
        raise
```

---

## Data Contracts

### AGENT_RESEARCH Metadata

```python
{
    "phase": "designing" | "training" | "backtesting" | "assessing",

    # Child operation IDs
    "design_op_id": "op_agent_design_...",
    "training_op_id": "op_training_...",
    "backtest_op_id": "op_backtesting_...",
    "assess_op_id": "op_agent_assessment_...",

    # Results (populated as phases complete)
    "strategy_name": "momentum_rsi_v3",
    "strategy_path": "/app/strategies/momentum_rsi_v3.yaml",
    "training_result": {"accuracy": 0.62, "final_loss": 0.35},
    "backtest_result": {"sharpe_ratio": 1.2, "win_rate": 0.54},
    "assessment_verdict": "promising",
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
    "strengths": ["Good risk management"],
    "weaknesses": ["Limited sample size"],
    "suggestions": ["Try with longer timeframe"],
    "assessment_path": "/app/strategies/momentum_rsi_v3/assessment.json",
    "input_tokens": 3000,
    "output_tokens": 1500,
}
```

---

## API Contracts

### POST /agent/trigger

**Success (202 Accepted)**:

```json
{
    "triggered": true,
    "operation_id": "op_agent_research_20251213_143052_abc123",
    "message": "Research cycle started"
}
```

**Conflict (409)** — cycle already running:

```json
{
    "triggered": false,
    "reason": "active_cycle_exists",
    "operation_id": "op_agent_research_..."
}
```

**Too Many Requests (429)** — budget exhausted:

```json
{
    "triggered": false,
    "reason": "budget_exhausted"
}
```

### GET /agent/status

**Active cycle**:

```json
{
    "status": "active",
    "operation_id": "op_agent_research_...",
    "phase": "training",
    "progress": {
        "percentage": 45,
        "current_step": "Training model (epoch 5/10)"
    },
    "strategy_name": "momentum_rsi_v3",
    "child_operation_id": "op_training_...",
    "started_at": "2025-12-13T10:30:00Z"
}
```

**Idle**:

```json
{
    "status": "idle",
    "last_cycle": {
        "operation_id": "op_agent_research_...",
        "outcome": "completed",
        "strategy_name": "momentum_rsi_v3",
        "completed_at": "2025-12-13T12:45:00Z"
    }
}
```

### DELETE /agent/cancel

```json
{
    "success": true,
    "operation_id": "op_agent_research_...",
    "child_cancelled": "op_training_..."
}
```

---

## Quality Gate Implementation

### Training Gate

```python
def check_training_gate(result: dict) -> tuple[bool, str]:
    """Returns (passed, reason)."""

    if result.get("accuracy", 0) < 0.45:
        return False, f"accuracy_below_threshold ({result['accuracy']:.1%} < 45%)"

    if result.get("final_loss", 1.0) > 0.8:
        return False, f"loss_too_high ({result['final_loss']:.3f} > 0.8)"

    initial = result.get("initial_loss", 0)
    final = result.get("final_loss", 0)
    if initial > 0:
        decrease = (initial - final) / initial
        if decrease < 0.2:
            return False, f"insufficient_loss_decrease ({decrease:.1%} < 20%)"

    return True, "passed"
```

### Backtest Gate

```python
def check_backtest_gate(result: dict) -> tuple[bool, str]:
    """Returns (passed, reason)."""

    if result.get("win_rate", 0) < 0.45:
        return False, f"win_rate_too_low ({result['win_rate']:.1%} < 45%)"

    if result.get("max_drawdown", 1.0) > 0.4:
        return False, f"drawdown_too_high ({result['max_drawdown']:.1%} > 40%)"

    if result.get("sharpe_ratio", -999) < -0.5:
        return False, f"sharpe_too_low ({result['sharpe_ratio']:.2f} < -0.5)"

    return True, "passed"
```

---

## Storage

### In-Memory (OperationsService)

- Parent operation (AGENT_RESEARCH) with phase and child IDs
- Child operations with their status/results
- **Lost on restart** — accepted trade-off for MVP

### Persistent Files

**Strategy files**: `strategies/{name}.yaml`

- Created by AGENT_DESIGN worker via `save_strategy_config` tool

**Assessment files**: `strategies/{name}/assessment.json`

- Created by AGENT_ASSESSMENT worker

---

## Observability

### Trace Structure

```text
AGENT_RESEARCH (parent span)
├── AGENT_DESIGN (child span)
│   └── anthropic.messages.create
├── TRAINING (child span)
│   └── training epochs...
├── BACKTESTING (child span)
│   └── backtest bars...
└── AGENT_ASSESSMENT (child span)
    └── anthropic.messages.create
```

### Prometheus Metrics

```text
agent_cycles_total{outcome="completed|failed|cancelled"}
agent_cycle_duration_seconds (histogram)
agent_phase_duration_seconds{phase="designing|training|backtesting|assessing"}
agent_gate_results_total{gate="training|backtest", result="pass|fail"}
agent_tokens_total{phase="design|assessment"}
```

---

## Error Handling

| Error | Behavior |
|-------|----------|
| Child worker fails | Parent marks FAILED with child error |
| Gate fails | Parent marks FAILED with gate reason |
| Anthropic API error | Child fails, parent fails |
| Cancellation | Parent cancels current child, both marked CANCELLED |
| Backend restart | All operations lost |

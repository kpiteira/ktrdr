# Agent Research System: Operations-Only Architecture

**Status**: PROPOSED
**Date**: 2025-12-12

---

## Overview

The agent research system uses **OperationsService** as the single source of truth for state management. Each research cycle is represented by one `AGENT_RESEARCH` operation. No separate session database.

---

## Core Concept: One Operation Per Cycle

A research cycle is a single operation that progresses through phases:

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT_RESEARCH Operation                      │
│                                                                  │
│  operation_id: "op_agent_research_20251212_143052_abc123"       │
│  type: AGENT_RESEARCH                                            │
│  status: PENDING → RUNNING → COMPLETED/FAILED/CANCELLED         │
│                                                                  │
│  metadata: {                                                     │
│    "phase": "designing" | "training" | "backtesting" | "done",  │
│    "strategy_name": "momentum_rsi_v3",                          │
│    "strategy_path": "/app/strategies/momentum_rsi_v3.yaml",     │
│    "training_result": { ... },                                  │
│    "backtest_result": { ... },                                  │
│    "assessment": { ... }                                        │
│  }                                                               │
│                                                                  │
│  progress: {                                                     │
│    "percentage": 45,                                             │
│    "current_step": "Training model on EURUSD",                  │
│    "phase_progress": {                                          │
│      "design": 100,                                              │
│      "training": 60,                                             │
│      "backtest": 0                                               │
│    }                                                             │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

**Key insight**: Phase is metadata on the operation. Operation status (RUNNING/COMPLETED/FAILED/CANCELLED) controls lifecycle.

---

## State Machine

```
                    ┌─────────┐
                    │  IDLE   │  (no operation exists)
                    └────┬────┘
                         │ trigger
                         ▼
              ┌──────────────────────┐
              │      DESIGNING       │
              │  (Claude designing)  │
              └──────────┬───────────┘
                         │ save_strategy_config
                         ▼
              ┌──────────────────────┐
              │      TRAINING        │
              │  (model training)    │
              └──────────┬───────────┘
                         │ training complete + gate pass
                         ▼
              ┌──────────────────────┐
              │     BACKTESTING      │
              │  (running backtest)  │
              └──────────┬───────────┘
                         │ backtest complete + gate pass
                         ▼
              ┌──────────────────────┐
              │      ASSESSING       │
              │  (Claude evaluates)  │
              └──────────┬───────────┘
                         │
           ┌─────────────┴─────────────┐
           ▼                           ▼
    ┌────────────┐              ┌────────────┐
    │ COMPLETED  │              │   FAILED   │
    │  (success) │              │  (reason)  │
    └────────────┘              └────────────┘
```

### Transitions

| From | To | Trigger |
|------|----|---------|
| IDLE | DESIGNING | `trigger()` called, operation created |
| DESIGNING | TRAINING | Strategy saved via `save_strategy_config` tool |
| TRAINING | BACKTESTING | Training completes AND passes quality gate |
| TRAINING | FAILED | Training fails OR gate fails |
| BACKTESTING | ASSESSING | Backtest completes AND passes quality gate |
| BACKTESTING | FAILED | Backtest fails OR gate fails |
| ASSESSING | COMPLETED | Assessment saved |
| Any | CANCELLED | `cancel_operation()` called |

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AgentService                            │
│                                                                 │
│  • Orchestrates research cycles                                 │
│  • Creates/queries AGENT_RESEARCH operations                    │
│  • Coordinates phases (design → train → backtest → assess)      │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│OperationsService│  │AnthropicInvoker │  │  ToolExecutor   │
│                 │  │                 │  │                 │
│ • State tracking│  │ • Claude API    │  │ • save_strategy │
│ • Progress      │  │ • Tool handling │  │ • start_training│
│ • Cancellation  │  │ • Token counting│  │ • start_backtest│
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Existing KTRDR Services                      │
│                                                                 │
│  TrainingManager          BacktestingService                    │
│  (distributed workers)    (distributed workers)                 │
└─────────────────────────────────────────────────────────────────┘
```

### AgentService

Orchestrates research cycles. Single entry point for agent operations.

```python
class AgentService:
    async def trigger() -> dict          # Start new cycle
    async def get_status() -> dict       # Current cycle status
    async def cancel(op_id) -> dict      # Cancel via OperationsService
```

### OperationsService (existing)

Battle-tested async operation tracking. Handles:
- Operation creation and status tracking
- Progress updates
- Cancellation via `CancelledError`
- Query by type/status

### AnthropicAgentInvoker (existing)

Calls Claude API for design and assessment phases:
- Agentic loop (tool calls → execution → response)
- Token counting
- Timeout handling

### ToolExecutor (existing)

Executes agent tools:
- `save_strategy_config` - Saves strategy YAML
- `get_available_indicators` - Lists indicators
- `get_available_symbols` - Lists symbols
- `start_training` - Kicks off training operation
- `start_backtest` - Kicks off backtest operation

---

## Data Flow

### Trigger Flow

```
CLI/API                AgentService           OperationsService
   │                        │                        │
   │─── trigger() ─────────▶│                        │
   │                        │── create_operation ───▶│
   │                        │◀── operation_id ───────│
   │                        │── start_operation ────▶│
   │◀── {operation_id} ─────│                        │
```

### Design Phase Flow

```
AgentService          AnthropicInvoker        ToolExecutor
    │                       │                      │
    │── run(prompt) ───────▶│                      │
    │                       │── save_strategy ────▶│
    │                       │◀── {path, name} ─────│
    │◀── AgentResult ───────│                      │
    │                       │                      │
    │── update_metadata ───▶OperationsService      │
```

### Training Phase Flow

```
AgentService          TrainingManager         OperationsService
    │                       │                      │
    │── start_training ────▶│                      │
    │◀── training_op_id ────│                      │
    │                       │                      │
    │── poll status ───────▶│                      │
    │◀── progress ──────────│                      │
    │                       │                      │
    │── update_metadata ──────────────────────────▶│
```

### Cancellation Flow

```
CLI/API              OperationsService         AgentService._run_cycle
   │                       │                        │
   │── cancel(op_id) ─────▶│                        │
   │                       │── task.cancel() ──────▶│
   │                       │                        │── CancelledError
   │                       │◀── raises ─────────────│
   │                       │── status=CANCELLED ────│
   │◀── {success} ─────────│                        │
```

---

## API Contracts

### POST /agent/trigger

Start a new research cycle.

**Response**:
```json
{
  "triggered": true,
  "operation_id": "op_agent_research_20251212_143052_abc123"
}
```

Or if cycle already running:
```json
{
  "triggered": false,
  "reason": "active_operation_exists",
  "operation_id": "op_agent_research_..."
}
```

### GET /agent/status

Get current cycle status.

**Response** (active):
```json
{
  "status": "active",
  "operation": {
    "id": "op_agent_research_...",
    "phase": "training",
    "progress": {"percentage": 45, "current_step": "Training..."},
    "strategy_name": "momentum_v3"
  }
}
```

**Response** (idle):
```json
{
  "status": "idle",
  "operation": null
}
```

### Standard Operations API

Cancellation and detailed status use existing operations endpoints:
- `DELETE /operations/{id}/cancel` - Cancel operation
- `GET /operations/{id}` - Full operation details

---

## Quality Gates

Gates are synchronous checks between phases. If a gate fails, the cycle fails.

### Training Gate

Checks before proceeding to backtest:
- Accuracy ≥ 45%
- Final loss ≤ 0.8
- Loss decreased by ≥ 20%

### Backtest Gate

Checks before proceeding to assessment:
- Win rate ≥ 45%
- Max drawdown ≤ 40%
- Sharpe ratio ≥ -0.5

---

## Storage

### Operation State (in-memory)

OperationsService stores:
- Operation status
- Phase (in metadata)
- Progress
- Results (in metadata)

Lost on restart. Cycles in progress fail and can be restarted.

### Strategy Files (persistent)

Saved to `strategies/{name}.yaml`:
- Strategy configuration
- Created by `save_strategy_config` tool

### Assessment Files (persistent)

Saved to `strategies/{name}/assessment.json`:
- Final assessment from Claude
- Backtest results summary

---

## Error Handling

| Error | Behavior |
|-------|----------|
| Anthropic timeout | Fail cycle with "anthropic_timeout" |
| Training fails | Fail cycle with training error |
| Backtest fails | Fail cycle with backtest error |
| Gate fails | Fail cycle with "gate_failed:{gate_name}" |
| Cancellation | Mark CANCELLED, clean shutdown |
| Unknown error | Fail cycle with error message |

All failures are logged. No automatic retry (manual re-trigger required).

---

## Observability

### Traces

Full cycle traced from trigger to completion:
- Span per phase (design, training, backtest, assess)
- Child spans for API calls
- Error details on failure

### Metrics

- `agent_cycles_total{outcome}` - Count by outcome
- `agent_cycle_duration_seconds` - Histogram
- `agent_phase_duration_seconds{phase}` - Per-phase timing
- `agent_tokens_total` - Token usage

---

## Open Questions

1. **History**: How to persist completed cycle history across restarts?
   - Option: Write summary to `strategies/{name}/history.json`

2. **Recent strategies**: How does agent discover what was tried before?
   - Option: Scan `strategies/` directory

3. **Budget**: Where to track daily spend?
   - Option: File-based counter, reset daily

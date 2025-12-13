# Agent MVP: Milestones

**Status**: Ready for Implementation Planning
**Validated**: See [scenarios.md](scenarios.md) for validation details
**Date**: 2025-12-13

---

## Overview

These milestones implement the autonomous research agent using the worker-based architecture. Each milestone is E2E-testable and builds on the previous.

**Key Architecture Principle**: Everything is a worker. The orchestrator (AGENT_RESEARCH) is a worker that spawns child workers (AGENT_DESIGN, TRAINING, BACKTESTING, AGENT_ASSESSMENT).

---

## Milestone 1: Orchestrator Shell

**Capability**: User can trigger a research cycle and see it progress through phases with stub workers

**Why M1**: Proves the orchestrator pattern works — state machine loop, child operation tracking, phase transitions — before adding real business logic.

**E2E Test**:

```bash
# Start cycle
ktrdr agent trigger
# Expected: "Research cycle started! Operation ID: op_agent_research_..."

# Watch progress (~30 seconds with stubs)
watch -n 2 "ktrdr agent status"
# Expected: Phase progresses: designing → training → backtesting → assessing → completed

# Verify completion
ktrdr operations list --type agent_research
# Expected: Operation shows COMPLETED status
```

**What's Built**:

- `AGENT_RESEARCH` operation type
- `AgentResearchWorker` with state machine loop (100ms sleep intervals)
- Stub child workers (instant complete, mock results)
- Child operation ID tracking in parent metadata
- `POST /agent/trigger` endpoint
- `GET /agent/status` endpoint
- `ktrdr agent trigger` / `ktrdr agent status` CLI

**Not Included**: Real Claude calls, real training/backtest, gates, budget, cancellation

---

## Milestone 2: Design Worker

**Capability**: Real Claude call designs a strategy and saves it to disk

**Builds On**: M1 (orchestrator now starts real design worker instead of stub)

**E2E Test**:

```bash
ktrdr agent trigger
# Wait for design phase to complete (~1-2 minutes)
ktrdr agent status
# Expected: Phase = training, strategy_name populated

# Verify strategy file
ls strategies/
# Expected: New strategy YAML file exists
cat strategies/<strategy_name>.yaml
# Expected: Valid strategy configuration
```

**What's Built**:

- `AGENT_DESIGN` operation type
- `AgentDesignWorker` class
- Claude API integration (AnthropicAgentInvoker)
- `save_strategy_config` tool execution
- Strategy file saved to `strategies/{name}.yaml`
- Token usage captured in result

---

## Milestone 3: Training Integration

**Capability**: Real training runs after design, with quality gate

**Builds On**: M2 (orchestrator now starts real training after design)

**E2E Test**:

```bash
ktrdr agent trigger
# Wait for training to complete (~5-10 minutes)
ktrdr agent status
# Expected: Phase = backtesting (if gate passed) or FAILED (if gate failed)

# Check training operation
ktrdr operations list --type training
# Expected: Training operation COMPLETED

# If gate failed:
ktrdr operations status <op_id>
# Expected: Error shows "Training gate failed: <reason>"
```

**What's Built**:

- Orchestrator starts real TRAINING operation
- Training status polling
- Training gate evaluation (accuracy, loss thresholds)
- Gate failure → cycle fails with clear error

---

## Milestone 4: Backtest Integration

**Capability**: Real backtest runs after training passes gate

**Builds On**: M3 (orchestrator now starts real backtest after training)

**E2E Test**:

```bash
ktrdr agent trigger
# Wait for full cycle through backtest (~15-20 minutes total)
ktrdr agent status
# Expected: Phase = assessing (if gate passed) or FAILED (if gate failed)

# Check backtest operation
ktrdr operations list --type backtesting
# Expected: Backtest operation COMPLETED
```

**What's Built**:

- Orchestrator starts real BACKTESTING operation
- Backtest status polling
- Backtest gate evaluation (win rate, drawdown, Sharpe thresholds)
- Gate failure → cycle fails with clear error

---

## Milestone 5: Assessment Worker

**Capability**: Real Claude assessment after backtest, saved to disk

**Builds On**: M4 (orchestrator now starts real assessment after backtest)

**E2E Test**:

```bash
ktrdr agent trigger
# Wait for full cycle completion (~20-30 minutes total)
ktrdr agent status
# Expected: status = idle (cycle completed)

# Verify assessment file
cat strategies/<strategy_name>/assessment.json
# Expected: JSON with verdict, strengths, weaknesses, suggestions

# Check full operation
ktrdr operations status <agent_research_op_id>
# Expected: COMPLETED with full result summary
```

**What's Built**:

- `AGENT_ASSESSMENT` operation type
- `AgentAssessmentWorker` class
- Assessment prompt with training/backtest results
- Assessment saved to `strategies/{name}/assessment.json`
- Full cycle now works end-to-end

---

## Milestone 6: Cancellation & Error Handling

**Capability**: User can cancel running cycles; errors are handled gracefully

**Builds On**: M5 (now adding robustness)

**E2E Test**:

```bash
# Test cancellation during training
ktrdr agent trigger
# Wait for training phase
ktrdr agent status  # Get operation ID
ktrdr agent cancel
# Expected: "Cancellation requested"

# Verify both operations cancelled
ktrdr operations status <agent_research_op_id>
# Expected: CANCELLED
ktrdr operations status <training_op_id>
# Expected: CANCELLED

# Test gate failure
# (Configure strategy to produce poor training results)
ktrdr agent trigger
# Expected: Cycle fails with clear gate error message
```

**What's Built**:

- `DELETE /agent/cancel` endpoint
- `ktrdr agent cancel` CLI command
- Parent cancellation → child cancellation
- Cancellation responsiveness (100ms)
- Clear error messages for all failure modes
- Proper cleanup on errors

---

## Milestone 7: Budget & Observability

**Capability**: Cost control and full visibility into cycle execution

**Builds On**: M6 (now adding production readiness)

**E2E Test**:

```bash
# Test budget enforcement
# Set budget to $0.01 in config
ktrdr agent trigger
# Expected: "budget_exhausted" error

# Reset budget, run cycle
ktrdr agent trigger
# Wait for completion

# Check traces
# Open Jaeger UI, search for operation ID
# Expected: Full trace with all child spans

# Check metrics
# Open Grafana dashboard
# Expected: agent_cycles_total incremented, phase durations recorded

# Check budget status
ktrdr agent budget
# Expected: Shows daily spend and remaining
```

**What's Built**:

- Budget tracking (file-based counter)
- Budget check in trigger
- `GET /agent/budget` endpoint
- `ktrdr agent budget` CLI command
- Prometheus metrics (cycles, durations, tokens, gates)
- OTEL tracing spans per phase
- Grafana dashboard

---

## Milestone Summary

| # | Milestone | Capability | Key Deliverable |
|---|-----------|------------|-----------------|
| 1 | Orchestrator Shell | Trigger cycle, see phases | State machine with stubs |
| 2 | Design Worker | Real Claude design | Strategy file on disk |
| 3 | Training Integration | Real training + gate | Training gate enforcement |
| 4 | Backtest Integration | Real backtest + gate | Backtest gate enforcement |
| 5 | Assessment Worker | Real Claude assessment | Assessment file on disk |
| 6 | Cancellation & Errors | Cancel, error handling | Robust error paths |
| 7 | Budget & Observability | Cost control, metrics | Production readiness |

---

## Dependencies

- **M1**: No dependencies (foundation)
- **M2**: Requires M1 + existing `AnthropicAgentInvoker`, `ToolExecutor`
- **M3**: Requires M2 + existing training infrastructure
- **M4**: Requires M3 + existing backtest infrastructure
- **M5**: Requires M4 + existing `AnthropicAgentInvoker`
- **M6**: Requires M5
- **M7**: Requires M6 + existing observability infrastructure

---

## Reference Documents

- [design.md](design.md) — What we're building and why
- [ARCHITECTURE_operations_only.md](../ARCHITECTURE_operations_only.md) — How it works technically
- [scenarios.md](scenarios.md) — Validated scenarios and key decisions

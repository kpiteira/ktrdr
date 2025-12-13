# Implementation Plan: Operations-Only Agent

**Based on**: [design.md](design.md) and [ARCHITECTURE_operations_only.md](../ARCHITECTURE_operations_only.md)
**Status**: Ready for implementation
**Date**: 2025-12-13
**Branch**: `feature/agent-mvp`

---

## Overview

This plan implements the autonomous research agent using **only OperationsService** for state management. No session database. Each phase builds on the previous one.

**Execution Order**:

1. **Cleanup** - Remove session database code, salvage working components
2. **Phase 0** - State machine with stubs (validate architecture)
3. **Phase 1** - Replace design stub with real Anthropic integration
4. **Phase 2** - Replace training stub with real training API
5. **Phase 3** - Replace backtest stub, add assessment phase
6. **Phase 4** - Add budget, observability, robustness

**Branch**: `feature/agent-mvp` (surgical cleanup, not restart)

---

## Step 0: Branch Cleanup

**Goal**: Remove session database code while preserving working components

**Detailed Plan**: [TASK_branch_cleanup.md](TASK_branch_cleanup.md)

### Summary of Cleanup

| Action | Files |
|--------|-------|
| **KEEP** | `ktrdr/agents/invoker.py`, `tools.py` |
| **MOVE** | Prompts, gates, strategy utils → `ktrdr/agents/` |
| **REWRITE** | `agent_service.py`, API endpoints, CLI |
| **DELETE** | `research_agents/` directory |

**Checkpoint**: No imports from `research_agents` remain

---

## Phase 0: State Machine (Stubs)

**Goal**: Validate architecture with stub implementations before adding real business logic

**Detailed Plan**: [PLAN_phase0_state_machine.md](PLAN_phase0_state_machine.md)

### Tasks

| Task | Description |
|------|-------------|
| 0.1 | Add `AGENT_RESEARCH` operation type |
| 0.2 | Create AgentService with state machine (stub phases) |
| 0.3 | Wire up API endpoints (trigger/status) |
| 0.4 | Wire up CLI commands (trigger/status/cancel) |
| 0.5 | Add `OperationsService.update_metadata()` if needed |

**Checkpoint**:

- [ ] Full stub cycle completes (~2 min): designing → training → backtesting → assessing → done
- [ ] Cancellation works at any phase (100ms granularity)
- [ ] Progress updates visible in CLI
- [ ] Gate failures mark cycle as FAILED

---

## Phase 1: Design Integration

**Goal**: Replace design stub with real Anthropic/Claude integration

**Detailed Plan**: [PLAN_phase1_foundation.md](PLAN_phase1_foundation.md)

### Phase 1 Tasks

| Task | Description |
|------|-------------|
| 1.1 | Replace `_run_design_phase()` stub with real AnthropicAgentInvoker |
| 1.2 | Capture strategy_name from tool_outputs |
| 1.3 | Update progress tracking for design phase |

**Checkpoint**:

- [ ] Real Claude invocation designs strategy
- [ ] Strategy saved to `strategies/{name}.yaml`
- [ ] Token usage captured in result
- [ ] Other phases still use stubs

---

## Phase 2: Training Integration

**Goal**: Replace training stub with real training API polling

**Detailed Plan**: [PLAN_phase2_training.md](PLAN_phase2_training.md)

### Phase 2 Tasks

| Task | Description |
|------|-------------|
| 2.1 | Create strategy loader to extract training params |
| 2.2 | Replace `_run_training_phase()` stub with real API polling |
| 2.3 | Use real training gate (moved from research_agents) |
| 2.4 | Wire training gate into cycle |

**Checkpoint**:

- [ ] Real training starts after design
- [ ] Progress updates during training
- [ ] Gate rejects poor training results
- [ ] Backtest/assessment phases still use stubs

---

## Phase 3: Full Cycle

**Goal**: Replace backtest stub and add assessment phase

**Detailed Plan**: [PLAN_phase3_full_cycle.md](PLAN_phase3_full_cycle.md)

### Phase 3 Tasks

| Task | Description |
|------|-------------|
| 3.1 | Replace `_run_backtest_phase()` stub with real API polling |
| 3.2 | Wire backtest gate into cycle |
| 3.3 | Replace `_run_assessment_phase()` stub with real Claude call |
| 3.4 | Add assessment prompt builder |
| 3.5 | Save assessment to `strategies/{name}/assessment.json` |
| 3.6 | Update `get_recent_strategies()` to include assessments |

**Checkpoint**:

- [ ] Full real cycle: design → train → backtest → assess → complete
- [ ] All gates functional
- [ ] Assessment saved to disk
- [ ] No stubs remain

---

## Phase 4: Polish

**Goal**: Add budget enforcement, observability, robust error handling

**Detailed Plan**: [PLAN_phase4_polish.md](PLAN_phase4_polish.md)

### Phase 4 Tasks

| Task | Description |
|------|-------------|
| 4.1 | Implement budget tracking (`ktrdr/agents/budget.py`) |
| 4.2 | Wire budget check into trigger |
| 4.3 | Add agent metrics (cycles, phase durations, tokens) |
| 4.4 | Wire metrics into AgentService |
| 4.5 | Add OTEL tracing spans |
| 4.6 | Improve error handling (timeouts, service unavailable) |
| 4.7 | Improve CLI status display |
| 4.8 | Add `/agent/budget` endpoint |

**Checkpoint**:

- [ ] Budget prevents overspending
- [ ] Cycles visible in Jaeger traces
- [ ] Metrics in Grafana
- [ ] Error cases handled gracefully

---

## Definition of Done

The MVP is complete when:

1. ✅ Full cycle works: trigger → design → train → backtest → assess → complete
2. ✅ Cancellation works cleanly at any phase
3. ✅ Budget enforcement prevents overspending
4. ✅ Cycles visible in operations list
5. ✅ Metrics in Grafana
6. ✅ Traces in Jaeger
7. ✅ No session database code remains
8. ✅ All tests pass

---

## Salvaged Components

These existing components are preserved during cleanup:

| Component | Location | Status |
|-----------|----------|--------|
| AnthropicAgentInvoker | `ktrdr/agents/invoker.py` | Keep unchanged |
| ToolExecutor | `ktrdr/agents/executor.py` | Update imports |
| AGENT_TOOLS | `ktrdr/agents/tools.py` | Keep unchanged |
| Prompt builder | → `ktrdr/agents/prompts.py` | Move from research_agents |
| Quality gates | → `ktrdr/agents/gates.py` | Move from research_agents |
| Strategy utils | → `ktrdr/agents/strategy_utils.py` | Move from research_agents |

---

## What We're NOT Doing (Deferred)

- Learning across cycles (agent memory)
- Multiple concurrent cycles
- Checkpoint recovery within cycles
- Auto-retry failed cycles
- Background triggering (manual only for MVP)

---

## Reference Documents

- [design.md](design.md) - High-level design (what/why)
- [ARCHITECTURE_operations_only.md](../ARCHITECTURE_operations_only.md) - Technical architecture (how)
- [TASK_branch_cleanup.md](TASK_branch_cleanup.md) - Cleanup surgery plan
- [archive/TASK_session_cancellation.md](archive/TASK_session_cancellation.md) - What went wrong with session DB

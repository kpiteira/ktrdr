# Task: Branch Cleanup (Surgery Plan)

**Purpose**: Clean up the `feature/agent-mvp` branch by removing session database code while preserving working components.

**Status**: Ready for execution

---

## Overview

The branch has good working code mixed with session database code we're removing. This task documents exactly what to keep, move, adapt, and delete.

**Approach**: Surgical cleanup on current branch (not trash-and-restart)

---

## Inventory

### What We're Keeping (Working Code)

| File | Status | Notes |
|------|--------|-------|
| `ktrdr/agents/invoker.py` | ✅ KEEP | AnthropicAgentInvoker - working agentic loop |
| `ktrdr/agents/executor.py` | ⚠️ ADAPT | ToolExecutor - remove `research_agents` imports |
| `ktrdr/agents/tools.py` | ✅ KEEP | AGENT_TOOLS definitions - working |
| `ktrdr/agents/__init__.py` | ✅ KEEP | Module init |

### What We're Moving (Relocate to ktrdr/agents/)

| Source | Destination | Notes |
|--------|-------------|-------|
| `research_agents/prompts/strategy_designer.py` | `ktrdr/agents/prompts.py` | Remove session_id, use operation_id |
| `research_agents/gates/training_gate.py` | `ktrdr/agents/gates.py` | Merge into single file |
| `research_agents/gates/backtest_gate.py` | `ktrdr/agents/gates.py` | Merge into single file |
| `research_agents/services/strategy_service.py` | `ktrdr/agents/strategy_utils.py` | validate/save/get_recent functions |

### What We're Rewriting (From Phase 0 Plan)

| File | Action | Notes |
|------|--------|-------|
| `ktrdr/api/services/agent_service.py` | REWRITE | New state machine from Phase 0 |
| `ktrdr/api/endpoints/agent.py` | SIMPLIFY | Just trigger/status endpoints |
| `ktrdr/cli/agent_commands.py` | SIMPLIFY | Just trigger/status/cancel |

### What We're Deleting

| Path | Reason |
|------|--------|
| `research_agents/database/` | Session database - entire directory |
| `research_agents/services/trigger.py` | Old trigger service (session-based) |
| `research_agents/services/agent_state.py` | Old state management |
| `research_agents/services/invoker.py` | Duplicate (we have ktrdr/agents/invoker.py) |
| `research_agents/prompts/phase0_test.py` | Test prompt, not needed |
| `research_agents/services/__init__.py` | Will be empty |
| `research_agents/prompts/__init__.py` | Will be empty |
| `research_agents/gates/__init__.py` | Will be empty |
| `research_agents/__init__.py` | Will be empty |

### Tests to Update/Delete

| File | Action | Reason |
|------|--------|--------|
| `tests/unit/agent_tests/test_agent_db.py` | DELETE | Tests session DB |
| `tests/unit/agent_tests/test_trigger.py` | DELETE | Tests old TriggerService |
| `tests/unit/agent_tests/test_trigger_state_machine.py` | DELETE | Tests old state machine |
| `tests/unit/agent_tests/test_background_trigger_loop.py` | DELETE | Tests old loop |
| `tests/unit/agent_tests/test_agent_cancellation_and_recovery.py` | DELETE | Tests session recovery |
| `tests/unit/agent_tests/test_strategy_designer_prompt.py` | KEEP | Tests prompt builder |
| `tests/unit/agent_tests/test_strategy_designer_prompt_full_cycle.py` | ADAPT | Remove session refs |
| `tests/unit/agent_tests/test_anthropic_invoker.py` | KEEP | Tests invoker |
| `tests/unit/agent_tests/test_invoker.py` | KEEP | Tests invoker |
| `tests/unit/agent_tests/test_tool_executor.py` | KEEP | Tests executor |
| `tests/unit/agent_tests/test_agent_tools.py` | KEEP | Tests tools |
| `tests/unit/agent_tests/test_training_gate.py` | ADAPT | Update imports |
| `tests/unit/agent_tests/test_backtest_gate.py` | ADAPT | Update imports |
| `tests/unit/agent_tests/test_get_recent_strategies.py` | ADAPT | Update imports |
| `tests/unit/agent_tests/test_strategy_service.py` | ADAPT | Update imports |
| `tests/unit/agent_tests/test_prompts.py` | KEEP | Basic prompt tests |
| `tests/unit/agent_tests/test_agent_api.py` | REWRITE | New API tests |
| `tests/unit/agent_tests/test_agent_cli.py` | REWRITE | New CLI tests |
| `tests/unit/agent_tests/test_agent_cli_api.py` | REWRITE | New integration |
| `tests/unit/agent_tests/test_agent_operations_service.py` | ADAPT | Remove session refs |
| `tests/unit/api/services/test_agent_parent_child_integration.py` | DELETE | Tests old pattern |
| `tests/integration/agent_tests/test_agent_e2e.py` | REWRITE | New E2E tests |
| `tests/integration/agent_tests/test_agent_real_e2e.py` | REWRITE | New real E2E |
| `tests/integration/agent_tests/test_full_cycle.py` | REWRITE | New full cycle |

---

## Execution Steps

### Step 1: Create Target Files (Empty Shells)

```bash
# Create new files that will receive moved code
touch ktrdr/agents/prompts.py
touch ktrdr/agents/gates.py
touch ktrdr/agents/strategy_utils.py
```

### Step 2: Move and Adapt Prompt Builder

**File**: `ktrdr/agents/prompts.py`

Copy from `research_agents/prompts/strategy_designer.py` with these changes:

1. Remove `session_id` from `PromptContext` (use `operation_id` instead)
2. Update header format in `_format_header()`:
   ```python
   # OLD
   Session ID: {context.session_id}
   # NEW
   Operation ID: {context.operation_id}
   ```
3. Keep everything else (SYSTEM_PROMPT_TEMPLATE is excellent)

### Step 3: Move and Merge Gates

**File**: `ktrdr/agents/gates.py`

Merge `training_gate.py` and `backtest_gate.py`:

```python
"""Quality gates for research cycle phases."""

from dataclasses import dataclass
from typing import Any
import os

# Training gate (from research_agents/gates/training_gate.py)
@dataclass
class TrainingGateConfig:
    min_accuracy: float = 0.45
    max_loss: float = 0.8
    min_loss_decrease: float = 0.2

    @classmethod
    def from_env(cls) -> "TrainingGateConfig":
        return cls(
            min_accuracy=float(os.getenv("TRAINING_GATE_MIN_ACCURACY", "0.45")),
            max_loss=float(os.getenv("TRAINING_GATE_MAX_LOSS", "0.8")),
            min_loss_decrease=float(os.getenv("TRAINING_GATE_MIN_LOSS_DECREASE", "0.2")),
        )


def check_training_gate(
    metrics: dict[str, Any],
    config: TrainingGateConfig | None = None,
) -> tuple[bool, str]:
    """Check if training results pass quality gate."""
    if config is None:
        config = TrainingGateConfig.from_env()
    # ... implementation from training_gate.py


# Backtest gate (from research_agents/gates/backtest_gate.py)
@dataclass
class BacktestGateConfig:
    min_win_rate: float = 0.45
    max_drawdown: float = 0.4
    min_sharpe: float = -0.5

    @classmethod
    def from_env(cls) -> "BacktestGateConfig":
        return cls(
            min_win_rate=float(os.getenv("BACKTEST_GATE_MIN_WIN_RATE", "0.45")),
            max_drawdown=float(os.getenv("BACKTEST_GATE_MAX_DRAWDOWN", "0.4")),
            min_sharpe=float(os.getenv("BACKTEST_GATE_MIN_SHARPE", "-0.5")),
        )


def check_backtest_gate(
    metrics: dict[str, Any],
    config: BacktestGateConfig | None = None,
) -> tuple[bool, str]:
    """Check if backtest results pass quality gate."""
    if config is None:
        config = BacktestGateConfig.from_env()
    # ... implementation from backtest_gate.py
```

### Step 4: Move Strategy Utils

**File**: `ktrdr/agents/strategy_utils.py`

Copy from `research_agents/services/strategy_service.py`:
- `validate_strategy_config()`
- `save_strategy_config()` (renamed `_save_strategy_config`)
- `get_recent_strategies()`
- `DEFAULT_STRATEGIES_DIR`

No session references to remove - this code is clean.

### Step 5: Update Executor Imports

**File**: `ktrdr/agents/executor.py`

```python
# OLD
from research_agents.services.strategy_service import (
    validate_strategy_config,
)
from research_agents.services.strategy_service import (
    save_strategy_config as _save_strategy_config,
)
from research_agents.services.strategy_service import (
    get_recent_strategies,
)

# NEW
from ktrdr.agents.strategy_utils import (
    validate_strategy_config,
    save_strategy_config as _save_strategy_config,
    get_recent_strategies,
)
```

### Step 6: Rewrite AgentService

**File**: `ktrdr/api/services/agent_service.py`

Replace entirely with code from Phase 0 plan. The new service:
- Uses only OperationsService for state
- Has stub phases (30 sec each with 100ms sleeps)
- No session database references

### Step 7: Simplify API Endpoints

**File**: `ktrdr/api/endpoints/agent.py`

Replace with simplified version from Phase 0:
- `POST /agent/trigger` - Start cycle
- `GET /agent/status` - Get status

Remove:
- `GET /agent/sessions` - Session list
- `DELETE /agent/sessions/{id}/cancel` - Session cancel

### Step 8: Simplify CLI Commands

**File**: `ktrdr/cli/agent_commands.py`

Replace with simplified version from Phase 0:
- `ktrdr agent trigger`
- `ktrdr agent status`
- `ktrdr agent cancel <op_id>` (uses operations API)

### Step 9: Clean Up Startup

**File**: `ktrdr/api/startup.py`

Remove all `research_agents` imports and background trigger loop startup.

### Step 10: Delete Session Database Directory

```bash
rm -rf research_agents/database/
rm research_agents/services/trigger.py
rm research_agents/services/agent_state.py
rm research_agents/services/invoker.py
rm research_agents/prompts/phase0_test.py
# Keep research_agents/ directory shell for now (will delete after tests pass)
```

### Step 11: Delete/Update Tests

```bash
# Delete session-dependent tests
rm tests/unit/agent_tests/test_agent_db.py
rm tests/unit/agent_tests/test_trigger.py
rm tests/unit/agent_tests/test_trigger_state_machine.py
rm tests/unit/agent_tests/test_background_trigger_loop.py
rm tests/unit/agent_tests/test_agent_cancellation_and_recovery.py
rm tests/unit/api/services/test_agent_parent_child_integration.py

# Update imports in remaining tests (grep and fix)
```

### Step 12: Update __init__.py Files

**File**: `ktrdr/agents/__init__.py`

```python
"""Agent components for autonomous research."""

from ktrdr.agents.invoker import AnthropicAgentInvoker, AgentResult
from ktrdr.agents.executor import ToolExecutor
from ktrdr.agents.tools import AGENT_TOOLS
from ktrdr.agents.gates import check_training_gate, check_backtest_gate
from ktrdr.agents.prompts import get_strategy_designer_prompt

__all__ = [
    "AnthropicAgentInvoker",
    "AgentResult",
    "ToolExecutor",
    "AGENT_TOOLS",
    "check_training_gate",
    "check_backtest_gate",
    "get_strategy_designer_prompt",
]
```

### Step 13: Final Cleanup

```bash
# Remove empty research_agents directory
rm -rf research_agents/

# Update pyproject.toml if research_agents is listed
# Run tests to verify nothing broke
uv run pytest tests/unit/agent_tests/ -v
```

---

## Verification Checklist

After cleanup:

- [ ] No imports from `research_agents` anywhere in codebase
- [ ] `ktrdr/agents/` contains: invoker.py, executor.py, tools.py, prompts.py, gates.py, strategy_utils.py
- [ ] `ktrdr agent trigger` works (starts stub cycle)
- [ ] `ktrdr agent status` shows progress
- [ ] `ktrdr agent cancel <op_id>` works
- [ ] Unit tests pass: `uv run pytest tests/unit/agent_tests/ -v`
- [ ] No `research_agents/` directory exists

---

## Files Summary

### Final Structure After Cleanup

```
ktrdr/agents/
├── __init__.py          # Exports
├── invoker.py           # AnthropicAgentInvoker (unchanged)
├── executor.py          # ToolExecutor (imports updated)
├── tools.py             # AGENT_TOOLS (unchanged)
├── prompts.py           # StrategyDesignerPromptBuilder (moved from research_agents)
├── gates.py             # Training + Backtest gates (merged from research_agents)
└── strategy_utils.py    # validate/save/get_recent (moved from research_agents)

ktrdr/api/services/
└── agent_service.py     # NEW - State machine from Phase 0

ktrdr/api/endpoints/
└── agent.py             # SIMPLIFIED - trigger/status only

ktrdr/cli/
└── agent_commands.py    # SIMPLIFIED - trigger/status/cancel

docs/agentic/mvp/
├── design.md
├── IMPLEMENTATION_PLAN.md
├── PLAN_phase0_state_machine.md
├── PLAN_phase1_foundation.md
├── PLAN_phase2_training.md
├── PLAN_phase3_full_cycle.md
├── PLAN_phase4_polish.md
└── TASK_branch_cleanup.md  # This file
```

### Deleted

```
research_agents/         # Entire directory
tests/unit/agent_tests/test_agent_db.py
tests/unit/agent_tests/test_trigger.py
tests/unit/agent_tests/test_trigger_state_machine.py
tests/unit/agent_tests/test_background_trigger_loop.py
tests/unit/agent_tests/test_agent_cancellation_and_recovery.py
tests/unit/api/services/test_agent_parent_child_integration.py
```

---

## Estimated Effort

| Step | Time |
|------|------|
| Steps 1-4: Move/adapt code | 30 min |
| Step 5: Update executor imports | 5 min |
| Step 6: Rewrite AgentService | 20 min (copy from Phase 0) |
| Steps 7-9: Simplify API/CLI/startup | 15 min |
| Steps 10-12: Delete and cleanup | 10 min |
| Step 13: Verification | 15 min |
| **Total** | ~1.5 hours |

---

## Risk Mitigation

1. **Before starting**: Commit current state as checkpoint
2. **After each step**: Run `uv run pytest tests/unit/agent_tests/ -v --ignore=tests/unit/agent_tests/test_agent_db.py` to catch breakage early
3. **If something breaks**: `git stash` and debug

# Milestone 0: Branch Cleanup

**Branch**: `feature/agent-mvp` (continue on current branch)
**Builds On**: Nothing (foundation)
**Capability**: Clean foundation with consolidated `ktrdr/agents/` module

---

## Why This Milestone

The branch has session database code mixed with good working code. This milestone surgically removes the session code while preserving:
- `AnthropicAgentInvoker` (working agentic loop)
- `ToolExecutor` (tool execution framework)
- `AGENT_TOOLS` (tool definitions)
- Quality gates (training/backtest)
- Strategy designer prompt

---

## E2E Test

```bash
# Verify no session imports
grep -r "research_agents" ktrdr/ --include="*.py"
# Expected: No matches

# Verify agents module imports work
uv run python -c "from ktrdr.agents import AnthropicAgentInvoker, check_training_gate"
# Expected: No errors

# Verify unit tests pass
make test-unit
# Expected: All pass (session tests deleted)
```

---

## Task 0.1: Create Target Files

**File(s)**:
- `ktrdr/agents/prompts.py`
- `ktrdr/agents/gates.py`
- `ktrdr/agents/strategy_utils.py`

**Type**: CODING

**Description**: Create empty shell files that will receive moved code from `research_agents/`.

**Implementation Notes**:
```python
# ktrdr/agents/prompts.py
"""Prompt builders for agent operations."""

# ktrdr/agents/gates.py
"""Quality gates for research cycle phases."""

# ktrdr/agents/strategy_utils.py
"""Strategy file utilities."""
```

**Acceptance Criteria**:
- [ ] Three new files created in `ktrdr/agents/`
- [ ] Each file has module docstring

---

## Task 0.2: Move and Adapt Prompt Builder

**File(s)**: `ktrdr/agents/prompts.py`
**Type**: CODING

**Description**: Copy `StrategyDesignerPromptBuilder` from `research_agents/prompts/strategy_designer.py`. Change `session_id` to `operation_id`.

**Implementation Notes**:

1. Copy entire file content
2. Update `PromptContext` dataclass:
```python
# OLD
@dataclass
class PromptContext:
    session_id: str
    ...

# NEW
@dataclass
class PromptContext:
    operation_id: str
    ...
```

3. Update `_format_header()`:
```python
# OLD
f"Session ID: {context.session_id}"

# NEW
f"Operation ID: {context.operation_id}"
```

4. Keep `SYSTEM_PROMPT_TEMPLATE` exactly as-is (it's excellent)

**Acceptance Criteria**:
- [ ] `PromptContext` uses `operation_id` instead of `session_id`
- [ ] `get_strategy_designer_prompt()` function exported
- [ ] No `session` references in file

---

## Task 0.3: Move and Merge Gates

**File(s)**: `ktrdr/agents/gates.py`
**Type**: CODING

**Description**: Merge `research_agents/gates/training_gate.py` and `backtest_gate.py` into single file.

**Implementation Notes**:
```python
"""Quality gates for research cycle phases."""

from dataclasses import dataclass
from typing import Any
import os


@dataclass
class TrainingGateConfig:
    """Configuration for training quality gate."""
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
    """Check if training results pass quality gate.

    Returns:
        Tuple of (passed, reason).
    """
    if config is None:
        config = TrainingGateConfig.from_env()

    if metrics.get("accuracy", 0) < config.min_accuracy:
        return False, f"accuracy_below_threshold ({metrics['accuracy']:.1%} < {config.min_accuracy:.0%})"

    if metrics.get("final_loss", 1.0) > config.max_loss:
        return False, f"loss_too_high ({metrics['final_loss']:.3f} > {config.max_loss})"

    initial = metrics.get("initial_loss", 0)
    final = metrics.get("final_loss", 0)
    if initial > 0:
        decrease = (initial - final) / initial
        if decrease < config.min_loss_decrease:
            return False, f"insufficient_loss_decrease ({decrease:.1%} < {config.min_loss_decrease:.0%})"

    return True, "passed"


@dataclass
class BacktestGateConfig:
    """Configuration for backtest quality gate."""
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
    """Check if backtest results pass quality gate.

    Returns:
        Tuple of (passed, reason).
    """
    if config is None:
        config = BacktestGateConfig.from_env()

    if metrics.get("win_rate", 0) < config.min_win_rate:
        return False, f"win_rate_too_low ({metrics['win_rate']:.1%} < {config.min_win_rate:.0%})"

    if metrics.get("max_drawdown", 1.0) > config.max_drawdown:
        return False, f"drawdown_too_high ({metrics['max_drawdown']:.1%} > {config.max_drawdown:.0%})"

    if metrics.get("sharpe_ratio", -999) < config.min_sharpe:
        return False, f"sharpe_too_low ({metrics['sharpe_ratio']:.2f} < {config.min_sharpe})"

    return True, "passed"
```

**Acceptance Criteria**:
- [ ] Both gate functions in single file
- [ ] Both config classes with `from_env()` methods
- [ ] Gate tests pass with updated imports

---

## Task 0.4: Move Strategy Utils

**File(s)**: `ktrdr/agents/strategy_utils.py`
**Type**: CODING

**Description**: Copy utility functions from `research_agents/services/strategy_service.py`.

**Implementation Notes**:
- Copy: `validate_strategy_config()`
- Copy: `save_strategy_config()`
- Copy: `get_recent_strategies()`
- Copy: `DEFAULT_STRATEGIES_DIR` constant
- No session references to remove (code is clean)

**Acceptance Criteria**:
- [ ] All three functions available
- [ ] `DEFAULT_STRATEGIES_DIR` constant defined
- [ ] Strategy service tests pass with updated imports

---

## Task 0.5: Fix Invoker Cancellation

**File(s)**: `ktrdr/agents/invoker.py`
**Type**: CODING

**Description**: Fix `AnthropicAgentInvoker.run()` to properly propagate `CancelledError` instead of catching it as generic exception.

**Implementation Notes**:

Current code (line ~232):
```python
except Exception as e:
    error_msg = str(e)
    logger.error(...)
    return AgentResult(success=False, ...)
```

Fixed code:
```python
except asyncio.CancelledError:
    logger.info(
        "Agent invocation cancelled",
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
    )
    raise  # Propagate cancellation
except Exception as e:
    error_msg = str(e)
    logger.error(...)
    return AgentResult(success=False, ...)
```

Also ensure `import asyncio` is present at top of file.

**Acceptance Criteria**:
- [ ] `CancelledError` is re-raised, not caught
- [ ] `import asyncio` present
- [ ] Existing invoker tests still pass

---

## Task 0.6: Update Executor Imports

**File(s)**: `ktrdr/agents/executor.py`
**Type**: CODING

**Description**: Update imports from `research_agents.services.strategy_service` to `ktrdr.agents.strategy_utils`.

**Implementation Notes**:
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

**Acceptance Criteria**:
- [ ] No imports from `research_agents`
- [ ] Executor tests pass

---

## Task 0.7: Delete Session Code and Tests

**File(s)**: Multiple deletions
**Type**: CODING

**Description**: Delete all session database code and tests.

**Delete these files**:
```
# Session database
research_agents/database/           # Entire directory

# Old services
research_agents/services/trigger.py
research_agents/services/agent_state.py
research_agents/services/invoker.py

# Test prompt
research_agents/prompts/phase0_test.py

# Session-dependent tests
tests/unit/agent_tests/test_agent_db.py
tests/unit/agent_tests/test_trigger.py
tests/unit/agent_tests/test_trigger_state_machine.py
tests/unit/agent_tests/test_background_trigger_loop.py
tests/unit/agent_tests/test_agent_cancellation_and_recovery.py
tests/unit/api/services/test_agent_parent_child_integration.py
```

**Acceptance Criteria**:
- [ ] All listed files deleted
- [ ] No remaining imports from deleted modules
- [ ] `research_agents/` directory can be deleted

---

## Task 0.8: Update Module Exports and Cleanup

**File(s)**:
- `ktrdr/agents/__init__.py`
- `research_agents/` directory (delete)

**Type**: CODING

**Description**: Update agents module exports and delete empty research_agents directory.

**Implementation Notes**:
```python
# ktrdr/agents/__init__.py
"""Agent components for autonomous research."""

from ktrdr.agents.invoker import AnthropicAgentInvoker, AgentResult
from ktrdr.agents.executor import ToolExecutor
from ktrdr.agents.tools import AGENT_TOOLS
from ktrdr.agents.gates import (
    check_training_gate,
    check_backtest_gate,
    TrainingGateConfig,
    BacktestGateConfig,
)
from ktrdr.agents.prompts import get_strategy_designer_prompt, PromptContext
from ktrdr.agents.strategy_utils import (
    validate_strategy_config,
    save_strategy_config,
    get_recent_strategies,
)

__all__ = [
    "AnthropicAgentInvoker",
    "AgentResult",
    "ToolExecutor",
    "AGENT_TOOLS",
    "check_training_gate",
    "check_backtest_gate",
    "TrainingGateConfig",
    "BacktestGateConfig",
    "get_strategy_designer_prompt",
    "PromptContext",
    "validate_strategy_config",
    "save_strategy_config",
    "get_recent_strategies",
]
```

Then delete:
```bash
rm -rf research_agents/
```

**Acceptance Criteria**:
- [ ] `ktrdr/agents/__init__.py` exports all public symbols
- [ ] `research_agents/` directory deleted
- [ ] `make test-unit` passes
- [ ] `make quality` passes

---

## Milestone 0 Verification Script

```bash
#!/bin/bash
set -e

echo "=== M0: Branch Cleanup Verification ==="

# Check no research_agents imports
echo "1. Checking for research_agents imports..."
if grep -r "research_agents" ktrdr/ --include="*.py" | grep -v __pycache__; then
    echo "FAIL: Found research_agents imports"
    exit 1
fi
echo "   PASS: No research_agents imports"

# Check agents module structure
echo "2. Checking agents module files..."
for file in invoker.py executor.py tools.py prompts.py gates.py strategy_utils.py; do
    if [ ! -f "ktrdr/agents/$file" ]; then
        echo "   FAIL: Missing ktrdr/agents/$file"
        exit 1
    fi
done
echo "   PASS: All agent files present"

# Check imports work
echo "3. Checking module imports..."
uv run python -c "
from ktrdr.agents import (
    AnthropicAgentInvoker, AgentResult, ToolExecutor, AGENT_TOOLS,
    check_training_gate, check_backtest_gate,
    get_strategy_designer_prompt, PromptContext,
    validate_strategy_config, save_strategy_config, get_recent_strategies,
)
print('   All imports successful')
"

# Check research_agents deleted
echo "4. Checking research_agents deleted..."
if [ -d "research_agents" ]; then
    echo "   FAIL: research_agents directory still exists"
    exit 1
fi
echo "   PASS: research_agents deleted"

# Run tests
echo "5. Running unit tests..."
make test-unit

# Run quality
echo "6. Running quality checks..."
make quality

echo ""
echo "=== M0 Complete ==="
```

---

## Files Summary After M0

```
ktrdr/agents/
├── __init__.py          # Updated exports
├── invoker.py           # CancelledError fix (Task 0.5)
├── executor.py          # Updated imports (Task 0.6)
├── tools.py             # Unchanged
├── prompts.py           # NEW: From research_agents (Task 0.2)
├── gates.py             # NEW: Merged gates (Task 0.3)
└── strategy_utils.py    # NEW: From research_agents (Task 0.4)
```

**Deleted**:
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

*Estimated effort: ~1.5 hours*

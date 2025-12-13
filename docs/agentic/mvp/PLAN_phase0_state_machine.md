# Phase 0: State Machine (Stub Implementation)

**Goal**: Validate the full state machine works before adding real business logic

**Prerequisite**: TASK_branch_cleanup.md complete
**Branch**: `feature/agent-mvp`

---

## Overview

Before implementing real design/training/backtest/assessment, we first nail the state machine with stub implementations. Each phase is a ~30 second loop of 100ms sleeps, making cancellation testable at any point.

**Why this approach:**
1. Validates architecture before adding complexity
2. Cancellation testable at any phase
3. Progress updates verifiable
4. Gate logic testable with mock metrics
5. Fast iteration (full cycle in ~2 minutes)
6. If design is wrong, we find out with minimal code

---

## Task 0.1: Add AGENT_RESEARCH operation type

**File**: `ktrdr/api/models/operations.py`

```python
class OperationType(str, Enum):
    """Types of async operations."""
    DATA_LOAD = "data_load"
    TRAINING = "training"
    BACKTESTING = "backtesting"
    AGENT_RESEARCH = "agent_research"  # NEW - single operation per research cycle
```

**Test**: Can create/query/cancel AGENT_RESEARCH operations via OperationsService.

---

## Task 0.2: Create AgentService with state machine

**File**: `ktrdr/api/services/agent_service.py` (rewrite from scratch)

```python
"""
Agent research service.

Orchestrates research cycles using OperationsService for state management.
Each cycle is a single AGENT_RESEARCH operation that progresses through phases.
"""

import asyncio
import time
from typing import Any

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationType, OperationStatus
from ktrdr.api.services.operations_service import OperationsService

logger = get_logger(__name__)


class AgentService:
    """Orchestrates agent research cycles.

    Uses OperationsService as the single source of truth for state.
    Each research cycle is one AGENT_RESEARCH operation.
    """

    def __init__(self, operations_service: OperationsService):
        """Initialize the agent service.

        Args:
            operations_service: OperationsService instance for state tracking
        """
        self._ops = operations_service

    async def trigger(self) -> dict[str, Any]:
        """Start a new research cycle.

        Returns:
            Dict with:
            - triggered: bool - whether cycle was started
            - operation_id: str - if triggered
            - reason: str - if not triggered (active_operation_exists)
        """
        # Check for active cycle
        active = await self._get_active_operation()
        if active:
            return {
                "triggered": False,
                "reason": "active_operation_exists",
                "operation_id": active.operation_id,
            }

        # Create operation with initial metadata
        operation = await self._ops.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata={
                "phase": "pending",
                "strategy_name": None,
            },
        )

        # Start the cycle in background
        asyncio.create_task(self._run_research_cycle(operation.operation_id))

        # Start the operation (registers the task for cancellation)
        # Note: We need to pass the task, but create_task already scheduled it
        # The operation is now "running"

        return {
            "triggered": True,
            "operation_id": operation.operation_id,
        }

    async def get_status(self) -> dict[str, Any]:
        """Get current cycle status.

        Returns:
            Dict with:
            - status: "idle" | "active"
            - operation: operation details if active
        """
        active = await self._get_active_operation()

        if not active:
            return {"status": "idle", "operation": None}

        return {
            "status": "active",
            "operation": {
                "id": active.operation_id,
                "phase": active.metadata.get("phase", "unknown"),
                "progress": {
                    "percentage": active.progress.percentage if active.progress else 0,
                    "current_step": active.progress.current_step if active.progress else "",
                },
                "strategy_name": active.metadata.get("strategy_name"),
                "created_at": active.created_at.isoformat() if active.created_at else None,
            },
        }

    async def _get_active_operation(self):
        """Get the active AGENT_RESEARCH operation, if any."""
        operations = await self._ops.list_operations(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        return operations[0] if operations else None

    async def _update_phase(self, operation_id: str, phase: str) -> None:
        """Update the phase in operation metadata."""
        op = await self._ops.get_operation(operation_id)
        if op:
            metadata = op.metadata or {}
            metadata["phase"] = phase
            await self._ops.update_metadata(operation_id, metadata)

    async def _update_metadata(self, operation_id: str, updates: dict[str, Any]) -> None:
        """Update operation metadata with new values."""
        op = await self._ops.get_operation(operation_id)
        if op:
            metadata = op.metadata or {}
            metadata.update(updates)
            await self._ops.update_metadata(operation_id, metadata)

    # =========================================================================
    # RESEARCH CYCLE - State Machine
    # =========================================================================

    async def _run_research_cycle(self, operation_id: str) -> None:
        """Execute a full research cycle.

        State machine:
        PENDING → DESIGNING → TRAINING → BACKTESTING → ASSESSING → COMPLETED

        Any phase can fail → FAILED
        Cancellation → CANCELLED
        """
        try:
            # Mark as running
            await self._ops.update_progress(operation_id, 0, "Starting research cycle")

            # Phase 1: Design
            await self._update_phase(operation_id, "designing")
            design_result = await self._run_design_phase(operation_id)

            if not design_result.get("success"):
                await self._ops.fail_operation(
                    operation_id,
                    error_message=design_result.get("error", "Design failed"),
                )
                return

            strategy_name = design_result.get("strategy_name")
            await self._update_metadata(operation_id, {
                "strategy_name": strategy_name,
                "strategy_path": design_result.get("strategy_path"),
            })

            # Phase 2: Training
            await self._update_phase(operation_id, "training")
            train_result = await self._run_training_phase(operation_id, strategy_name)

            if not train_result.get("success"):
                await self._ops.fail_operation(
                    operation_id,
                    error_message=train_result.get("error", "Training failed"),
                )
                return

            # Training gate
            gate_passed, gate_reason = self._check_training_gate(train_result)
            if not gate_passed:
                await self._ops.fail_operation(
                    operation_id,
                    error_message=f"Training gate failed: {gate_reason}",
                )
                return

            await self._update_metadata(operation_id, {
                "training_result": train_result,
                "model_path": train_result.get("model_path"),
            })

            # Phase 3: Backtesting
            await self._update_phase(operation_id, "backtesting")
            backtest_result = await self._run_backtest_phase(
                operation_id, strategy_name, train_result.get("model_path")
            )

            if not backtest_result.get("success"):
                await self._ops.fail_operation(
                    operation_id,
                    error_message=backtest_result.get("error", "Backtest failed"),
                )
                return

            # Backtest gate
            gate_passed, gate_reason = self._check_backtest_gate(backtest_result)
            if not gate_passed:
                await self._ops.fail_operation(
                    operation_id,
                    error_message=f"Backtest gate failed: {gate_reason}",
                )
                return

            await self._update_metadata(operation_id, {
                "backtest_result": backtest_result,
            })

            # Phase 4: Assessment
            await self._update_phase(operation_id, "assessing")
            assessment = await self._run_assessment_phase(
                operation_id, strategy_name, train_result, backtest_result
            )

            await self._update_metadata(operation_id, {
                "assessment": assessment,
            })

            # Complete!
            await self._ops.complete_operation(
                operation_id,
                result_summary={
                    "phase": "completed",
                    "strategy_name": strategy_name,
                    "verdict": assessment.get("verdict"),
                },
            )

            logger.info(f"Research cycle {operation_id} completed successfully")

        except asyncio.CancelledError:
            logger.info(f"Research cycle {operation_id} cancelled")
            # OperationsService handles marking as cancelled
            raise
        except Exception as e:
            logger.error(f"Research cycle {operation_id} failed: {e}", exc_info=True)
            await self._ops.fail_operation(operation_id, error_message=str(e))

    # =========================================================================
    # STUB PHASES - Replace with real implementations later
    # Each phase runs ~30 seconds with 100ms sleeps for cancellation testing
    # =========================================================================

    async def _run_design_phase(self, operation_id: str) -> dict[str, Any]:
        """STUB: Simulate design phase (~30 seconds).

        Real implementation will call AnthropicAgentInvoker.
        """
        logger.info(f"[{operation_id}] Starting STUB design phase")

        steps = 300  # 300 * 100ms = 30 seconds
        for i in range(steps):
            # Check for cancellation
            await asyncio.sleep(0.1)

            # Update progress (0-25% of total cycle)
            pct = int((i / steps) * 25)
            step_name = f"Designing strategy... ({i}/{steps})"
            if i % 50 == 0:  # Update every 5 seconds
                await self._ops.update_progress(operation_id, pct, step_name)

        strategy_name = f"stub_strategy_{int(time.time())}"
        logger.info(f"[{operation_id}] STUB design complete: {strategy_name}")

        return {
            "success": True,
            "strategy_name": strategy_name,
            "strategy_path": f"/strategies/{strategy_name}.yaml",
        }

    async def _run_training_phase(
        self, operation_id: str, strategy_name: str
    ) -> dict[str, Any]:
        """STUB: Simulate training phase (~30 seconds).

        Real implementation will call training API and poll for completion.
        """
        logger.info(f"[{operation_id}] Starting STUB training phase for {strategy_name}")

        steps = 300  # 300 * 100ms = 30 seconds
        for i in range(steps):
            # Check for cancellation
            await asyncio.sleep(0.1)

            # Update progress (25-60% of total cycle)
            pct = 25 + int((i / steps) * 35)
            step_name = f"Training model... epoch {i // 30 + 1}/10"
            if i % 50 == 0:  # Update every 5 seconds
                await self._ops.update_progress(operation_id, pct, step_name)

        logger.info(f"[{operation_id}] STUB training complete")

        # Return mock metrics that pass the gate
        return {
            "success": True,
            "model_path": f"/models/{strategy_name}/model.pt",
            "accuracy": 0.55,  # Passes 45% threshold
            "final_loss": 0.35,  # Passes 0.8 threshold
            "initial_loss": 0.9,  # Shows 61% decrease
        }

    async def _run_backtest_phase(
        self, operation_id: str, strategy_name: str, model_path: str
    ) -> dict[str, Any]:
        """STUB: Simulate backtest phase (~30 seconds).

        Real implementation will call backtest API and poll for completion.
        """
        logger.info(f"[{operation_id}] Starting STUB backtest phase")

        steps = 300  # 300 * 100ms = 30 seconds
        for i in range(steps):
            # Check for cancellation
            await asyncio.sleep(0.1)

            # Update progress (60-85% of total cycle)
            pct = 60 + int((i / steps) * 25)
            step_name = f"Backtesting... bar {i * 10}/{steps * 10}"
            if i % 50 == 0:  # Update every 5 seconds
                await self._ops.update_progress(operation_id, pct, step_name)

        logger.info(f"[{operation_id}] STUB backtest complete")

        # Return mock metrics that pass the gate
        return {
            "success": True,
            "win_rate": 0.52,  # Passes 45% threshold
            "max_drawdown": 0.15,  # Passes 40% threshold
            "sharpe_ratio": 0.8,  # Passes -0.5 threshold
            "total_trades": 156,
            "profit_factor": 1.3,
        }

    async def _run_assessment_phase(
        self,
        operation_id: str,
        strategy_name: str,
        training_result: dict[str, Any],
        backtest_result: dict[str, Any],
    ) -> dict[str, Any]:
        """STUB: Simulate assessment phase (~30 seconds).

        Real implementation will call AnthropicAgentInvoker for assessment.
        """
        logger.info(f"[{operation_id}] Starting STUB assessment phase")

        steps = 300  # 300 * 100ms = 30 seconds
        for i in range(steps):
            # Check for cancellation
            await asyncio.sleep(0.1)

            # Update progress (85-100% of total cycle)
            pct = 85 + int((i / steps) * 15)
            step_name = "Claude analyzing results..."
            if i % 50 == 0:  # Update every 5 seconds
                await self._ops.update_progress(operation_id, pct, step_name)

        logger.info(f"[{operation_id}] STUB assessment complete")

        return {
            "verdict": "promising",
            "raw_text": "STUB: This is a placeholder assessment.",
            "strengths": ["Good accuracy", "Reasonable Sharpe"],
            "weaknesses": ["Limited data", "Single symbol"],
            "suggestions": ["Try multi-symbol", "Extend date range"],
        }

    # =========================================================================
    # QUALITY GATES
    # =========================================================================

    def _check_training_gate(self, train_result: dict[str, Any]) -> tuple[bool, str]:
        """Check if training results pass quality gate."""
        accuracy = train_result.get("accuracy")
        final_loss = train_result.get("final_loss")
        initial_loss = train_result.get("initial_loss")

        if accuracy is not None and accuracy < 0.45:
            return False, f"accuracy_below_threshold ({accuracy:.1%} < 45%)"

        if final_loss is not None and final_loss > 0.8:
            return False, f"loss_too_high ({final_loss:.3f} > 0.8)"

        if initial_loss is not None and final_loss is not None and initial_loss > 0:
            decrease_pct = (initial_loss - final_loss) / initial_loss
            if decrease_pct < 0.2:
                return False, f"insufficient_loss_decrease ({decrease_pct:.1%} < 20%)"

        return True, "passed"

    def _check_backtest_gate(self, backtest_result: dict[str, Any]) -> tuple[bool, str]:
        """Check if backtest results pass quality gate."""
        win_rate = backtest_result.get("win_rate")
        max_drawdown = backtest_result.get("max_drawdown")
        sharpe = backtest_result.get("sharpe_ratio")

        if win_rate is not None and win_rate < 0.45:
            return False, f"win_rate_too_low ({win_rate:.1%} < 45%)"

        if max_drawdown is not None and max_drawdown > 0.4:
            return False, f"drawdown_too_high ({max_drawdown:.1%} > 40%)"

        if sharpe is not None and sharpe < -0.5:
            return False, f"sharpe_too_low ({sharpe:.2f} < -0.5)"

        return True, "passed"
```

---

## Task 0.3: Wire up API endpoints

**File**: `ktrdr/api/endpoints/agent.py`

Simplify to just trigger/status:

```python
"""Agent research API endpoints."""

from fastapi import APIRouter, Depends

from ktrdr.api.dependencies import get_agent_service
from ktrdr.api.services.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/trigger")
async def trigger_research_cycle(
    agent_service: AgentService = Depends(get_agent_service),
):
    """Start a new research cycle.

    Returns operation_id if triggered, or rejection reason if not.
    """
    result = await agent_service.trigger()
    return result


@router.get("/status")
async def get_agent_status(
    agent_service: AgentService = Depends(get_agent_service),
):
    """Get current research cycle status.

    Returns 'idle' if no active cycle, or operation details if active.
    """
    result = await agent_service.get_status()
    return result
```

**File**: `ktrdr/api/dependencies.py`

Add dependency:

```python
from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import get_operations_service

def get_agent_service() -> AgentService:
    """Get AgentService instance."""
    ops = get_operations_service()
    return AgentService(operations_service=ops)
```

---

## Task 0.4: Wire up CLI commands

**File**: `ktrdr/cli/agent_commands.py`

Simplify to trigger/status/cancel:

```python
"""Agent CLI commands."""

import asyncio
import sys

import typer
from rich.console import Console

from ktrdr.cli.helpers.async_cli_client import AsyncCLIClient
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr import get_logger

logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

agent_app = typer.Typer(name="agent", help="Agent research commands")


@agent_app.command("status")
@trace_cli_command("agent_status")
def status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed info"),
):
    """Show current agent research cycle status."""
    try:
        asyncio.run(_status_async(verbose))
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


async def _status_async(verbose: bool = False):
    """Get and display agent status."""
    async with AsyncCLIClient() as client:
        result = await client.get("/agent/status")

    if result.get("status") == "idle":
        console.print("\n[dim]No active research cycle[/dim]")
        return

    op = result.get("operation", {})
    console.print(f"\n[bold green]Active Research Cycle[/bold green]")
    console.print(f"  Operation: {op.get('id', 'unknown')}")
    console.print(f"  Phase: [cyan]{op.get('phase', 'unknown')}[/cyan]")

    progress = op.get("progress", {})
    pct = progress.get("percentage", 0)
    step = progress.get("current_step", "")

    # Progress bar
    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    console.print(f"  Progress: [{bar}] {pct:.0f}%")

    if step:
        console.print(f"  Step: {step}")

    if op.get("strategy_name"):
        console.print(f"  Strategy: {op['strategy_name']}")

    if verbose and op.get("created_at"):
        console.print(f"  Started: {op['created_at']}")


@agent_app.command("trigger")
@trace_cli_command("agent_trigger")
def trigger():
    """Start a new research cycle."""
    try:
        asyncio.run(_trigger_async())
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


async def _trigger_async():
    """Trigger a research cycle."""
    async with AsyncCLIClient() as client:
        result = await client.post("/agent/trigger")

    if result.get("triggered"):
        console.print(f"\n[green]Research cycle started![/green]")
        console.print(f"  Operation ID: {result.get('operation_id')}")
        console.print(f"\nMonitor with: [cyan]ktrdr agent status[/cyan]")
    else:
        reason = result.get("reason", "unknown")
        if reason == "active_operation_exists":
            console.print(f"\n[yellow]Cycle already in progress[/yellow]")
            console.print(f"  Operation ID: {result.get('operation_id')}")
        else:
            console.print(f"\n[red]Could not start cycle:[/red] {reason}")


@agent_app.command("cancel")
@trace_cli_command("agent_cancel")
def cancel(
    operation_id: str = typer.Argument(help="Operation ID to cancel"),
):
    """Cancel an active research cycle."""
    try:
        asyncio.run(_cancel_async(operation_id))
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


async def _cancel_async(operation_id: str):
    """Cancel a research cycle via operations API."""
    async with AsyncCLIClient() as client:
        result = await client.delete(f"/operations/{operation_id}/cancel")

    if result.get("success"):
        console.print(f"\n[green]Operation cancelled![/green]")
    else:
        error = result.get("error", "Unknown error")
        console.print(f"\n[red]Cancel failed:[/red] {error}")
```

---

## Task 0.5: Add OperationsService.update_metadata

**File**: `ktrdr/api/services/operations_service.py`

Add method to update metadata (if not already present):

```python
async def update_metadata(
    self, operation_id: str, metadata: dict[str, Any]
) -> None:
    """Update operation metadata.

    Args:
        operation_id: Operation to update
        metadata: New metadata dict (replaces existing)
    """
    if operation_id in self._operations:
        self._operations[operation_id].metadata = metadata
```

---

## Phase 0 Verification

### Test Sequence

```bash
# 1. Start services
docker compose up -d

# 2. Trigger a cycle
ktrdr agent trigger
# Expected: "Research cycle started! Operation ID: op_agent_research_..."

# 3. Watch status (separate terminal)
watch -n 1 "ktrdr agent status"
# Expected: Phase progresses through designing → training → backtesting → assessing
# Expected: Progress bar updates every ~5 seconds
# Expected: Full cycle takes ~2 minutes

# 4. Test cancellation at different phases
ktrdr agent trigger
# Wait for "training" phase
ktrdr agent cancel <op_id>
# Expected: Clean cancellation

# 5. Verify operation in list
ktrdr operations list --type agent_research
# Expected: Shows completed/cancelled operations

# 6. Test gate failure
# Modify _run_training_phase to return accuracy=0.30
# Trigger cycle, should fail at training gate
```

### Acceptance Criteria

- [ ] `ktrdr agent trigger` starts a cycle
- [ ] `ktrdr agent status` shows phase and progress
- [ ] Progress bar updates during each phase
- [ ] Full cycle completes in ~2 minutes (4 phases × 30 sec)
- [ ] Cancellation works at any phase (100ms granularity)
- [ ] Gate failures mark cycle as FAILED with reason
- [ ] Operations appear in `ktrdr operations list`
- [ ] No session database code used

---

## Files Created/Modified Summary

| File | Action |
|------|--------|
| `ktrdr/api/models/operations.py` | Modify - add AGENT_RESEARCH |
| `ktrdr/api/services/agent_service.py` | Rewrite - state machine with stubs |
| `ktrdr/api/services/operations_service.py` | Modify - add update_metadata |
| `ktrdr/api/endpoints/agent.py` | Simplify - trigger/status only |
| `ktrdr/api/dependencies.py` | Modify - add get_agent_service |
| `ktrdr/cli/agent_commands.py` | Simplify - trigger/status/cancel |

---

## What's NOT in Phase 0

- Real Anthropic API calls (design, assessment)
- Real training API calls
- Real backtest API calls
- Budget tracking
- Observability (metrics, traces)
- Strategy file saving
- Assessment file saving

These come in Phases 1-4 by replacing the stubs.

---

## Next Steps After Phase 0

Once the state machine works:

1. **Phase 1**: Replace design stub with real AnthropicAgentInvoker
2. **Phase 2**: Replace training stub with real training API polling
3. **Phase 3**: Replace backtest stub with real backtest API polling, add assessment
4. **Phase 4**: Add budget, metrics, tracing, error handling

# Milestone 1: Orchestrator Shell

**Branch**: `feature/agent-mvp`
**Builds On**: M0 (Branch Cleanup)
**Capability**: User can trigger a research cycle and see it progress through phases with stub workers

---

## Why This Milestone

Proves the orchestrator pattern works — state machine loop, child operation tracking, phase transitions — before adding real business logic. With stub workers, the full cycle completes in ~30 seconds.

---

## E2E Test

```bash
# Start cycle via API
curl -X POST http://localhost:8000/api/v1/agent/trigger
# Expected: {"triggered": true, "operation_id": "op_agent_research_..."}

# Watch progress (~30 seconds with stubs)
watch -n 2 'curl -s http://localhost:8000/api/v1/agent/status | jq'
# Expected: Phase progresses: designing → training → backtesting → assessing → completed

# CLI equivalents
ktrdr agent trigger
ktrdr agent status
ktrdr operations list --type agent_research
```

---

## Task 1.1: Add Operation Types

**File(s)**: `ktrdr/api/models/operations.py`
**Type**: CODING

**Description**: Add/update operation types for agent system.

**Implementation Notes**:
```python
class OperationType(str, Enum):
    # ... existing types ...
    DATA_LOAD = "data_load"
    TRAINING = "training"
    BACKTESTING = "backtesting"
    INDICATOR_COMPUTE = "indicator_compute"
    FUZZY_ANALYSIS = "fuzzy_analysis"
    DUMMY = "dummy"

    # Agent types (add/update these)
    AGENT_RESEARCH = "agent_research"      # Orchestrator operation
    AGENT_DESIGN = "agent_design"          # Claude design phase
    AGENT_ASSESSMENT = "agent_assessment"  # Claude assessment phase
```

Note: `AGENT_SESSION` may exist — rename to `AGENT_RESEARCH` for clarity.

**Acceptance Criteria**:
- [ ] `AGENT_RESEARCH` type exists
- [ ] `AGENT_DESIGN` type exists
- [ ] `AGENT_ASSESSMENT` type exists
- [ ] No breaking changes to existing types

---

## Task 1.2: Create Stub Child Workers

**File(s)**:
- `ktrdr/agents/workers/__init__.py`
- `ktrdr/agents/workers/stubs.py`

**Type**: CODING

**Description**: Create stub worker classes that complete instantly with mock results.

**Implementation Notes**:
```python
# ktrdr/agents/workers/stubs.py
"""Stub workers for testing orchestrator without real operations."""

import asyncio
from typing import Any


class StubDesignWorker:
    """Stub that simulates strategy design."""

    async def run(self, operation_id: str) -> dict[str, Any]:
        """Simulate design phase (~500ms)."""
        await asyncio.sleep(0.5)
        return {
            "success": True,
            "strategy_name": "stub_momentum_v1",
            "strategy_path": "/app/strategies/stub_momentum_v1.yaml",
            "input_tokens": 2500,
            "output_tokens": 1800,
        }


class StubTrainingWorker:
    """Stub that simulates model training."""

    async def run(self, operation_id: str, strategy_path: str) -> dict[str, Any]:
        """Simulate training phase (~500ms)."""
        await asyncio.sleep(0.5)
        return {
            "success": True,
            "accuracy": 0.65,
            "final_loss": 0.35,
            "initial_loss": 0.85,
            "model_path": "/app/models/stub_momentum_v1/model.pt",
        }


class StubBacktestWorker:
    """Stub that simulates backtesting."""

    async def run(self, operation_id: str, model_path: str) -> dict[str, Any]:
        """Simulate backtest phase (~500ms)."""
        await asyncio.sleep(0.5)
        return {
            "success": True,
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "max_drawdown": 0.15,
            "total_return": 0.23,
        }


class StubAssessmentWorker:
    """Stub that simulates Claude assessment."""

    async def run(self, operation_id: str, results: dict[str, Any]) -> dict[str, Any]:
        """Simulate assessment phase (~500ms)."""
        await asyncio.sleep(0.5)
        return {
            "success": True,
            "verdict": "promising",
            "strengths": ["Good risk management", "Consistent returns"],
            "weaknesses": ["Limited sample size"],
            "suggestions": ["Test with longer timeframe"],
            "input_tokens": 3000,
            "output_tokens": 1500,
        }
```

**Unit Tests** (`tests/unit/agent_tests/test_stub_workers.py`):
- [ ] Test: StubDesignWorker returns strategy_name
- [ ] Test: StubTrainingWorker returns accuracy and loss
- [ ] Test: StubBacktestWorker returns sharpe and win_rate
- [ ] Test: StubAssessmentWorker returns verdict

**Acceptance Criteria**:
- [ ] Four stub worker classes created
- [ ] Each returns mock successful results
- [ ] Each has ~500ms delay
- [ ] Unit tests pass

---

## Task 1.3: Create AgentResearchWorker (Orchestrator)

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Create the orchestrator worker that runs the state machine loop.

**Implementation Notes**:
```python
# ktrdr/agents/workers/research_worker.py
"""Orchestrator worker for agent research cycles."""

import asyncio
from typing import Any, Protocol

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationStatus, OperationType
from ktrdr.api.services.operations_service import OperationsService

logger = get_logger(__name__)


class ChildWorker(Protocol):
    """Protocol for child workers."""
    async def run(self, operation_id: str, **kwargs) -> dict[str, Any]: ...


class AgentResearchWorker:
    """Orchestrator for research cycles. Runs as AGENT_RESEARCH operation."""

    PHASES = ["designing", "training", "backtesting", "assessing"]
    POLL_INTERVAL = 5.0  # seconds between status checks (short for stubs)

    def __init__(
        self,
        operations_service: OperationsService,
        design_worker: ChildWorker,
        training_worker: ChildWorker,
        backtest_worker: ChildWorker,
        assessment_worker: ChildWorker,
    ):
        self.ops = operations_service
        self.design_worker = design_worker
        self.training_worker = training_worker
        self.backtest_worker = backtest_worker
        self.assessment_worker = assessment_worker

    async def run(self, operation_id: str) -> dict[str, Any]:
        """Main orchestrator loop."""
        logger.info("Starting research cycle", operation_id=operation_id)

        try:
            # Phase 1: Design
            await self._update_phase(operation_id, "designing")
            design_result = await self._run_child(
                operation_id, "design", self.design_worker.run, operation_id
            )

            # Phase 2: Training
            await self._update_phase(operation_id, "training")
            training_result = await self._run_child(
                operation_id, "training", self.training_worker.run,
                operation_id, design_result["strategy_path"]
            )

            # Phase 3: Backtest
            await self._update_phase(operation_id, "backtesting")
            backtest_result = await self._run_child(
                operation_id, "backtest", self.backtest_worker.run,
                operation_id, training_result["model_path"]
            )

            # Phase 4: Assessment
            await self._update_phase(operation_id, "assessing")
            assessment_result = await self._run_child(
                operation_id, "assessment", self.assessment_worker.run,
                operation_id, {
                    "training": training_result,
                    "backtest": backtest_result,
                }
            )

            # Complete
            return {
                "success": True,
                "strategy_name": design_result["strategy_name"],
                "verdict": assessment_result["verdict"],
            }

        except asyncio.CancelledError:
            logger.info("Research cycle cancelled", operation_id=operation_id)
            raise
        except Exception as e:
            logger.error("Research cycle failed", operation_id=operation_id, error=str(e))
            raise

    async def _update_phase(self, operation_id: str, phase: str):
        """Update operation metadata with current phase."""
        await self.ops.update_operation_metadata(
            operation_id, {"phase": phase}
        )
        logger.info("Phase started", operation_id=operation_id, phase=phase)

    async def _run_child(
        self, parent_op_id: str, child_name: str,
        worker_func, *args, **kwargs
    ) -> dict[str, Any]:
        """Run a child worker and track its operation."""
        # Create child operation
        child_op = await self.ops.create_operation(
            operation_type=self._get_child_op_type(child_name),
            metadata={"parent_operation_id": parent_op_id},
        )

        # Track child in parent metadata
        await self.ops.update_operation_metadata(
            parent_op_id, {f"{child_name}_op_id": child_op.operation_id}
        )

        try:
            # Run child worker
            result = await worker_func(*args, **kwargs)

            # Mark child complete
            await self.ops.complete_operation(child_op.operation_id, result)
            return result

        except Exception as e:
            await self.ops.fail_operation(child_op.operation_id, str(e))
            raise

    def _get_child_op_type(self, child_name: str) -> OperationType:
        """Get operation type for child."""
        return {
            "design": OperationType.AGENT_DESIGN,
            "training": OperationType.TRAINING,
            "backtest": OperationType.BACKTESTING,
            "assessment": OperationType.AGENT_ASSESSMENT,
        }[child_name]

    async def _cancellable_sleep(self, seconds: float):
        """Sleep in small intervals for cancellation responsiveness."""
        intervals = int(seconds / 0.1)
        for _ in range(intervals):
            await asyncio.sleep(0.1)
```

**Unit Tests** (`tests/unit/agent_tests/test_research_worker.py`):
- [ ] Test: State advances from idle → designing → training → backtesting → assessing → complete
- [ ] Test: Child operation IDs stored in parent metadata
- [ ] Test: Cancellation stops worker within 200ms
- [ ] Test: Child failure propagates to parent
- [ ] Test: Phase updates visible in operation metadata

**Acceptance Criteria**:
- [ ] State machine transitions through all phases
- [ ] Child operation IDs tracked in parent metadata
- [ ] Uses 100ms sleep intervals for cancellation
- [ ] Completes full cycle with stub workers

---

## Task 1.4: Create New AgentService

**File(s)**: `ktrdr/api/services/agent_service.py`
**Type**: CODING (complete rewrite)

**Description**: Replace session-based service with operations-only service.

**Implementation Notes**:
```python
# ktrdr/api/services/agent_service.py
"""Agent API service - operations-only, no sessions."""

import asyncio
from typing import Any

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationStatus, OperationType
from ktrdr.api.services.operations_service import (
    OperationsService,
    get_operations_service,
)
from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.agents.workers.stubs import (
    StubDesignWorker,
    StubTrainingWorker,
    StubBacktestWorker,
    StubAssessmentWorker,
)

logger = get_logger(__name__)


class AgentService:
    """Service layer for agent API operations."""

    def __init__(self, operations_service: OperationsService | None = None):
        self.ops = operations_service or get_operations_service()
        self._worker: AgentResearchWorker | None = None

    def _get_worker(self) -> AgentResearchWorker:
        """Get or create the research worker."""
        if self._worker is None:
            self._worker = AgentResearchWorker(
                operations_service=self.ops,
                design_worker=StubDesignWorker(),
                training_worker=StubTrainingWorker(),
                backtest_worker=StubBacktestWorker(),
                assessment_worker=StubAssessmentWorker(),
            )
        return self._worker

    async def trigger(self) -> dict[str, Any]:
        """Start a new research cycle.

        Returns immediately with operation_id. Cycle runs in background.
        """
        # Check for active cycle
        active = await self._get_active_research_op()
        if active:
            return {
                "triggered": False,
                "reason": "active_cycle_exists",
                "operation_id": active.operation_id,
                "message": f"Active cycle exists: {active.operation_id}",
            }

        # Create operation
        op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata={"phase": "idle"},
        )

        # Start worker in background
        worker = self._get_worker()
        task = asyncio.create_task(self._run_worker(op.operation_id, worker))
        await self.ops.start_operation(op.operation_id, task)

        logger.info("Research cycle triggered", operation_id=op.operation_id)

        return {
            "triggered": True,
            "operation_id": op.operation_id,
            "message": "Research cycle started",
        }

    async def _run_worker(self, operation_id: str, worker: AgentResearchWorker):
        """Run worker and handle completion/failure."""
        try:
            result = await worker.run(operation_id)
            await self.ops.complete_operation(operation_id, result)
        except asyncio.CancelledError:
            await self.ops.cancel_operation(operation_id, "Cancelled by user")
            raise
        except Exception as e:
            await self.ops.fail_operation(operation_id, str(e))
            raise

    async def get_status(self) -> dict[str, Any]:
        """Get current agent status."""
        active = await self._get_active_research_op()

        if active:
            return {
                "status": "active",
                "operation_id": active.operation_id,
                "phase": active.metadata.get("phase", "unknown"),
                "progress": active.progress.model_dump() if active.progress else None,
                "strategy_name": active.metadata.get("strategy_name"),
                "started_at": active.created_at.isoformat() if active.created_at else None,
            }

        # Find last completed/failed
        last = await self._get_last_research_op()
        if last:
            return {
                "status": "idle",
                "last_cycle": {
                    "operation_id": last.operation_id,
                    "outcome": last.status.value,
                    "strategy_name": last.result_summary.get("strategy_name") if last.result_summary else None,
                    "completed_at": last.completed_at.isoformat() if last.completed_at else None,
                },
            }

        return {"status": "idle", "last_cycle": None}

    async def _get_active_research_op(self):
        """Get active AGENT_RESEARCH operation if any."""
        ops = await self.ops.list_operations(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            limit=1,
        )
        return ops[0] if ops else None

    async def _get_last_research_op(self):
        """Get most recent completed/failed AGENT_RESEARCH operation."""
        for status in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
            ops = await self.ops.list_operations(
                operation_type=OperationType.AGENT_RESEARCH,
                status=status,
                limit=1,
            )
            if ops:
                return ops[0]
        return None


# Singleton
_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    """Get the agent service singleton."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
```

**Unit Tests** (`tests/unit/agent_tests/test_agent_service_new.py`):
- [ ] Test: trigger() creates AGENT_RESEARCH operation
- [ ] Test: trigger() returns operation_id
- [ ] Test: trigger() rejects if cycle already active
- [ ] Test: get_status() returns phase from metadata
- [ ] Test: get_status() returns idle when no active cycle

**Acceptance Criteria**:
- [ ] No imports from `research_agents`
- [ ] `trigger()` creates operation and starts worker
- [ ] `get_status()` returns phase info
- [ ] Rejects trigger if cycle already active

---

## Task 1.5: Simplify API Endpoints

**File(s)**: `ktrdr/api/endpoints/agent.py`
**Type**: CODING (simplify)

**Description**: Simplify endpoints to just trigger and status.

**Implementation Notes**:
```python
# ktrdr/api/endpoints/agent.py
"""Agent API endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ktrdr import get_logger
from ktrdr.api.services.agent_service import get_agent_service

logger = get_logger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/trigger")
async def trigger_agent():
    """Start a new research cycle.

    Returns 202 if triggered, 409 if cycle already active.
    """
    service = get_agent_service()
    result = await service.trigger()

    if result["triggered"]:
        return JSONResponse(result, status_code=202)
    return JSONResponse(result, status_code=409)


@router.get("/status")
async def get_agent_status():
    """Get current agent status.

    Returns current phase if active, or last cycle info if idle.
    """
    service = get_agent_service()
    return await service.get_status()
```

**Remove** (delete these routes if they exist):
- `GET /agent/sessions`
- `DELETE /agent/sessions/{id}/cancel`
- Any other session-related endpoints

**Acceptance Criteria**:
- [ ] Only `POST /trigger` and `GET /status` endpoints
- [ ] No session-related endpoints
- [ ] Swagger docs show new contract
- [ ] Correct HTTP status codes (202, 409)

---

## Task 1.6: Simplify CLI Commands

**File(s)**: `ktrdr/cli/agent_commands.py`
**Type**: CODING (simplify)

**Description**: Simplify CLI to trigger and status commands.

**Implementation Notes**:
```python
# ktrdr/cli/agent_commands.py
"""Agent CLI commands."""

import click
import requests

from ktrdr.cli.utils import get_api_url, format_json


@click.group("agent")
def agent_group():
    """Agent research cycle commands."""
    pass


@agent_group.command("trigger")
def trigger_agent():
    """Start a new research cycle."""
    url = f"{get_api_url()}/agent/trigger"

    try:
        response = requests.post(url, timeout=10)
        data = response.json()

        if data.get("triggered"):
            click.echo(f"Research cycle started!")
            click.echo(f"Operation ID: {data['operation_id']}")
            click.echo(f"\nUse 'ktrdr agent status' to monitor progress.")
        else:
            click.echo(f"Could not start cycle: {data.get('reason')}")
            if data.get("operation_id"):
                click.echo(f"Active operation: {data['operation_id']}")

    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@agent_group.command("status")
def agent_status():
    """Show current agent status."""
    url = f"{get_api_url()}/agent/status"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get("status") == "active":
            click.echo("Status: ACTIVE")
            click.echo(f"Operation: {data['operation_id']}")
            click.echo(f"Phase: {data['phase']}")
            if data.get("strategy_name"):
                click.echo(f"Strategy: {data['strategy_name']}")
        else:
            click.echo("Status: IDLE")
            if data.get("last_cycle"):
                last = data["last_cycle"]
                click.echo(f"\nLast cycle:")
                click.echo(f"  Operation: {last['operation_id']}")
                click.echo(f"  Outcome: {last['outcome']}")
                if last.get("strategy_name"):
                    click.echo(f"  Strategy: {last['strategy_name']}")
            else:
                click.echo("No previous cycles.")

    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)
```

**Note**: Cancel uses existing operations CLI: `ktrdr operations cancel <op_id>`

**Acceptance Criteria**:
- [ ] `ktrdr agent trigger` works
- [ ] `ktrdr agent status` shows phase and progress
- [ ] Remove session-related commands
- [ ] Help text is clear

---

## Task 1.7: Wire Up Startup

**File(s)**: `ktrdr/api/startup.py`
**Type**: CODING

**Description**: Remove old research_agents imports from startup.

**Implementation Notes**:
- Remove any `from research_agents` imports
- Remove background trigger loop if present
- Agent system is triggered on-demand, no startup initialization needed

**Acceptance Criteria**:
- [ ] No `research_agents` imports in startup
- [ ] No background trigger loop
- [ ] Backend starts cleanly

---

## Task 1.8: Write Unit Tests

**File(s)**:
- `tests/unit/agent_tests/test_research_worker.py`
- `tests/unit/agent_tests/test_agent_service_new.py`

**Type**: CODING

**Description**: Write unit tests for orchestrator and service.

**Tests for AgentResearchWorker**:
```python
async def test_worker_completes_all_phases():
    """Worker transitions through all phases."""
    # Setup mock ops service and stub workers
    # Run worker
    # Assert phases: designing → training → backtesting → assessing
    # Assert final result has success=True

async def test_worker_tracks_child_operations():
    """Worker stores child op IDs in parent metadata."""
    # Run worker
    # Assert metadata has design_op_id, training_op_id, etc.

async def test_worker_cancellation_responsive():
    """Worker responds to cancellation within 200ms."""
    # Start worker
    # Cancel after 100ms
    # Assert CancelledError raised within 200ms total

async def test_worker_propagates_child_failure():
    """Worker fails if child fails."""
    # Use failing stub worker
    # Assert worker raises exception
```

**Tests for AgentService**:
```python
async def test_trigger_creates_operation():
    """Trigger creates AGENT_RESEARCH operation."""
    # Trigger
    # Assert operation created with correct type

async def test_trigger_returns_operation_id():
    """Trigger returns operation_id for tracking."""
    # Trigger
    # Assert response has operation_id

async def test_trigger_rejects_when_active():
    """Trigger returns 409 if cycle already active."""
    # Create active operation
    # Trigger again
    # Assert triggered=False, reason=active_cycle_exists

async def test_status_returns_phase():
    """Status returns current phase from metadata."""
    # Create operation with phase=training
    # Get status
    # Assert phase=training

async def test_status_returns_idle_when_no_active():
    """Status returns idle when no active cycle."""
    # No active operations
    # Get status
    # Assert status=idle
```

**Acceptance Criteria**:
- [ ] All tests pass
- [ ] Tests use mocks for operations service
- [ ] No real API calls in unit tests

---

## Task 1.9: Integration Test

**File(s)**: `tests/integration/agent_tests/test_agent_stub_cycle.py`
**Type**: CODING

**Description**: Integration test that runs a full stub cycle.

**Implementation Notes**:
```python
# tests/integration/agent_tests/test_agent_stub_cycle.py
"""Integration test for stub research cycle."""

import pytest
import asyncio

from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import OperationStatus


@pytest.mark.integration
async def test_full_stub_cycle():
    """Full cycle with stubs completes successfully."""
    # Setup
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    # Trigger
    result = await service.trigger()
    assert result["triggered"] is True
    op_id = result["operation_id"]

    # Wait for completion (max 30 seconds)
    for _ in range(60):
        status = await service.get_status()
        if status["status"] == "idle":
            break
        await asyncio.sleep(0.5)

    # Verify completion
    op = await ops.get_operation(op_id)
    assert op.status == OperationStatus.COMPLETED
    assert op.result_summary["success"] is True
    assert "strategy_name" in op.result_summary


@pytest.mark.integration
async def test_cycle_phases_progression():
    """Cycle progresses through all phases."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    result = await service.trigger()
    op_id = result["operation_id"]

    phases_seen = set()

    for _ in range(60):
        status = await service.get_status()
        if status["status"] == "active":
            phases_seen.add(status["phase"])
        elif status["status"] == "idle":
            break
        await asyncio.sleep(0.5)

    # All phases should have been seen
    assert "designing" in phases_seen
    assert "training" in phases_seen
    assert "backtesting" in phases_seen
    assert "assessing" in phases_seen
```

**Acceptance Criteria**:
- [ ] Full stub cycle completes in <10 seconds
- [ ] All phases visible in status progression
- [ ] Operation marked COMPLETED at end

---

## Task 1.10: Fix Orchestrator Polling Pattern

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING (refactor)
**Priority**: HIGH — Current implementation violates ARCHITECTURE.md

**Problem**: Task 1.3 was implemented with sequential awaits instead of the polling loop specified in ARCHITECTURE.md. This works for in-process stubs but won't work for real distributed workers.

**Current (wrong)**:
```python
# Directly awaits each child - blocks until complete
design_result = await self.design_worker.run(operation_id)
training_result = await self.training_worker.run(...)
```

**Required (per ARCHITECTURE.md)**:
```python
while True:
    op = await self.ops.get_operation(operation_id)
    phase = op.metadata.get("phase", "idle")

    child_op_id = self._get_child_op_id(op, phase)
    child_op = await self.ops.get_operation(child_op_id)

    if child_op is None:
        await self._start_phase_worker(operation_id, phase)
    elif child_op.status == OperationStatus.RUNNING:
        await self._update_parent_progress(operation_id, child_op)
    elif child_op.status == OperationStatus.COMPLETED:
        if not await self._check_gate_and_advance(operation_id, phase, child_op):
            return {"success": False, "reason": "gate_failed"}
        if phase == "assessing":
            return {"success": True, ...}
    elif child_op.status == OperationStatus.FAILED:
        raise WorkerError(f"Child failed: {child_op.error_message}")

    await self._cancellable_sleep(POLL_INTERVAL)
```

**Key Changes**:
1. Main loop polls OperationsService instead of awaiting workers directly
2. Child workers started as separate asyncio tasks with their own operations
3. State machine advances based on child operation status
4. Poll interval configurable (5s for stubs, 300s for real workers)

**Implementation Notes**:
- Stub workers still work the same (they run as child operations)
- The orchestrator just changes HOW it waits for them
- Use `asyncio.create_task()` to start child workers
- Track child operation IDs in parent metadata

**Environment Variables**:
- `AGENT_POLL_INTERVAL`: Seconds between status checks (default: 5 for stubs, 300 for real)

**Acceptance Criteria**: ✅ COMPLETED
- [x] Orchestrator uses polling loop per ARCHITECTURE.md
- [x] Child workers started as separate operations/tasks
- [x] Parent tracks child operation IDs in metadata
- [x] Poll interval is configurable (AGENT_POLL_INTERVAL env var)
- [x] Cancellation propagates to active child
- [x] All existing tests still pass (2303 unit tests)
- [x] E2E test still shows phase progression (designing→training→backtesting→assessing→completed)

---

## Task 1.11: Implement Quality Gates

**File(s)**: `ktrdr/agents/workers/research_worker.py`, `ktrdr/agents/gates.py`
**Type**: CODING
**Priority**: HIGH — Required by ARCHITECTURE.md

**Problem**: Orchestrator proceeds through all phases regardless of results. ARCHITECTURE.md specifies quality gates between training→backtest and backtest→assessment.

**Spec (ARCHITECTURE.md)**:

Training Gate — Fail cycle if:
- Accuracy below 45%
- Final loss above 0.8
- Loss didn't decrease by at least 20%

Backtest Gate — Fail cycle if:
- Win rate below 45%
- Max drawdown above 40%
- Sharpe ratio below -0.5

**Implementation Notes**:

```python
# ktrdr/agents/gates.py already exists with check_training_gate() and check_backtest_gate()
# Just need to call them in the orchestrator

# In research_worker.py after training completes:
from ktrdr.agents.gates import check_training_gate, check_backtest_gate

passed, reason = check_training_gate(training_result)
if not passed:
    raise GateFailedError(f"Training gate failed: {reason}")

# After backtest completes:
passed, reason = check_backtest_gate(backtest_result)
if not passed:
    raise GateFailedError(f"Backtest gate failed: {reason}")
```

**Acceptance Criteria**: ✅ COMPLETED
- [x] Training gate checked after training phase
- [x] Backtest gate checked after backtest phase
- [x] Gate failure raises GateFailedError with reason
- [x] Gate failure stops cycle (doesn't proceed to next phase)
- [x] Unit tests for gate integration (5 tests in TestQualityGateIntegration)

---

## Task 1.12: Fix Cancellation Propagation

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING
**Priority**: HIGH — Current impl leaves orphan child operations

**Problem**: When parent operation is cancelled, child operation continues running.

**Spec (ARCHITECTURE.md)**:
```python
except asyncio.CancelledError:
    child_op_id = self._get_current_child_op_id(op)
    if child_op_id:
        await self.ops.cancel_operation(child_op_id, "Parent cancelled")
    raise
```

**Current Code**:
```python
except asyncio.CancelledError:
    logger.info(f"Research cycle cancelled: {operation_id}")
    raise  # Child left running!
```

**Implementation Notes**:
- Track current child operation ID in instance variable
- On cancellation, cancel the child operation before re-raising
- Child operations should also handle CancelledError properly

**Acceptance Criteria**: ✅ COMPLETED (implemented in Task 1.10)
- [x] Cancelling parent cancels active child (via `_cancel_current_child()`)
- [x] Both parent and child marked CANCELLED
- [x] No orphan operations left running (task cancelled and awaited)
- [x] Unit test verifies propagation (`test_cancellation_propagates_to_child`)

---

## Task 1.13: Complete Metadata Contract

**File(s)**:
- `ktrdr/agents/workers/research_worker.py`
- `ktrdr/agents/workers/stubs.py`
- `ktrdr/api/services/agent_service.py`

**Type**: CODING
**Priority**: MEDIUM — Status response incomplete per ARCHITECTURE.md

**Problem**: Several fields missing from metadata and status response.

**Missing from status response**:
```python
# ARCHITECTURE.md shows:
{
    "child_operation_id": "op_training_...",  # MISSING
}
```

**Missing from parent metadata**:
```python
# ARCHITECTURE.md shows these should be stored:
{
    "strategy_name": "...",
    "strategy_path": "...",
    "training_result": {...},
    "backtest_result": {...},
    "assessment_verdict": "...",
}
```

**Missing from stub assessment result**:
```python
# ARCHITECTURE.md shows:
{
    "assessment_path": "/app/strategies/.../assessment.json",  # MISSING
}
```

**Implementation Notes**:

1. In `research_worker.py`, store results in parent metadata:
```python
parent_op.metadata.parameters["strategy_name"] = design_result["strategy_name"]
parent_op.metadata.parameters["training_result"] = training_result
# etc.
```

2. In `agent_service.py`, add child_operation_id to status:
```python
# Find current child from parent metadata
child_op_id = active.metadata.parameters.get(f"{phase}_op_id")
return {
    "child_operation_id": child_op_id,
    ...
}
```

3. In `stubs.py`, add assessment_path:
```python
return {
    "assessment_path": "/app/strategies/stub_momentum_v1/assessment.json",
    ...
}
```

**Acceptance Criteria**:
- [ ] Status response includes child_operation_id when active
- [ ] Parent metadata stores strategy_name after design
- [ ] Parent metadata stores training_result after training
- [ ] Parent metadata stores backtest_result after backtest
- [ ] Parent metadata stores assessment_verdict after assessment
- [ ] Stub assessment returns assessment_path
- [ ] Unit tests verify metadata contract

---

## Milestone 1 Verification Script

```bash
#!/bin/bash
set -e

echo "=== M1: Orchestrator Shell Verification ==="

# Ensure backend is running
echo "1. Checking backend health..."
curl -sf http://localhost:8000/api/v1/health > /dev/null
echo "   Backend is healthy"

# Trigger cycle
echo ""
echo "2. Triggering cycle..."
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
echo "   Response: $RESULT"

OP_ID=$(echo $RESULT | jq -r '.operation_id')
if [ "$OP_ID" == "null" ] || [ -z "$OP_ID" ]; then
    echo "   FAIL: No operation_id returned"
    exit 1
fi
echo "   Operation ID: $OP_ID"

# Poll until complete (max 60 seconds)
echo ""
echo "3. Polling status..."
for i in {1..30}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase // .status')
    echo "   [$i] Phase: $PHASE"

    if [ "$PHASE" == "idle" ]; then
        echo "   Cycle completed!"
        break
    fi
    sleep 2
done

# Verify operation completed
echo ""
echo "4. Verifying operation status..."
OP_STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
if [ "$OP_STATUS" != "completed" ]; then
    echo "   FAIL: Operation status is '$OP_STATUS', expected 'completed'"
    exit 1
fi
echo "   PASS: Operation completed"

# Test duplicate trigger rejection
echo ""
echo "5. Testing duplicate trigger rejection..."
# First start a new cycle
RESULT1=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
TRIGGERED=$(echo $RESULT1 | jq -r '.triggered')
if [ "$TRIGGERED" != "true" ]; then
    echo "   FAIL: First trigger should succeed"
    exit 1
fi

# Try to trigger again while active
sleep 1
RESULT2=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
TRIGGERED2=$(echo $RESULT2 | jq -r '.triggered')
if [ "$TRIGGERED2" != "false" ]; then
    echo "   FAIL: Second trigger should be rejected"
    exit 1
fi
echo "   PASS: Duplicate trigger rejected"

# Wait for second cycle to complete
echo ""
echo "6. Waiting for second cycle..."
for i in {1..30}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    if [ "$(echo $STATUS | jq -r '.status')" == "idle" ]; then
        break
    fi
    sleep 2
done

# Test CLI
echo ""
echo "7. Testing CLI..."
ktrdr agent status
echo "   PASS: CLI works"

echo ""
echo "=== M1 Complete ==="
```

---

## Files Created/Modified in M1

**New files**:
```
ktrdr/agents/workers/__init__.py
ktrdr/agents/workers/stubs.py
ktrdr/agents/workers/research_worker.py
tests/unit/agent_tests/test_stub_workers.py
tests/unit/agent_tests/test_research_worker.py
tests/unit/agent_tests/test_agent_service_new.py
tests/integration/agent_tests/test_agent_stub_cycle.py
```

**Modified files**:
```
ktrdr/api/models/operations.py      # Add operation types
ktrdr/api/services/agent_service.py # Complete rewrite
ktrdr/api/endpoints/agent.py        # Simplify
ktrdr/cli/agent_commands.py         # Simplify
ktrdr/api/startup.py                # Remove research_agents
```

---

*Estimated effort: ~4-6 hours*

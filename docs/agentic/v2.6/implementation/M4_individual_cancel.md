---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
validation: ../VALIDATION.md
---

# Milestone 4: Individual Cancel

**Branch:** `feature/v2.6-m4-individual-cancel`
**Depends on:** M1 (coordinator loop)
**Goal:** User can cancel a specific research by operation_id while others continue.

---

## Task 4.1: Modify `cancel()` to Accept operation_id

**File:** `ktrdr/api/services/agent_service.py`
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** API Endpoint, State Machine

**Description:**
Change `cancel()` method signature to accept an operation_id parameter. Cancel that specific research instead of "the active one."

**Implementation Notes:**
- Change signature: `async def cancel(self, operation_id: str) -> dict`
- Validate the operation exists and is an AGENT_RESEARCH type
- Validate the operation is in a cancellable state (RUNNING, PENDING)
- Cancel via OperationsService
- Return appropriate responses for not found, not cancellable, success

**Code sketch:**
```python
@trace_service_method("agent.cancel")
async def cancel(self, operation_id: str) -> dict[str, Any]:
    """Cancel a specific research by operation_id."""

    # Get the operation
    op = await self.ops.get_operation(operation_id)

    if op is None:
        return {
            "success": False,
            "reason": "not_found",
            "message": f"Operation not found: {operation_id}",
        }

    # Verify it's an agent research
    if op.operation_type != OperationType.AGENT_RESEARCH:
        return {
            "success": False,
            "reason": "not_research",
            "message": f"Operation is not a research: {operation_id}",
        }

    # Verify it's cancellable
    if op.status not in [OperationStatus.RUNNING, OperationStatus.PENDING]:
        return {
            "success": False,
            "reason": "not_cancellable",
            "message": f"Cannot cancel {op.status.value} operation",
        }

    # Get child operation for logging
    phase = op.metadata.parameters.get("phase", "")
    child_op_id = self._get_child_op_id_for_phase(op, phase)

    # Cancel
    await self.ops.cancel_operation(operation_id, "Cancelled by user")

    logger.info(f"Research cancelled: {operation_id}, child: {child_op_id}")

    return {
        "success": True,
        "operation_id": operation_id,
        "child_cancelled": child_op_id,
        "message": "Research cancelled",
    }
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Cancel succeeds for running research
- [ ] Cancel succeeds for pending research
- [ ] Cancel returns not_found for unknown operation_id
- [ ] Cancel returns not_research for non-research operation
- [ ] Cancel returns not_cancellable for completed research

*Integration Tests:*
- [ ] DB verification: Operation status is CANCELLED after cancel

*Smoke Test:*
```bash
uv run ktrdr agent trigger --brief "test"
# Get operation ID from output
uv run ktrdr agent cancel <operation_id>
uv run ktrdr ops get <operation_id>
# Should show CANCELLED
```

**Acceptance Criteria:**
- [ ] cancel() accepts operation_id parameter
- [ ] Validates operation exists and is cancellable
- [ ] Returns appropriate error responses
- [ ] Unit tests pass

---

## Task 4.2: Update API Endpoint for cancel

**File:** `ktrdr/api/endpoints/agent.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** API Endpoint

**Description:**
Update the cancel API endpoint to accept operation_id as a path parameter.

**Implementation Notes:**
- Current endpoint might be `DELETE /agent/cancel` (no param)
- Change to `DELETE /agent/cancel/{operation_id}`
- Pass operation_id to service
- Update response model if needed

**Code sketch:**
```python
@router.delete("/cancel/{operation_id}")
async def cancel_research(
    operation_id: str,
    agent_service: AgentService = Depends(get_agent_service),
) -> dict:
    """Cancel a specific research by operation_id."""
    return await agent_service.cancel(operation_id)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Endpoint accepts operation_id path param
- [ ] Passes operation_id to service

*Integration Tests:*
- [ ] API contract: DELETE /agent/cancel/{id} works

*Smoke Test:*
```bash
curl -X DELETE http://localhost:8000/api/v1/agent/cancel/op_abc123
```

**Acceptance Criteria:**
- [ ] Endpoint accepts operation_id
- [ ] Swagger docs updated
- [ ] Unit tests pass

---

## Task 4.3: Update CLI cancel Command

**File:** `ktrdr/cli/agent.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** API Endpoint

**Description:**
Update the CLI cancel command to require an operation_id argument.

**Implementation Notes:**
- Change from `ktrdr agent cancel` (no args) to `ktrdr agent cancel <operation_id>`
- Make operation_id a required positional argument
- Update help text
- Display appropriate output for success/failure

**Code sketch:**
```python
@agent_app.command("cancel")
def cancel_research(
    operation_id: str = typer.Argument(..., help="Operation ID to cancel"),
):
    """Cancel a specific research by operation_id."""
    response = httpx.delete(f"{API_BASE}/agent/cancel/{operation_id}")
    result = response.json()

    if result.get("success"):
        console.print(f"Research cancelled: {operation_id}")
    else:
        console.print(f"[red]Cannot cancel: {result.get('message')}[/red]")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] CLI requires operation_id argument
- [ ] Displays success message on success
- [ ] Displays error message on failure

*Smoke Test:*
```bash
uv run ktrdr agent cancel
# Should show error: missing argument

uv run ktrdr agent cancel op_abc123
# Should show result
```

**Acceptance Criteria:**
- [ ] CLI accepts operation_id argument
- [ ] Help text explains the argument
- [ ] Output matches design spec

---

## Task 4.4: Track Child Tasks Per Operation

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** Background/Async, State Machine

**Description:**
Track asyncio tasks per operation for clean cancellation. When a research is cancelled, its in-process child task (design/assessment) should be cancelled too.

**Implementation Notes:**
- Change `_current_child_task` to `_child_tasks: dict[str, asyncio.Task]`
- When starting design/assessment, store: `_child_tasks[operation_id] = task`
- When research completes/fails/cancelled, remove from dict
- On cancellation, cancel the specific task

**Code sketch:**
```python
class AgentResearchWorker:
    def __init__(self, ...):
        # ... existing
        self._child_tasks: dict[str, asyncio.Task] = {}  # operation_id -> task

    async def _start_design(self, operation_id: str) -> None:
        """Start design phase, tracking the task."""
        # ... existing setup ...

        async def run_child():
            await self.design_worker.run(operation_id, model=model, brief=brief)

        task = asyncio.create_task(run_child())
        self._child_tasks[operation_id] = task  # Track by operation_id

    async def _handle_research_cancelled(self, op) -> None:
        """Handle cancellation, including child task."""
        operation_id = op.operation_id

        # Cancel child task if running
        if operation_id in self._child_tasks:
            task = self._child_tasks[operation_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self._child_tasks[operation_id]

        # ... existing cancellation logic ...

    def _cleanup_task(self, operation_id: str) -> None:
        """Remove task tracking when research completes."""
        self._child_tasks.pop(operation_id, None)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] Task tracked when design starts
- [ ] Task tracked when assessment starts
- [ ] Task cancelled when research cancelled
- [ ] Task removed on completion

*Integration Tests:*
- [ ] Cancelling research stops in-progress design

**Acceptance Criteria:**
- [ ] Child tasks tracked per operation
- [ ] Cancellation propagates to child task
- [ ] No memory leak (tasks cleaned up)
- [ ] Unit tests pass

---

## E2E Validation

### Test to Run

| Test | Purpose | Source |
|------|---------|--------|
| Individual cancel | Cancel one, others continue | New |

### Test Specification

**Test: agent/individual-cancel**

**Purpose:** Verify cancelling one research doesn't affect others.

**Duration:** ~45 seconds

**Prerequisites:**
- Backend running
- USE_STUB_WORKERS=true (or real workers)

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Trigger research A | Success | CLI |
| 2 | Trigger research B | Success | CLI |
| 3 | Trigger research C | Success | CLI |
| 4 | Wait for all in progress | All advancing | Status |
| 5 | Cancel research B | Success | CLI output |
| 6 | Check B status | CANCELLED | `ktrdr ops get B` |
| 7 | Wait for A, C | Both complete | Status |
| 8 | Check A, C status | Both COMPLETED | `ktrdr ops list` |

**Success Criteria:**
- [ ] Cancel command succeeds for B
- [ ] B is CANCELLED
- [ ] A completes successfully
- [ ] C completes successfully
- [ ] No errors in logs

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration test passes
- [ ] E2E test passes
- [ ] Quality gates pass: `make quality`
- [ ] M1 E2E tests still pass
- [ ] Branch merged to main

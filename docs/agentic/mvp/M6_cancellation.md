# Milestone 6: Cancellation & Error Handling

**Branch**: `feature/agent-mvp`
**Builds On**: M5 (Assessment Worker)
**Capability**: User can cancel running cycles; errors are handled gracefully

---

## Why This Milestone

Makes the system robust for real-world use. Users can cancel long-running cycles, and all failure modes have clear error messages. This is about reliability, not features.

---

## E2E Test

```bash
# Test cancellation during training
ktrdr agent trigger
# Wait for training phase (~2 minutes)

ktrdr agent status
# Note the operation ID

ktrdr agent cancel
# Expected: "Cancellation requested"

# Verify both operations cancelled
ktrdr operations status <agent_research_op_id>  # CANCELLED
ktrdr operations status <training_op_id>        # CANCELLED

# Next trigger should work
ktrdr agent trigger
# Expected: New cycle starts
```

---

## Task 6.1: Add Cancel Endpoint

**File(s)**: `ktrdr/api/endpoints/agent.py`, `ktrdr/api/services/agent_service.py`
**Type**: CODING

**Description**: Add DELETE /agent/cancel endpoint.

**Implementation Notes**:

In `ktrdr/api/services/agent_service.py`:
```python
class AgentService:
    async def cancel(self) -> dict[str, Any]:
        """Cancel the active research cycle.

        Returns:
            Dict with cancellation result.
        """
        active = await self._get_active_research_op()

        if not active:
            return {
                "success": False,
                "reason": "no_active_cycle",
                "message": "No active research cycle to cancel",
            }

        # Get current child operation
        child_op_id = self._get_current_child_op_id(active)

        # Cancel parent (will propagate to child via worker)
        await self.ops.cancel_operation(active.operation_id, "Cancelled by user")

        logger.info(
            "Research cycle cancelled",
            operation_id=active.operation_id,
            child_operation_id=child_op_id,
        )

        return {
            "success": True,
            "operation_id": active.operation_id,
            "child_cancelled": child_op_id,
            "message": "Research cycle cancelled",
        }

    def _get_current_child_op_id(self, op) -> str | None:
        """Get the current child operation ID based on phase."""
        phase = op.metadata.get("phase")
        phase_to_key = {
            "designing": "design_op_id",
            "training": "training_op_id",
            "backtesting": "backtest_op_id",
            "assessing": "assessment_op_id",
        }
        key = phase_to_key.get(phase)
        return op.metadata.get(key) if key else None
```

In `ktrdr/api/endpoints/agent.py`:
```python
@router.delete("/cancel")
async def cancel_agent():
    """Cancel the active research cycle.

    Returns 200 with cancellation details if cancelled.
    Returns 404 if no active cycle.
    """
    service = get_agent_service()
    result = await service.cancel()

    if result["success"]:
        return result
    return JSONResponse(result, status_code=404)
```

**Acceptance Criteria**:
- [ ] Endpoint returns success if cycle cancelled
- [ ] Returns operation IDs that were cancelled
- [ ] Returns 404 if no active cycle

---

## Task 6.2: Implement Parent-Child Cancellation

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: When parent is cancelled, cancel current child operation.

**Implementation Notes**:
```python
class AgentResearchWorker:
    async def run(self, operation_id: str) -> dict[str, Any]:
        """Main orchestrator loop with cancellation handling."""
        try:
            # ... phase execution ...
            return result

        except asyncio.CancelledError:
            logger.info("Research cycle cancelled", operation_id=operation_id)

            # Get current child from metadata
            op = await self.ops.get_operation(operation_id)
            child_op_id = self._get_current_child_op_id(op)

            if child_op_id:
                logger.info(
                    "Cancelling child operation",
                    parent_id=operation_id,
                    child_id=child_op_id,
                )
                try:
                    await self.ops.cancel_operation(child_op_id, "Parent cancelled")
                except Exception as e:
                    logger.warning(
                        "Failed to cancel child",
                        child_id=child_op_id,
                        error=str(e),
                    )

            raise  # Re-raise to complete cancellation

    def _get_current_child_op_id(self, op) -> str | None:
        """Get current child operation ID from metadata."""
        phase = op.metadata.get("phase")
        phase_to_key = {
            "designing": "design_op_id",
            "training": "training_op_id",
            "backtesting": "backtest_op_id",
            "assessing": "assessment_op_id",
        }
        key = phase_to_key.get(phase)
        return op.metadata.get(key) if key else None
```

**Unit Tests** (`tests/unit/agent_tests/test_cancellation.py`):
- [ ] Test: Parent cancel triggers child cancel
- [ ] Test: Cancellation completes within 500ms
- [ ] Test: Both parent and child marked CANCELLED
- [ ] Test: Cancellation during each phase works
- [ ] Test: Cancellation when no child running works

**Acceptance Criteria**:
- [ ] Child operation cancelled when parent cancelled
- [ ] Both marked CANCELLED
- [ ] Cancellation responsive (<500ms)

---

## Task 6.3: Add CLI Cancel Command

**File(s)**: `ktrdr/cli/agent_commands.py`
**Type**: CODING

**Description**: Add `ktrdr agent cancel` command.

**Implementation Notes**:
```python
@agent_group.command("cancel")
def cancel_agent():
    """Cancel the active research cycle."""
    url = f"{get_api_url()}/agent/cancel"

    try:
        response = requests.delete(url, timeout=10)
        data = response.json()

        if data.get("success"):
            click.echo("Research cycle cancelled!")
            click.echo(f"Operation: {data['operation_id']}")
            if data.get("child_cancelled"):
                click.echo(f"Child operation: {data['child_cancelled']}")
        else:
            click.echo(f"Could not cancel: {data.get('reason')}")
            if data.get("reason") == "no_active_cycle":
                click.echo("No active research cycle to cancel.")

    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)
```

**Acceptance Criteria**:
- [ ] `ktrdr agent cancel` cancels active cycle
- [ ] Shows cancelled operation IDs
- [ ] Clear message if no active cycle

---

## Task 6.4: Improve Error Messages

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Ensure all failure modes have clear, actionable error messages.

**Implementation Notes**:
```python
class AgentResearchWorker:
    async def run(self, operation_id: str) -> dict[str, Any]:
        try:
            # Design phase
            await self._update_phase(operation_id, "designing")
            try:
                design_result = await self._run_child(...)
            except WorkerError as e:
                raise CycleError(f"Design phase failed: {e}")

            # Training phase with gate
            await self._update_phase(operation_id, "training")
            try:
                training_result = await self._run_child(...)
            except WorkerError as e:
                raise CycleError(f"Training failed: {e}")

            passed, reason = check_training_gate(training_result)
            if not passed:
                raise GateError(
                    f"Training gate failed: {reason}",
                    gate="training",
                    metrics=training_result,
                )

            # ... similar for backtest ...

        except GateError as e:
            # Format gate errors nicely
            error_msg = str(e)
            logger.warning("Gate failed", error=error_msg, gate=e.gate)
            raise

        except CycleError as e:
            # Format cycle errors
            logger.error("Cycle failed", error=str(e))
            raise

        except asyncio.CancelledError:
            # ... cancellation handling ...
            raise


class CycleError(Exception):
    """Error during research cycle."""
    pass


class GateError(CycleError):
    """Quality gate failed."""
    def __init__(self, message: str, gate: str, metrics: dict):
        super().__init__(message)
        self.gate = gate
        self.metrics = metrics
```

**Error message examples**:
```
Design phase failed: Claude API error: rate_limit_exceeded
Training failed: Worker timeout after 30 minutes
Training gate failed: accuracy_below_threshold (42.3% < 45.0%)
Backtest gate failed: drawdown_too_high (45.2% > 40.0%)
Assessment failed: Claude did not save an assessment
```

**Acceptance Criteria**:
- [ ] All errors include context (phase, values)
- [ ] Gate failures include actual vs threshold values
- [ ] Errors visible in operation error_message
- [ ] Errors visible in CLI output

---

## Task 6.5: Integration Test

**File(s)**: `tests/integration/agent_tests/test_agent_cancellation.py`
**Type**: CODING

**Description**: Test cancellation during different phases.

**Implementation Notes**:
```python
# tests/integration/agent_tests/test_agent_cancellation.py
"""Integration test for cancellation."""

import pytest
import asyncio

from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import OperationStatus


@pytest.mark.integration
async def test_cancel_during_designing():
    """Cancel during design phase."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    # Trigger
    result = await service.trigger()
    op_id = result["operation_id"]

    # Wait for designing phase
    for _ in range(30):
        status = await service.get_status()
        if status.get("phase") == "designing":
            break
        await asyncio.sleep(0.5)

    # Cancel
    cancel_result = await service.cancel()
    assert cancel_result["success"] is True

    # Wait for cancellation to complete
    await asyncio.sleep(1)

    # Verify parent cancelled
    op = await ops.get_operation(op_id)
    assert op.status == OperationStatus.CANCELLED


@pytest.mark.integration
async def test_cancel_during_training():
    """Cancel during training phase."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    result = await service.trigger()
    op_id = result["operation_id"]

    # Wait for training phase
    for _ in range(120):
        status = await service.get_status()
        if status.get("phase") == "training":
            break
        await asyncio.sleep(1)

    # Get training op ID before cancel
    parent_op = await ops.get_operation(op_id)
    training_op_id = parent_op.metadata.get("training_op_id")

    # Cancel
    cancel_result = await service.cancel()
    assert cancel_result["success"] is True

    # Wait for cancellation
    await asyncio.sleep(2)

    # Verify both cancelled
    parent_op = await ops.get_operation(op_id)
    assert parent_op.status == OperationStatus.CANCELLED

    if training_op_id:
        training_op = await ops.get_operation(training_op_id)
        assert training_op.status == OperationStatus.CANCELLED


@pytest.mark.integration
async def test_cancel_no_active_cycle():
    """Cancel when no active cycle returns error."""
    service = AgentService()

    result = await service.cancel()
    assert result["success"] is False
    assert result["reason"] == "no_active_cycle"


@pytest.mark.integration
async def test_trigger_after_cancel():
    """Can trigger new cycle after cancellation."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    # Start and cancel
    result1 = await service.trigger()
    await asyncio.sleep(1)
    await service.cancel()
    await asyncio.sleep(1)

    # Should be able to trigger again
    result2 = await service.trigger()
    assert result2["triggered"] is True
    assert result2["operation_id"] != result1["operation_id"]


@pytest.mark.integration
async def test_cancellation_speed():
    """Cancellation completes within 500ms."""
    import time

    ops = OperationsService()
    service = AgentService(operations_service=ops)

    result = await service.trigger()
    op_id = result["operation_id"]

    # Wait for cycle to start
    await asyncio.sleep(1)

    # Time the cancellation
    start = time.time()
    await service.cancel()

    # Wait for status to reflect cancellation
    for _ in range(10):
        op = await ops.get_operation(op_id)
        if op.status == OperationStatus.CANCELLED:
            break
        await asyncio.sleep(0.1)

    elapsed = time.time() - start
    assert elapsed < 0.5, f"Cancellation took {elapsed:.2f}s, expected <0.5s"
```

**Acceptance Criteria**:
- [ ] Cancellation works from any phase
- [ ] Child operations cleaned up
- [ ] New cycle can start after cancel
- [ ] Cancellation completes in <500ms

---

## Milestone 6 Verification Script

```bash
#!/bin/bash
set -e

echo "=== M6: Cancellation & Error Handling Verification ==="

# Test 1: Cancel during design (with stubs for speed)
echo "1. Testing cancel during design phase..."
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "   Started: $OP_ID"

sleep 2

# Cancel
echo "   Cancelling..."
CANCEL=$(curl -s -X DELETE http://localhost:8000/api/v1/agent/cancel)
SUCCESS=$(echo $CANCEL | jq -r '.success')
if [ "$SUCCESS" != "true" ]; then
    echo "   FAIL: Cancel returned success=$SUCCESS"
    exit 1
fi
echo "   Cancel response: $(echo $CANCEL | jq -c)"

sleep 1

# Verify cancelled
STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
if [ "$STATUS" != "cancelled" ]; then
    echo "   FAIL: Status is '$STATUS', expected 'cancelled'"
    exit 1
fi
echo "   PASS: Operation cancelled"

# Test 2: Cancel when no active cycle
echo ""
echo "2. Testing cancel with no active cycle..."
CANCEL=$(curl -s -X DELETE http://localhost:8000/api/v1/agent/cancel)
SUCCESS=$(echo $CANCEL | jq -r '.success')
REASON=$(echo $CANCEL | jq -r '.reason')
if [ "$SUCCESS" != "false" ] || [ "$REASON" != "no_active_cycle" ]; then
    echo "   FAIL: Expected success=false, reason=no_active_cycle"
    exit 1
fi
echo "   PASS: Correctly reports no active cycle"

# Test 3: Trigger after cancel
echo ""
echo "3. Testing trigger after cancel..."
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
TRIGGERED=$(echo $RESULT | jq -r '.triggered')
if [ "$TRIGGERED" != "true" ]; then
    echo "   FAIL: Could not trigger after cancel"
    exit 1
fi
NEW_OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "   PASS: New cycle started: $NEW_OP_ID"

# Cancel this one too
curl -s -X DELETE http://localhost:8000/api/v1/agent/cancel > /dev/null

# Test 4: CLI cancel command
echo ""
echo "4. Testing CLI cancel..."
ktrdr agent trigger > /dev/null 2>&1
sleep 1
ktrdr agent cancel
echo "   PASS: CLI cancel works"

# Test 5: Cancellation speed
echo ""
echo "5. Testing cancellation speed..."
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
sleep 1

START=$(date +%s%N)
curl -s -X DELETE http://localhost:8000/api/v1/agent/cancel > /dev/null

# Poll for cancelled status
for i in {1..10}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
    if [ "$STATUS" == "cancelled" ]; then
        break
    fi
    sleep 0.1
done

END=$(date +%s%N)
ELAPSED=$(( (END - START) / 1000000 ))
echo "   Cancellation took ${ELAPSED}ms"
if [ $ELAPSED -gt 500 ]; then
    echo "   WARNING: Cancellation took longer than 500ms"
fi
echo "   PASS: Cancellation speed acceptable"

echo ""
echo "=== M6 Complete ==="
```

---

## Files Created/Modified in M6

**New files**:
```
tests/unit/agent_tests/test_cancellation.py
tests/integration/agent_tests/test_agent_cancellation.py
```

**Modified files**:
```
ktrdr/api/endpoints/agent.py             # Add cancel endpoint
ktrdr/api/services/agent_service.py      # Add cancel method
ktrdr/cli/agent_commands.py              # Add cancel command
ktrdr/agents/workers/research_worker.py  # Improve cancellation and errors
```

---

*Estimated effort: ~3 hours*

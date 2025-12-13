# Milestone 3: Training Integration

**Branch**: `feature/agent-mvp`
**Builds On**: M2 (Design Worker)
**Capability**: Real training runs after design, with quality gate

---

## Why This Milestone

Connects the orchestrator to the existing training infrastructure. After design creates a strategy, real training runs. The training gate evaluates results and fails the cycle if quality is poor.

---

## E2E Test

```bash
ktrdr agent trigger
# Wait for training to complete (~5-10 minutes)

ktrdr agent status
# Expected: Phase = backtesting (if gate passed) or status = idle with failed (if gate failed)

ktrdr operations list --type training
# Expected: Training operation with COMPLETED status

# If gate failed:
ktrdr operations status <op_id>
# Expected: Error shows "Training gate failed: <reason>"
```

---

## Task 3.1: Create Training Worker Adapter

**File(s)**: `ktrdr/agents/workers/training_adapter.py`
**Type**: CODING

**Description**: Create adapter that starts training via TrainingService and polls for completion.

**Implementation Notes**:
```python
# ktrdr/agents/workers/training_adapter.py
"""Training worker adapter for agent orchestrator."""

import asyncio
from typing import Any

import yaml

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationStatus
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.services.training_service import TrainingService

logger = get_logger(__name__)


class WorkerError(Exception):
    """Error during worker execution."""
    pass


class TrainingWorkerAdapter:
    """Adapts TrainingService for orchestrator use.

    This adapter:
    1. Starts training via TrainingService
    2. Polls the training operation until complete
    3. Returns training metrics for gate evaluation
    """

    POLL_INTERVAL = 10.0  # seconds between status checks

    def __init__(
        self,
        operations_service: OperationsService,
        training_service: TrainingService | None = None,
    ):
        self.ops = operations_service
        self.training = training_service or TrainingService()

    async def run(
        self,
        parent_operation_id: str,
        strategy_path: str,
    ) -> dict[str, Any]:
        """Run training phase.

        Args:
            parent_operation_id: Parent AGENT_RESEARCH operation ID.
            strategy_path: Path to strategy YAML file.

        Returns:
            Training metrics including accuracy, loss, model_path.
        """
        logger.info(
            "Starting training phase",
            parent_operation_id=parent_operation_id,
            strategy_path=strategy_path,
        )

        # Load strategy config
        config = self._load_strategy_config(strategy_path)

        # Start training
        training_result = await self.training.start_training(
            strategy_name=config["name"],
            symbol=config.get("symbol", "EURUSD"),
            timeframe=config.get("timeframe", "1h"),
            # Additional params from strategy config
            epochs=config.get("training", {}).get("epochs", 50),
            batch_size=config.get("training", {}).get("batch_size", 32),
        )

        training_op_id = training_result["operation_id"]
        logger.info("Training started", training_op_id=training_op_id)

        # Poll until complete
        try:
            result = await self._poll_until_complete(training_op_id)
            return result
        except asyncio.CancelledError:
            # Cancel the training operation too
            await self.ops.cancel_operation(training_op_id, "Parent cancelled")
            raise

    async def _poll_until_complete(self, training_op_id: str) -> dict[str, Any]:
        """Poll training operation until it completes."""
        while True:
            op = await self.ops.get_operation(training_op_id)

            if op.status == OperationStatus.COMPLETED:
                logger.info(
                    "Training completed",
                    training_op_id=training_op_id,
                    accuracy=op.result_summary.get("accuracy"),
                )
                return {
                    "success": True,
                    "training_op_id": training_op_id,
                    "accuracy": op.result_summary.get("accuracy", 0),
                    "final_loss": op.result_summary.get("final_loss", 1.0),
                    "initial_loss": op.result_summary.get("initial_loss", 1.0),
                    "model_path": op.result_summary.get("model_path"),
                }

            if op.status == OperationStatus.FAILED:
                error = op.error_message or "Unknown error"
                logger.error(
                    "Training failed",
                    training_op_id=training_op_id,
                    error=error,
                )
                raise WorkerError(f"Training failed: {error}")

            if op.status == OperationStatus.CANCELLED:
                raise asyncio.CancelledError("Training was cancelled")

            # Log progress
            if op.progress:
                logger.debug(
                    "Training progress",
                    training_op_id=training_op_id,
                    percentage=op.progress.percentage,
                    step=op.progress.current_step,
                )

            await asyncio.sleep(self.POLL_INTERVAL)

    def _load_strategy_config(self, strategy_path: str) -> dict[str, Any]:
        """Load strategy configuration from YAML file."""
        with open(strategy_path) as f:
            return yaml.safe_load(f)
```

**Unit Tests** (`tests/unit/agent_tests/test_training_adapter.py`):
- [ ] Test: Polls until COMPLETED status returns metrics
- [ ] Test: Raises WorkerError on FAILED status
- [ ] Test: Raises CancelledError on CANCELLED status
- [ ] Test: Passes strategy config to TrainingService
- [ ] Test: Cancels child on parent cancellation
- [ ] Test: Returns training_op_id in result

**Acceptance Criteria**:
- [ ] Starts real training via TrainingService
- [ ] Polls training operation until complete
- [ ] Returns training metrics (accuracy, loss, model_path)
- [ ] Cancels training if parent cancelled

---

## Task 3.2: Implement Training Gate

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Add training gate evaluation after training completes.

**Implementation Notes**:
```python
from ktrdr.agents.gates import check_training_gate

class AgentResearchWorker:

    async def run(self, operation_id: str) -> dict[str, Any]:
        # ... design phase ...

        # Phase 2: Training
        await self._update_phase(operation_id, "training")
        training_result = await self._run_child(
            operation_id, "training", self.training_worker.run,
            operation_id, design_result["strategy_path"]
        )

        # Store training results
        await self.ops.update_operation_metadata(operation_id, {
            "training_result": {
                "accuracy": training_result["accuracy"],
                "final_loss": training_result["final_loss"],
            },
            "model_path": training_result["model_path"],
        })

        # Check training gate
        passed, reason = check_training_gate(training_result)
        if not passed:
            raise GateFailedError(f"Training gate failed: {reason}")

        logger.info("Training gate passed", reason=reason)

        # Continue to backtest...


class GateFailedError(Exception):
    """Quality gate failed."""
    pass
```

**Unit Tests**:
- [ ] Test: Gate failure raises GateFailedError with reason
- [ ] Test: Gate pass allows progression to backtesting
- [ ] Test: Gate reason includes threshold values (e.g., "42% < 45%")
- [ ] Test: Training result stored in parent metadata

**Acceptance Criteria**:
- [ ] Gate evaluated after training completes
- [ ] Failed gate raises clear exception
- [ ] Passed gate advances to backtesting
- [ ] Training metrics stored in parent metadata

---

## Task 3.3: Wire Real Training into Orchestrator

**File(s)**: `ktrdr/api/services/agent_service.py`
**Type**: CODING

**Description**: Replace stub training worker with real adapter.

**Implementation Notes**:
```python
from ktrdr.agents.workers.design_worker import AgentDesignWorker
from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter
from ktrdr.agents.workers.stubs import StubBacktestWorker, StubAssessmentWorker

class AgentService:
    def _get_worker(self) -> AgentResearchWorker:
        if self._worker is None:
            self._worker = AgentResearchWorker(
                operations_service=self.ops,
                design_worker=AgentDesignWorker(self.ops),
                training_worker=TrainingWorkerAdapter(self.ops),  # Real training
                backtest_worker=StubBacktestWorker(),             # Still stub
                assessment_worker=StubAssessmentWorker(),         # Still stub
            )
        return self._worker
```

**Acceptance Criteria**:
- [ ] Real training runs after design
- [ ] Training operation visible in operations list
- [ ] Parent metadata includes training_op_id and training_result

---

## Task 3.4: Integration Test

**File(s)**: `tests/integration/agent_tests/test_agent_training_gate.py`
**Type**: CODING

**Description**: Test training integration and gate evaluation.

**Implementation Notes**:
```python
# tests/integration/agent_tests/test_agent_training_gate.py
"""Integration test for training with gate."""

import os
import pytest
import asyncio

from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import OperationStatus


@pytest.mark.integration
@pytest.mark.slow  # Training takes time
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
async def test_training_runs_after_design():
    """Training phase runs after successful design."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    result = await service.trigger()
    op_id = result["operation_id"]

    # Wait for training or beyond
    phases_seen = set()
    for _ in range(300):  # Up to 5 minutes
        status = await service.get_status()
        phase = status.get("phase", "")
        phases_seen.add(phase)

        if phase in ["backtesting", "assessing"] or status.get("status") == "idle":
            break
        await asyncio.sleep(2)

    # Verify training phase was hit
    assert "training" in phases_seen, f"Training phase not seen. Phases: {phases_seen}"

    # Verify training operation exists
    op = await ops.get_operation(op_id)
    training_op_id = op.metadata.get("training_op_id")
    assert training_op_id is not None, "No training_op_id in metadata"


@pytest.mark.integration
async def test_training_gate_failure_stops_cycle():
    """Training gate failure fails the entire cycle."""
    # This test requires a strategy that produces poor training results
    # We'll mock the training result for testing

    from ktrdr.agents.gates import check_training_gate

    # Simulate poor training results
    poor_results = {
        "accuracy": 0.35,  # Below 45% threshold
        "final_loss": 0.9,
        "initial_loss": 0.95,
    }

    passed, reason = check_training_gate(poor_results)
    assert passed is False
    assert "accuracy_below_threshold" in reason
    assert "35%" in reason
    assert "45%" in reason


@pytest.mark.integration
async def test_training_gate_pass_continues():
    """Training gate pass allows continuation."""
    from ktrdr.agents.gates import check_training_gate

    good_results = {
        "accuracy": 0.65,  # Above 45%
        "final_loss": 0.35,  # Below 0.8
        "initial_loss": 0.85,  # >20% decrease
    }

    passed, reason = check_training_gate(good_results)
    assert passed is True
    assert reason == "passed"
```

**Acceptance Criteria**:
- [ ] Gate pass/fail correctly evaluated
- [ ] Clear error message on gate failure includes values
- [ ] Training metrics visible in operation metadata
- [ ] Training operation visible in operations list

---

## Milestone 3 Verification Script

```bash
#!/bin/bash
set -e

echo "=== M3: Training Integration Verification ==="

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    exit 1
fi

# Trigger cycle
echo "1. Triggering cycle..."
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "   Operation: $OP_ID"

# Wait for training phase
echo ""
echo "2. Waiting for training phase..."
for i in {1..60}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase')

    if [ "$PHASE" == "training" ]; then
        echo "   Entered training phase"
        break
    fi
    echo "   [$i] Phase: $PHASE"
    sleep 2
done

# Wait for training to complete
echo ""
echo "3. Waiting for training to complete..."
for i in {1..180}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase // .status')

    if [ "$PHASE" == "backtesting" ] || [ "$PHASE" == "assessing" ]; then
        echo "   Training complete! Gate PASSED. Now in phase: $PHASE"
        break
    fi

    if [ "$PHASE" == "idle" ]; then
        # Check if failed
        OP_STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
        if [ "$OP_STATUS" == "failed" ]; then
            ERROR=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.error_message')
            if [[ "$ERROR" == *"gate"* ]]; then
                echo "   Training gate FAILED (expected if poor results): $ERROR"
            else
                echo "   Cycle failed: $ERROR"
            fi
        fi
        break
    fi

    echo "   [$i] Phase: $PHASE"
    sleep 3
done

# Check training operation
echo ""
echo "4. Checking training operation..."
OP_DATA=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID)
TRAINING_OP_ID=$(echo $OP_DATA | jq -r '.data.metadata.training_op_id')

if [ "$TRAINING_OP_ID" != "null" ] && [ -n "$TRAINING_OP_ID" ]; then
    echo "   Training operation: $TRAINING_OP_ID"
    TRAINING_OP=$(curl -s http://localhost:8000/api/v1/operations/$TRAINING_OP_ID)
    TRAINING_STATUS=$(echo $TRAINING_OP | jq -r '.data.status')
    echo "   Training status: $TRAINING_STATUS"

    if [ "$TRAINING_STATUS" == "completed" ]; then
        ACCURACY=$(echo $TRAINING_OP | jq -r '.data.result_summary.accuracy')
        LOSS=$(echo $TRAINING_OP | jq -r '.data.result_summary.final_loss')
        echo "   Accuracy: $ACCURACY"
        echo "   Final loss: $LOSS"
    fi
else
    echo "   No training operation found (may have failed before training)"
fi

# List training operations
echo ""
echo "5. Training operations list:"
curl -s "http://localhost:8000/api/v1/operations?type=training&limit=3" | jq '.data[] | {id: .operation_id, status: .status}'

echo ""
echo "=== M3 Complete ==="
```

---

## Files Created/Modified in M3

**New files**:
```
ktrdr/agents/workers/training_adapter.py
tests/unit/agent_tests/test_training_adapter.py
tests/integration/agent_tests/test_agent_training_gate.py
```

**Modified files**:
```
ktrdr/agents/workers/research_worker.py  # Add gate check, store training result
ktrdr/api/services/agent_service.py      # Use real training adapter
```

---

*Estimated effort: ~3-4 hours*

# Milestone 4: Backtest Integration

**Branch**: `feature/agent-mvp`
**Builds On**: M3 (Training Integration)
**Capability**: Real backtest runs after training passes gate

---

## Why This Milestone

Connects the orchestrator to the existing backtesting infrastructure. After training passes the gate, real backtesting runs on held-out data. The backtest gate evaluates results before assessment.

---

## E2E Test

```bash
ktrdr agent trigger
# Wait for full cycle through backtest (~15-20 minutes total)

ktrdr agent status
# Expected: Phase = assessing (if gate passed) or status = failed (if gate failed)

ktrdr operations list --type backtesting
# Expected: Backtest operation with COMPLETED status
```

---

## Task 4.1: Create Backtest Worker Adapter

**File(s)**: `ktrdr/agents/workers/backtest_adapter.py`
**Type**: CODING

**Description**: Create adapter that starts backtest via BacktestService and polls for completion.

**Implementation Notes**:
```python
# ktrdr/agents/workers/backtest_adapter.py
"""Backtest worker adapter for agent orchestrator."""

import asyncio
from typing import Any

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationStatus
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.services.backtest_service import BacktestService

logger = get_logger(__name__)


class WorkerError(Exception):
    """Error during worker execution."""
    pass


class BacktestWorkerAdapter:
    """Adapts BacktestService for orchestrator use.

    This adapter:
    1. Starts backtest via BacktestService
    2. Polls the backtest operation until complete
    3. Returns backtest metrics for gate evaluation
    """

    POLL_INTERVAL = 10.0  # seconds between status checks

    def __init__(
        self,
        operations_service: OperationsService,
        backtest_service: BacktestService | None = None,
    ):
        self.ops = operations_service
        self.backtest = backtest_service or BacktestService()

    async def run(
        self,
        parent_operation_id: str,
        model_path: str,
    ) -> dict[str, Any]:
        """Run backtest phase.

        Args:
            parent_operation_id: Parent AGENT_RESEARCH operation ID.
            model_path: Path to trained model.

        Returns:
            Backtest metrics including sharpe_ratio, win_rate, max_drawdown.
        """
        logger.info(
            "Starting backtest phase",
            parent_operation_id=parent_operation_id,
            model_path=model_path,
        )

        # Get parent operation for strategy info
        parent_op = await self.ops.get_operation(parent_operation_id)
        strategy_name = parent_op.metadata.get("strategy_name")
        symbol = parent_op.metadata.get("symbol", "EURUSD")
        timeframe = parent_op.metadata.get("timeframe", "1h")

        # Start backtest
        backtest_result = await self.backtest.start_backtest(
            model_path=model_path,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            # Use held-out period (different from training)
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        backtest_op_id = backtest_result["operation_id"]
        logger.info("Backtest started", backtest_op_id=backtest_op_id)

        # Poll until complete
        try:
            result = await self._poll_until_complete(backtest_op_id)
            return result
        except asyncio.CancelledError:
            # Cancel the backtest operation too
            await self.ops.cancel_operation(backtest_op_id, "Parent cancelled")
            raise

    async def _poll_until_complete(self, backtest_op_id: str) -> dict[str, Any]:
        """Poll backtest operation until it completes."""
        while True:
            op = await self.ops.get_operation(backtest_op_id)

            if op.status == OperationStatus.COMPLETED:
                logger.info(
                    "Backtest completed",
                    backtest_op_id=backtest_op_id,
                    sharpe_ratio=op.result_summary.get("sharpe_ratio"),
                    win_rate=op.result_summary.get("win_rate"),
                )
                return {
                    "success": True,
                    "backtest_op_id": backtest_op_id,
                    "sharpe_ratio": op.result_summary.get("sharpe_ratio", 0),
                    "win_rate": op.result_summary.get("win_rate", 0),
                    "max_drawdown": op.result_summary.get("max_drawdown", 1.0),
                    "total_return": op.result_summary.get("total_return", 0),
                    "total_trades": op.result_summary.get("total_trades", 0),
                }

            if op.status == OperationStatus.FAILED:
                error = op.error_message or "Unknown error"
                logger.error(
                    "Backtest failed",
                    backtest_op_id=backtest_op_id,
                    error=error,
                )
                raise WorkerError(f"Backtest failed: {error}")

            if op.status == OperationStatus.CANCELLED:
                raise asyncio.CancelledError("Backtest was cancelled")

            # Log progress
            if op.progress:
                logger.debug(
                    "Backtest progress",
                    backtest_op_id=backtest_op_id,
                    percentage=op.progress.percentage,
                    step=op.progress.current_step,
                )

            await asyncio.sleep(self.POLL_INTERVAL)
```

**Unit Tests** (`tests/unit/agent_tests/test_backtest_adapter.py`):
- [ ] Test: Polls until COMPLETED status returns metrics
- [ ] Test: Raises WorkerError on FAILED status
- [ ] Test: Raises CancelledError on CANCELLED status
- [ ] Test: Passes model_path to BacktestService
- [ ] Test: Cancels child on parent cancellation
- [ ] Test: Returns all expected metrics (sharpe, win_rate, drawdown)

**Acceptance Criteria**:
- [ ] Starts real backtest via BacktestService
- [ ] Polls backtest operation until complete
- [ ] Returns backtest metrics (sharpe_ratio, win_rate, max_drawdown)
- [ ] Cancels backtest if parent cancelled

---

## Task 4.2: Implement Backtest Gate

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Add backtest gate evaluation after backtest completes.

**Implementation Notes**:
```python
from ktrdr.agents.gates import check_training_gate, check_backtest_gate

class AgentResearchWorker:

    async def run(self, operation_id: str) -> dict[str, Any]:
        # ... design and training phases ...

        # Phase 3: Backtest
        await self._update_phase(operation_id, "backtesting")
        backtest_result = await self._run_child(
            operation_id, "backtest", self.backtest_worker.run,
            operation_id, training_result["model_path"]
        )

        # Store backtest results
        await self.ops.update_operation_metadata(operation_id, {
            "backtest_result": {
                "sharpe_ratio": backtest_result["sharpe_ratio"],
                "win_rate": backtest_result["win_rate"],
                "max_drawdown": backtest_result["max_drawdown"],
                "total_return": backtest_result["total_return"],
            },
        })

        # Check backtest gate
        passed, reason = check_backtest_gate(backtest_result)
        if not passed:
            raise GateFailedError(f"Backtest gate failed: {reason}")

        logger.info("Backtest gate passed", reason=reason)

        # Continue to assessment...
```

**Unit Tests**:
- [ ] Test: Gate failure raises GateFailedError with reason
- [ ] Test: Gate pass allows progression to assessing
- [ ] Test: Gate reason includes threshold values
- [ ] Test: Backtest result stored in parent metadata

**Acceptance Criteria**:
- [ ] Gate evaluated after backtest completes
- [ ] Failed gate raises clear exception
- [ ] Passed gate advances to assessing
- [ ] Backtest metrics stored in parent metadata

---

## Task 4.3: Wire Real Backtest into Orchestrator

**File(s)**: `ktrdr/api/services/agent_service.py`
**Type**: CODING

**Description**: Replace stub backtest worker with real adapter.

**Implementation Notes**:
```python
from ktrdr.agents.workers.design_worker import AgentDesignWorker
from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter
from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter
from ktrdr.agents.workers.stubs import StubAssessmentWorker

class AgentService:
    def _get_worker(self) -> AgentResearchWorker:
        if self._worker is None:
            self._worker = AgentResearchWorker(
                operations_service=self.ops,
                design_worker=AgentDesignWorker(self.ops),
                training_worker=TrainingWorkerAdapter(self.ops),
                backtest_worker=BacktestWorkerAdapter(self.ops),  # Real backtest
                assessment_worker=StubAssessmentWorker(),         # Still stub
            )
        return self._worker
```

**Acceptance Criteria**:
- [ ] Real backtest runs after training gate passes
- [ ] Backtest operation visible in operations list
- [ ] Parent metadata includes backtest_op_id and backtest_result

---

## Task 4.4: Integration Test

**File(s)**: `tests/integration/agent_tests/test_agent_backtest_gate.py`
**Type**: CODING

**Description**: Test backtest integration and gate evaluation.

**Implementation Notes**:
```python
# tests/integration/agent_tests/test_agent_backtest_gate.py
"""Integration test for backtest with gate."""

import os
import pytest
import asyncio

from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import OperationStatus
from ktrdr.agents.gates import check_backtest_gate


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
async def test_backtest_runs_after_training():
    """Backtest phase runs after training gate passes."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    result = await service.trigger()
    op_id = result["operation_id"]

    # Wait for backtest or beyond
    phases_seen = set()
    for _ in range(600):  # Up to 10 minutes
        status = await service.get_status()
        phase = status.get("phase", "")
        phases_seen.add(phase)

        if phase == "assessing" or status.get("status") == "idle":
            break
        await asyncio.sleep(2)

    # Verify backtest phase was hit (if training passed)
    op = await ops.get_operation(op_id)
    if op.status == OperationStatus.COMPLETED or "assessing" in phases_seen:
        assert "backtesting" in phases_seen, f"Backtest phase not seen. Phases: {phases_seen}"


@pytest.mark.integration
async def test_backtest_gate_failure():
    """Backtest gate failure correctly identifies poor results."""
    poor_results = {
        "sharpe_ratio": -1.0,  # Below -0.5 threshold
        "win_rate": 0.35,      # Below 45% threshold
        "max_drawdown": 0.55,  # Above 40% threshold
    }

    passed, reason = check_backtest_gate(poor_results)
    assert passed is False
    # Should fail on one of the thresholds
    assert any(x in reason for x in ["win_rate", "sharpe", "drawdown"])


@pytest.mark.integration
async def test_backtest_gate_pass():
    """Backtest gate pass with good results."""
    good_results = {
        "sharpe_ratio": 1.2,
        "win_rate": 0.55,
        "max_drawdown": 0.15,
    }

    passed, reason = check_backtest_gate(good_results)
    assert passed is True
    assert reason == "passed"
```

**Acceptance Criteria**:
- [ ] Gate pass/fail correctly evaluated
- [ ] Clear error message on gate failure includes values
- [ ] Backtest metrics visible in operation metadata
- [ ] Backtest operation visible in operations list

---

## Milestone 4 Verification Script

```bash
#!/bin/bash
set -e

echo "=== M4: Backtest Integration Verification ==="

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

# Wait for backtest phase
echo ""
echo "2. Waiting for backtest phase..."
for i in {1..300}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase // .status')

    if [ "$PHASE" == "backtesting" ]; then
        echo "   Entered backtest phase"
        break
    fi

    if [ "$PHASE" == "assessing" ] || [ "$PHASE" == "idle" ]; then
        echo "   Already past backtesting (phase: $PHASE)"
        break
    fi

    echo "   [$i] Phase: $PHASE"
    sleep 3
done

# Wait for backtest to complete
echo ""
echo "3. Waiting for backtest to complete..."
for i in {1..120}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase // .status')

    if [ "$PHASE" == "assessing" ]; then
        echo "   Backtest complete! Gate PASSED. Now in phase: assessing"
        break
    fi

    if [ "$PHASE" == "idle" ]; then
        OP_STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
        if [ "$OP_STATUS" == "failed" ]; then
            ERROR=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.error_message')
            echo "   Cycle failed: $ERROR"
        elif [ "$OP_STATUS" == "completed" ]; then
            echo "   Cycle completed!"
        fi
        break
    fi

    echo "   [$i] Phase: $PHASE"
    sleep 3
done

# Check backtest operation
echo ""
echo "4. Checking backtest operation..."
OP_DATA=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID)
BACKTEST_OP_ID=$(echo $OP_DATA | jq -r '.data.metadata.backtest_op_id')

if [ "$BACKTEST_OP_ID" != "null" ] && [ -n "$BACKTEST_OP_ID" ]; then
    echo "   Backtest operation: $BACKTEST_OP_ID"
    BACKTEST_OP=$(curl -s http://localhost:8000/api/v1/operations/$BACKTEST_OP_ID)
    BACKTEST_STATUS=$(echo $BACKTEST_OP | jq -r '.data.status')
    echo "   Backtest status: $BACKTEST_STATUS"

    if [ "$BACKTEST_STATUS" == "completed" ]; then
        SHARPE=$(echo $BACKTEST_OP | jq -r '.data.result_summary.sharpe_ratio')
        WIN_RATE=$(echo $BACKTEST_OP | jq -r '.data.result_summary.win_rate')
        DRAWDOWN=$(echo $BACKTEST_OP | jq -r '.data.result_summary.max_drawdown')
        echo "   Sharpe ratio: $SHARPE"
        echo "   Win rate: $WIN_RATE"
        echo "   Max drawdown: $DRAWDOWN"
    fi
else
    echo "   No backtest operation found"
fi

# List backtest operations
echo ""
echo "5. Backtest operations list:"
curl -s "http://localhost:8000/api/v1/operations?type=backtesting&limit=3" | jq '.data[] | {id: .operation_id, status: .status}'

echo ""
echo "=== M4 Complete ==="
```

---

## Files Created/Modified in M4

**New files**:
```
ktrdr/agents/workers/backtest_adapter.py
tests/unit/agent_tests/test_backtest_adapter.py
tests/integration/agent_tests/test_agent_backtest_gate.py
```

**Modified files**:
```
ktrdr/agents/workers/research_worker.py  # Add backtest gate check
ktrdr/api/services/agent_service.py      # Use real backtest adapter
```

---

*Estimated effort: ~3 hours*

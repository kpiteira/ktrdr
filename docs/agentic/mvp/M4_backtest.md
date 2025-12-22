# Milestone 4: Backtest Integration (Revised)

**Branch**: `feature/agent-mvp`
**Builds On**: M3 (Training Integration)
**Capability**: Real backtest runs after training passes gate

---

## Architecture Alignment

**Pattern**: The orchestrator directly calls BacktestingService and tracks the real backtest operation. NO adapter, NO nested polling.

```
Orchestrator wakes up (phase = training, training op COMPLETED, gate PASS)
  → calls BacktestingService.run_backtest()
  → stores backtest_op_id in metadata
  → sets phase = "backtesting"
  → goes to sleep

Orchestrator wakes up (phase = backtesting)
  → checks backtest_op_id status
  → if RUNNING: sleep
  → if COMPLETED: check gate, start assessment
  → if FAILED: fail parent
```

**What we will NOT do:**
- ❌ BacktestWorkerAdapter with nested polling
- ❌ Wrapper operations around real backtest operations
- ❌ Any polling inside child workers

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

## Task 4.1: Add Backtest Service Integration to Orchestrator

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Add method to start backtest via BacktestingService and update main loop to handle backtesting phase.

**Implementation Notes**:

```python
# In research_worker.py

class AgentResearchWorker:

    @property
    def backtest_service(self):
        """Lazy load BacktestingService."""
        if self._backtest_service is None:
            from ktrdr.api.endpoints.workers import get_worker_registry
            from ktrdr.backtesting.backtesting_service import BacktestingService
            registry = get_worker_registry()
            self._backtest_service = BacktestingService(worker_registry=registry)
        return self._backtest_service

    async def _start_backtest(self, operation_id: str) -> None:
        """Start backtest by calling BacktestingService directly.

        Stores the real backtest operation ID in parent metadata.
        """
        from datetime import datetime

        parent_op = await self.ops.get_operation(operation_id)
        params = parent_op.metadata.parameters

        strategy_path = params.get("strategy_path")
        model_path = params.get("model_path")

        # Load strategy config for symbol/timeframe
        config = self._load_strategy_config(strategy_path)
        symbol = config.get("training_data", {}).get("symbols", {}).get("list", ["EURUSD"])[0]
        timeframe = config.get("training_data", {}).get("timeframes", {}).get("list", ["1h"])[0]

        # Call service directly - returns immediately with operation_id
        result = await self.backtest_service.run_backtest(
            symbol=symbol,
            timeframe=timeframe,
            strategy_config_path=strategy_path,
            model_path=model_path,
            start_date=datetime(2024, 1, 1),  # Held-out period
            end_date=datetime(2024, 12, 31),
        )

        backtest_op_id = result["operation_id"]

        # Store in parent metadata and update phase
        params["phase"] = "backtesting"
        params["backtest_op_id"] = backtest_op_id

        logger.info(f"Backtest started: {backtest_op_id}")
```

**Main loop addition** (backtesting phase):

```python
elif phase == "backtesting":
    # Check REAL backtest operation directly
    backtest_op_id = op.metadata.parameters.get("backtest_op_id")
    backtest_op = await self.ops.get_operation(backtest_op_id)

    if backtest_op.status == OperationStatus.COMPLETED:
        # Extract metrics from result_summary.metrics (nested structure)
        result_summary = backtest_op.result_summary or {}
        metrics = result_summary.get("metrics", {})

        backtest_result = {
            "sharpe_ratio": metrics.get("sharpe_ratio", 0),
            "win_rate": metrics.get("win_rate", 0),
            "max_drawdown": metrics.get("max_drawdown_pct", 1.0),
            "total_return": metrics.get("total_return", 0),
            "total_trades": metrics.get("total_trades", 0),
        }

        op.metadata.parameters["backtest_result"] = backtest_result

        # Check gate
        passed, reason = check_backtest_gate(backtest_result)
        if not passed:
            raise GateFailedError(f"Backtest gate failed: {reason}")

        await self._start_phase_worker(operation_id, "assessing")

    elif backtest_op.status == OperationStatus.FAILED:
        raise WorkerError(f"Backtest failed: {backtest_op.error_message}")
```

**Unit Tests** (`tests/unit/agent_tests/test_research_worker_backtest.py`):
- [ ] Test: Backtest service called with correct params
- [ ] Test: backtest_op_id stored in parent metadata
- [ ] Test: Phase transitions to "backtesting" after training gate passes
- [ ] Test: Backtest metrics extracted from result_summary.metrics
- [ ] Test: Backtest gate checked when backtest completes
- [ ] Test: GateFailedError raised on gate failure
- [ ] Test: Phase transitions to "assessing" on gate pass

**Acceptance Criteria**:
- [ ] Orchestrator calls BacktestingService.run_backtest() directly
- [ ] Real backtest operation ID stored in parent metadata
- [ ] Orchestrator polls real backtest operation (no adapter)
- [ ] Backtest gate applied after backtest completes
- [ ] Metrics correctly extracted from nested result_summary.metrics

---

## Task 4.2: Delete BacktestWorkerAdapter

**File(s)**:
- `ktrdr/agents/workers/backtest_adapter.py` (DELETE)
- `tests/unit/agent_tests/test_backtest_adapter.py` (DELETE)
- `ktrdr/agents/workers/stubs.py` (MODIFY - remove StubBacktestWorker)

**Type**: CODING

**Description**: Remove the incorrect adapter that was created.

**Implementation Notes**:

```bash
# Delete files
rm ktrdr/agents/workers/backtest_adapter.py
rm tests/unit/agent_tests/test_backtest_adapter.py

# Revert commit if needed
git revert ca20a1b  # The backtest adapter commit
```

**Acceptance Criteria**:
- [ ] BacktestWorkerAdapter deleted
- [ ] No reference to backtest_worker in orchestrator constructor
- [ ] StubBacktestWorker removed from stubs.py

---

## Task 4.3: Update Stub Workers

**File(s)**: `ktrdr/agents/workers/stubs.py`
**Type**: CODING

**Description**: Update stubs to only include workers that are needed (Design and Assessment only, since those are Claude calls).

**Implementation Notes**:

```python
# stubs.py - simplified
"""Stub workers for testing.

Only Design and Assessment need stubs because they're Claude calls.
Training and Backtest are handled by the orchestrator calling services directly.
"""

class StubDesignWorker:
    """Stub design worker for testing."""

    async def run(self, parent_operation_id: str) -> dict[str, Any]:
        return {
            "success": True,
            "strategy_name": "stub_strategy_v1",
            "strategy_path": "/app/strategies/stub_strategy_v1.yaml",
            "input_tokens": 100,
            "output_tokens": 50,
        }


class StubAssessmentWorker:
    """Stub assessment worker for testing."""

    async def run(
        self, parent_operation_id: str, results: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "success": True,
            "verdict": "promising",
            "strengths": ["Good test coverage"],
            "weaknesses": ["Stub data"],
            "suggestions": ["Use real data"],
            "input_tokens": 100,
            "output_tokens": 50,
        }
```

**Acceptance Criteria**:
- [ ] Only StubDesignWorker and StubAssessmentWorker remain
- [ ] No StubTrainingWorker or StubBacktestWorker

---

## Task 4.4: Update AgentService

**File(s)**: `ktrdr/api/services/agent_service.py`
**Type**: CODING

**Description**: Update AgentService to pass services instead of workers for training/backtest.

**Implementation Notes**:

```python
class AgentService:
    def _get_worker(self) -> AgentResearchWorker:
        if self._worker is None:
            self._worker = AgentResearchWorker(
                operations_service=self.ops,
                design_worker=AgentDesignWorker(self.ops),
                assessment_worker=StubAssessmentWorker(),  # Still stub until M5
                # Services lazy-loaded inside orchestrator
                training_service=None,
                backtest_service=None,
            )
        return self._worker
```

**Acceptance Criteria**:
- [ ] AgentService creates orchestrator with correct params
- [ ] No training_worker or backtest_worker parameters

---

## Task 4.5: Integration Test

**File(s)**: `tests/integration/agent_tests/test_agent_backtest_real.py`
**Type**: CODING

**Description**: Integration test that verifies real backtest runs after training.

**Implementation Notes**:

```python
@pytest.mark.integration
@pytest.mark.slow
async def test_backtest_runs_after_training():
    """Backtest phase runs after training gate passes."""
    # This test requires full system running
    # Verify:
    # 1. backtest_op_id in parent metadata is a REAL backtesting operation
    # 2. Backtest operation has metrics in result_summary.metrics
    # 3. Gate evaluated correctly
```

**Acceptance Criteria**:
- [ ] Real backtest operation created
- [ ] Backtest operation visible in operations list
- [ ] Backtest metrics stored in parent metadata
- [ ] Gate evaluated correctly

---

## Milestone 4 Verification

```bash
# 1. Trigger cycle
curl -s -X POST http://localhost:8000/api/v1/agent/trigger | jq

# 2. Wait for backtesting phase
# Check that backtest_op_id is a REAL backtest operation
curl -s http://localhost:8000/api/v1/agent/status | jq

# 3. Verify backtest operation exists and is type "backtesting"
BACKTEST_OP_ID=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.child_operation_id')
curl -s "http://localhost:8000/api/v1/operations/$BACKTEST_OP_ID" | jq '.data.operation_type'
# Expected: "backtesting"

# 4. Check backtest metrics after completion (note: nested in .metrics)
curl -s "http://localhost:8000/api/v1/operations/$BACKTEST_OP_ID" | jq '.data.result_summary.metrics'
```

---

## Files Changed in M4

**Deleted**:
- `ktrdr/agents/workers/backtest_adapter.py`
- `tests/unit/agent_tests/test_backtest_adapter.py`

**Modified**:
- `ktrdr/agents/workers/research_worker.py` - Add _start_backtest(), update main loop
- `ktrdr/agents/workers/stubs.py` - Remove StubBacktestWorker, StubTrainingWorker
- `ktrdr/api/services/agent_service.py` - Update worker creation
- `tests/unit/agent_tests/test_research_worker.py` - Mock services

**New**:
- `tests/unit/agent_tests/test_research_worker_backtest.py`
- `tests/integration/agent_tests/test_agent_backtest_real.py`

---

## Key Implementation Notes

### Backtest Metrics Structure

The BacktestingService returns metrics nested under `result_summary.metrics`:

```python
{
    "result_summary": {
        "metrics": {
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "max_drawdown": 15000.0,      # Absolute value in $
            "max_drawdown_pct": 0.15,     # Percentage (use this for gate)
            "total_return": 25000.0,
            "total_trades": 42,
        }
    }
}
```

Use `max_drawdown_pct` for the backtest gate evaluation.

### Service Dependencies

Both TrainingService and BacktestingService require WorkerRegistry:

```python
from ktrdr.api.endpoints.workers import get_worker_registry
registry = get_worker_registry()
service = BacktestingService(worker_registry=registry)
```

---

*Estimated effort: ~2-3 hours*

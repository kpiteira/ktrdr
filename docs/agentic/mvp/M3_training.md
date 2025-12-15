# Milestone 3: Training Integration (Revised)

**Branch**: `feature/agent-mvp`
**Builds On**: M2 (Design Worker)
**Capability**: Real training runs after design, with quality gate

---

## Architecture Alignment

**Pattern**: The orchestrator directly calls TrainingService and tracks the real training operation. NO adapter, NO nested polling.

```
Orchestrator wakes up (phase = designing, child COMPLETED)
  → calls TrainingService.start_training()
  → stores training_op_id in metadata
  → sets phase = "training"
  → goes to sleep

Orchestrator wakes up (phase = training)
  → checks training_op_id status
  → if RUNNING: sleep
  → if COMPLETED: check gate, start backtest
  → if FAILED: fail parent
```

**What we will NOT do:**
- ❌ TrainingWorkerAdapter with nested polling
- ❌ Wrapper operations around real training operations
- ❌ Any polling inside child workers

---

## E2E Test

```bash
ktrdr agent trigger
# Wait for training to complete (~5-10 minutes)

ktrdr agent status
# Expected: Phase = backtesting (if gate passed) or status = failed (if gate failed)

ktrdr operations list --type training
# Expected: Training operation with COMPLETED status
```

---

## Task 3.1: Add Training Service Integration to Orchestrator

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Modify orchestrator to directly call TrainingService when transitioning to training phase. The orchestrator tracks the real training operation ID.

**Implementation Notes**:

```python
# In research_worker.py

class AgentResearchWorker:
    def __init__(
        self,
        operations_service: Any,
        design_worker: ChildWorker,
        # NO training_worker - we call the service directly
        assessment_worker: ChildWorker,
        training_service: Any = None,  # TrainingService
        backtest_service: Any = None,  # BacktestingService
    ):
        self.ops = operations_service
        self.design_worker = design_worker
        self.assessment_worker = assessment_worker
        self._training_service = training_service
        self._backtest_service = backtest_service

    @property
    def training_service(self):
        """Lazy load TrainingService."""
        if self._training_service is None:
            from ktrdr.api.endpoints.workers import get_worker_registry
            from ktrdr.api.services.training_service import TrainingService
            registry = get_worker_registry()
            self._training_service = TrainingService(worker_registry=registry)
        return self._training_service

    async def _start_training(self, operation_id: str) -> None:
        """Start training by calling TrainingService directly.

        Stores the real training operation ID in parent metadata.
        """
        parent_op = await self.ops.get_operation(operation_id)
        strategy_path = parent_op.metadata.parameters.get("strategy_path")

        # Load strategy config to get training params
        config = self._load_strategy_config(strategy_path)
        symbols = config.get("training_data", {}).get("symbols", {}).get("list", ["EURUSD"])
        timeframes = config.get("training_data", {}).get("timeframes", {}).get("list", ["1h"])
        strategy_name = config.get("name", "unknown")

        # Call service directly - this returns immediately with operation_id
        result = await self.training_service.start_training(
            symbols=symbols,
            timeframes=timeframes,
            strategy_name=strategy_name,
        )

        training_op_id = result["operation_id"]

        # Store in parent metadata and update phase
        parent_op.metadata.parameters["phase"] = "training"
        parent_op.metadata.parameters["training_op_id"] = training_op_id

        logger.info(f"Training started: {training_op_id}")
```

**Changes to main loop**:

```python
async def run(self, operation_id: str) -> dict[str, Any]:
    while True:
        op = await self.ops.get_operation(operation_id)
        phase = op.metadata.parameters.get("phase", "idle")

        if phase == "idle":
            await self._start_phase_worker(operation_id, "designing")

        elif phase == "designing":
            child_op_id = op.metadata.parameters.get("design_op_id")
            child_op = await self.ops.get_operation(child_op_id)

            if child_op.status == OperationStatus.COMPLETED:
                # Store design results, start training
                result = child_op.result_summary or {}
                op.metadata.parameters["strategy_name"] = result.get("strategy_name")
                op.metadata.parameters["strategy_path"] = result.get("strategy_path")
                await self._start_training(operation_id)
            elif child_op.status == OperationStatus.FAILED:
                raise WorkerError(f"Design failed: {child_op.error_message}")

        elif phase == "training":
            # Check REAL training operation directly
            training_op_id = op.metadata.parameters.get("training_op_id")
            training_op = await self.ops.get_operation(training_op_id)

            if training_op.status == OperationStatus.COMPLETED:
                result = training_op.result_summary or {}
                op.metadata.parameters["training_result"] = result
                op.metadata.parameters["model_path"] = result.get("model_path")

                # Check gate
                passed, reason = check_training_gate(result)
                if not passed:
                    raise GateFailedError(f"Training gate failed: {reason}")

                await self._start_backtest(operation_id)
            elif training_op.status == OperationStatus.FAILED:
                raise WorkerError(f"Training failed: {training_op.error_message}")

        # ... backtesting and assessing phases ...

        await self._cancellable_sleep(self.POLL_INTERVAL)
```

**Unit Tests** (`tests/unit/agent_tests/test_research_worker_training.py`):
- [ ] Test: Training service called with correct params from strategy config
- [ ] Test: training_op_id stored in parent metadata
- [ ] Test: Phase transitions to "training" after design completes
- [ ] Test: Training gate checked when training completes
- [ ] Test: GateFailedError raised on gate failure
- [ ] Test: Phase transitions to "backtesting" on gate pass

**Acceptance Criteria**:
- [ ] Orchestrator calls TrainingService.start_training() directly
- [ ] Real training operation ID stored in parent metadata
- [ ] Orchestrator polls real training operation (no adapter)
- [ ] Training gate applied after training completes

---

## Task 3.2: Remove TrainingWorkerAdapter and Stubs

**File(s)**:
- `ktrdr/agents/workers/training_adapter.py` (DELETE)
- `tests/unit/agent_tests/test_training_adapter.py` (DELETE)
- `ktrdr/agents/workers/stubs.py` (MODIFY - remove StubTrainingWorker)
- `ktrdr/api/services/agent_service.py` (MODIFY)

**Type**: CODING

**Description**: Remove the incorrect adapter and update AgentService to not pass training_worker.

**Implementation Notes**:

```python
# agent_service.py - updated
class AgentService:
    def _get_worker(self) -> AgentResearchWorker:
        if self._worker is None:
            self._worker = AgentResearchWorker(
                operations_service=self.ops,
                design_worker=AgentDesignWorker(self.ops),
                # NO training_worker - orchestrator calls service directly
                assessment_worker=StubAssessmentWorker(),
                # Services injected for testing, lazy-loaded in production
                training_service=None,
                backtest_service=None,
            )
        return self._worker
```

**Acceptance Criteria**:
- [ ] TrainingWorkerAdapter deleted
- [ ] No reference to training_worker in orchestrator constructor
- [ ] StubTrainingWorker removed from stubs.py
- [ ] Tests updated to not use training adapter

---

## Task 3.3: Update Tests for New Pattern

**File(s)**: `tests/unit/agent_tests/test_research_worker.py`
**Type**: CODING

**Description**: Update existing tests to mock TrainingService instead of training worker.

**Implementation Notes**:

```python
@pytest.fixture
def mock_training_service():
    """Mock TrainingService that returns operation IDs."""
    service = AsyncMock()
    service.start_training.return_value = {
        "operation_id": "op_training_test_123",
        "success": True,
    }
    return service

@pytest.fixture
def orchestrator(mock_operations_service, mock_training_service):
    return AgentResearchWorker(
        operations_service=mock_operations_service,
        design_worker=StubDesignWorker(),
        assessment_worker=StubAssessmentWorker(),
        training_service=mock_training_service,
        backtest_service=mock_backtest_service,
    )
```

**Acceptance Criteria**:
- [ ] Tests mock services instead of workers for training/backtest
- [ ] Tests verify service called with correct params
- [ ] Tests verify real operation IDs tracked in metadata

---

## Task 3.4: Integration Test

**File(s)**: `tests/integration/agent_tests/test_agent_training_real.py`
**Type**: CODING

**Description**: Integration test that verifies real training runs.

**Acceptance Criteria**:
- [ ] Real training operation created
- [ ] Training operation visible in operations list
- [ ] Training result stored in parent metadata
- [ ] Gate evaluated correctly

---

## Milestone 3 Verification

```bash
# 1. Trigger cycle
curl -s -X POST http://localhost:8000/api/v1/agent/trigger | jq

# 2. Wait for training phase, check that training_op_id is a REAL training operation
curl -s http://localhost:8000/api/v1/agent/status | jq '.training_op_id'

# 3. Verify training operation exists
TRAINING_OP_ID=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.child_operation_id')
curl -s "http://localhost:8000/api/v1/operations/$TRAINING_OP_ID" | jq '.data.operation_type'
# Expected: "training" (NOT "agent_design" or wrapper)

# 4. Check training metrics after completion
curl -s "http://localhost:8000/api/v1/operations/$TRAINING_OP_ID" | jq '.data.result_summary'
```

---

## Files Changed in M3

**Deleted**:
- `ktrdr/agents/workers/training_adapter.py`
- `tests/unit/agent_tests/test_training_adapter.py`

**Modified**:
- `ktrdr/agents/workers/research_worker.py` - Add _start_training(), update main loop
- `ktrdr/agents/workers/stubs.py` - Remove StubTrainingWorker
- `ktrdr/api/services/agent_service.py` - Update worker creation
- `tests/unit/agent_tests/test_research_worker.py` - Mock services instead of workers

**New**:
- `tests/unit/agent_tests/test_research_worker_training.py`
- `tests/integration/agent_tests/test_agent_training_real.py`

---

*Estimated effort: ~3-4 hours*
